"""Графіки та аналіз за результатами bench.py.

Графіки (results/*.png):
  fig1_speedup.png        S(P) для всіх коректних версій + пряма ідеального прискорення
  fig2_efficiency.png     E(P)
  fig3_v3_k.png           час V3 залежно від K (логарифмічна вісь)
  fig4_false_sharing.png  час реалізацій A і B залежно від P
  fig5_padding.png        час залежно від розміру елемента (контрольне питання 7)
  fig6_merge.png          час злиття V4: послідовне і деревом

Аналіз (results/analysis.md):
  медіани з розкидом (мін – макс, IQR), S(P) = T(V0)/T(P), E(P) = S/P,
  метрика Карпа – Флатта e = (1/S - 1/P) / (1 - 1/P),
  оцінка послідовної частки s за законом Амдала (МНК для 1/S = s + (1-s)/P) і S(∞) = 1/s,
  точка припинення зменшення часу V3 за K, порівняння способів злиття V4.

Таблиці рахуються без сторонніх бібліотек; для графіків потрібен matplotlib.

Запуск: python scripts/plots.py [--csv results/results.csv] [--fs-csv results/false_sharing.csv]"""

import argparse
import csv
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path

from runner import ROOT

# Категоріальна палітра у фіксованому порядку (слоти 1–4), текст і поверхня
SERIES_COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
MARKERS = ["o", "s", "^", "D"]
SURFACE = "#fcfcfb"
TEXT = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
GRID = "#e4e3df"
REFERENCE = "#8a8984"

PLATEAU_TOLERANCE = 0.05  # подальше збільшення K дає менше ніж 5% виграшу


# ---------- статистика ----------

def summarize(values):
    v = sorted(values)
    if len(v) > 1:
        q = statistics.quantiles(v, n=4, method="inclusive")
        q1, q3 = q[0], q[2]
    else:
        q1 = q3 = v[0]
    return {"median": statistics.median(v), "min": v[0], "max": v[-1], "q1": q1, "q3": q3, "n": len(v)}


def karp_flatt(s, p):
    return (1 / s - 1 / p) / (1 - 1 / p) if p > 1 else None


def amdahl_fit(points):
    """МНК без вільного члена: (1/S - 1/P) = s * (1 - 1/P)."""
    num = sum((1 - 1 / p) * (1 / s - 1 / p) for p, s in points if p > 1)
    den = sum((1 - 1 / p) ** 2 for p, s in points if p > 1)
    return num / den if den else None


# ---------- читання даних ----------

def load_index_results(path: Path):
    groups = defaultdict(lambda: defaultdict(list))  # key -> field -> values
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            key = (r["version"], int(r["threads"]), int(r["K"]) if r["K"] else None, r["merge"] or None)
            groups[key]["compute"].append(float(r["compute_ms"]))
            groups[key]["merge"].append(float(r["merge_ms"]))
    return {k: {"compute": summarize(v["compute"]), "merge": summarize(v["merge"])} for k, v in groups.items()}


def load_fs_results(path: Path):
    groups = defaultdict(list)
    sizes = {}
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            key = (r["impl"], int(r["threads"]))
            groups[key].append(float(r["time_ms"]))
            sizes[r["impl"]] = int(r["element_bytes"])
    return {k: summarize(v) for k, v in groups.items()}, sizes


# ---------- вибір серій ----------

def scaling_series(res):
    """Серії для графіків 1–2: V2, V3 (K, наявний за всіх P), V4 seq, V4 tree."""
    threads_all = sorted({p for (v, p, k, m) in res if v != "V0"})
    v3_ks = [k for k in sorted({k for (v, p, k, m) in res if v == "V3"})
             if all(("V3", p, k, None) in res for p in threads_all)]
    k_scaling = v3_ks[-1] if v3_ks else None
    series = [("V2 (один м'ютекс)", "V2", None, None)]
    if k_scaling:
        series.append((f"V3 (K = {k_scaling})", "V3", k_scaling, None))
    series += [("V4 (злиття послідовне)", "V4", None, "seq"), ("V4 (злиття деревом)", "V4", None, "tree")]
    out = []
    for name, v, k, m in series:
        pts = [(p, res[(v, p, k, m)]) for p in threads_all if (v, p, k, m) in res]
        if pts:
            out.append((name, v, k, m, pts))
    return out, threads_all, k_scaling


def k_sweep(res):
    """V3 за фіксованого P з найбільшою кількістю значень K (графік 3)."""
    by_p = defaultdict(list)
    for (v, p, k, m), s in res.items():
        if v == "V3":
            by_p[p].append((k, s))
    if not by_p:
        return None, []
    p = max(by_p, key=lambda q: (len(by_p[q]), q))
    return p, sorted(by_p[p])


def plateau_k(points):
    """Найменше K, після якого жодне більше K не зменшує медіану більш ніж на PLATEAU_TOLERANCE."""
    for i, (k, s) in enumerate(points):
        rest = [t["compute"]["median"] for _, t in points[i + 1:]]
        if all(r >= s["compute"]["median"] * (1 - PLATEAU_TOLERANCE) for r in rest):
            return k
    return points[-1][0]


# ---------- аналіз (markdown) ----------

def fmt(x, digits=1):
    return "—" if x is None else f"{x:.{digits}f}"


def write_analysis(path, res, fs, fs_sizes):
    t0 = res[("V0", 1, None, None)]["compute"]["median"] if ("V0", 1, None, None) in res else None
    series, threads_all, k_scaling = scaling_series(res)
    L = ["# Аналіз результатів вимірювань", ""]
    if t0:
        L += [f"Базовий час T(V0) = **{t0:.1f} мс** (медіана). Прискорення S(P) = T(V0)/T(P), "
              f"ефективність E(P) = S/P, e — метрика Карпа – Флатта.", ""]

    L += ["## Таблиця результатів (медіана, мс)", "",
          "| Версія | P | K | Злиття | Медіана | Мін | Макс | IQR | n | S(P) | E(P) | e |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for key in sorted(res, key=lambda k: (k[0], k[3] or "", k[2] or 0, k[1])):
        v, p, k, m = key
        c = res[key]["compute"]
        s = t0 / c["median"] if t0 else None
        e = s / p if s else None
        kf = karp_flatt(s, p) if s else None
        L.append(f"| {v} | {p} | {k or ''} | {m or ''} | {c['median']:.1f} | {c['min']:.1f} | {c['max']:.1f} | "
                 f"{c['q3'] - c['q1']:.1f} | {c['n']} | {fmt(s, 2)} | {fmt(e, 2)} | {fmt(kf, 3)} |")

    if t0 and series:
        L += ["", "## Закон Амдала", "",
              "Послідовна частка s оцінена методом найменших квадратів за всіма P > 1 "
              "(1/S − 1/P = s·(1 − 1/P)); S(∞) = 1/s — гранична оцінка прискорення.", "",
              "| Версія | s | S(∞) = 1/s | S(P) за найбільшого P | e за найбільшого P |",
              "|---|---|---|---|---|"]
        for name, v, k, m, pts in series:
            sp = [(p, t0 / st["compute"]["median"]) for p, st in pts]
            s_fit = amdahl_fit(sp)
            p_max, s_max = sp[-1]
            if s_fit is None:
                s_inf_text = "—"
            elif s_fit >= 1:
                s_inf_text = "не застосовно: S < 1, накладні витрати перевищують виграш"
            elif s_fit <= 0:
                s_inf_text = "∞ (s ≤ 0: надлінійне прискорення)"
            else:
                s_inf_text = f"{1 / s_fit:.2f}"
            L.append(f"| {name} | {fmt(s_fit, 3)} | {s_inf_text} | "
                     f"{s_max:.2f} (P = {p_max}) | {fmt(karp_flatt(s_max, p_max), 3)} |")

    p_k, pts_k = k_sweep(res)
    if pts_k:
        pk = plateau_k(pts_k)
        L += ["", f"## V3: залежність часу від K (P = {p_k})", "",
              "| K | Медіана, мс | Мін | Макс |", "|---|---|---|---|"]
        for k, s in pts_k:
            c = s["compute"]
            L.append(f"| {k} | {c['median']:.1f} | {c['min']:.1f} | {c['max']:.1f} |")
        L += ["", f"Час перестає зменшуватися після **K = {pk}** "
                  f"(подальше збільшення K дає менше ніж {PLATEAU_TOLERANCE:.0%} виграшу)."]

    merge_rows = [(p, res.get(("V4", p, None, "seq")), res.get(("V4", p, None, "tree"))) for p in threads_all]
    merge_rows = [r for r in merge_rows if r[1] and r[2] and r[0] > 1]
    if merge_rows:
        L += ["", "## V4: способи злиття", "",
              "| P | Кроків seq (P−1) | Кроків tree (⌈log₂P⌉) | Злиття seq, мс | Злиття tree, мс | seq / tree | "
              "Разом seq, мс | Разом tree, мс |", "|---|---|---|---|---|---|---|---|"]
        for p, sq, tr in merge_rows:
            ms, mt = sq["merge"]["median"], tr["merge"]["median"]
            L.append(f"| {p} | {p - 1} | {math.ceil(math.log2(p))} | {ms:.1f} | {mt:.1f} | {ms / mt:.2f} | "
                     f"{sq['compute']['median']:.1f} | {tr['compute']['median']:.1f} |")

    if fs:
        fs_threads = sorted({p for _, p in fs})
        impls = sorted(fs_sizes, key=lambda i: fs_sizes[i])
        L += ["", "## Хибне розділення (медіана, мс)", "",
              "| P | " + " | ".join(f"{i} ({fs_sizes[i]} Б)" for i in impls) + " | A / B |",
              "|---|" + "---|" * (len(impls) + 1)]
        for p in fs_threads:
            cells = [fmt(fs[(i, p)]["median"]) if (i, p) in fs else "—" for i in impls]
            ratio = fs[("A", p)]["median"] / fs[("B", p)]["median"] if ("A", p) in fs and ("B", p) in fs else None
            L.append(f"| {p} | " + " | ".join(cells) + f" | {fmt(ratio, 2)} |")

    path.write_text("\n".join(L) + "\n", encoding="utf-8")


# ---------- графіки ----------

def style(plt):
    plt.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
        "axes.edgecolor": GRID, "axes.labelcolor": TEXT_SECONDARY, "axes.titlecolor": TEXT,
        "axes.titlesize": 12, "axes.labelsize": 10, "axes.grid": True, "grid.color": GRID,
        "grid.linewidth": 0.8, "xtick.color": TEXT_SECONDARY, "ytick.color": TEXT_SECONDARY,
        "legend.frameon": False, "legend.labelcolor": TEXT, "font.size": 10,
        "axes.spines.top": False, "axes.spines.right": False, "lines.linewidth": 2,
    })


def errbars(values_med, values_lo, values_hi):
    return [[m - lo for m, lo in zip(values_med, values_lo)], [hi - m for m, hi in zip(values_med, values_hi)]]


def legend_below(ax, ncol=3):
    """Легенда під областю графіка, щоб не перекривати лінії."""
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.16), ncol=ncol, fontsize=9)


def end_labels(ax, x, items):
    """Підписи значень у кінці ліній, розсунуті по вертикалі, щоб не накладалися.
    items — список (y, текст)."""
    lo, hi = ax.get_ylim()
    gap = 0.045 * (hi - lo)
    placed = []
    for y, text in sorted(items):
        pos = max(y, placed[-1] + gap) if placed else y
        placed.append(pos)
        ax.annotate(text, (x, y), xytext=(x, pos), textcoords="data", color=TEXT, fontsize=8, va="center",
                    ha="left", annotation_clip=False,
                    bbox={"boxstyle": "square,pad=0.1", "fc": SURFACE, "ec": "none"})


def physical_cores_line(ax, cores, ymax_text):
    if cores:
        ax.axvline(cores, color=REFERENCE, linewidth=1, linestyle=":")
        ax.text(cores, ymax_text, f" {cores} фізичні ядра", color=TEXT_SECONDARY, fontsize=8, va="top")


def plot_all(out_dir, res, fs, fs_sizes, cores):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    style(plt)
    saved = []
    t0 = res[("V0", 1, None, None)]["compute"]["median"] if ("V0", 1, None, None) in res else None
    series, threads_all, _ = scaling_series(res)

    if t0 and series:
        # 1. Прискорення
        fig, ax = plt.subplots(figsize=(7, 5))
        pmax = max(threads_all)
        ax.plot([1, pmax], [1, pmax], color=REFERENCE, linestyle="--", linewidth=1.5, label="ідеальне S = P")
        last = []
        for i, (name, v, k, m, pts) in enumerate(series):
            ps = [p for p, _ in pts]
            med = [t0 / st["compute"]["median"] for _, st in pts]
            lo = [t0 / st["compute"]["max"] for _, st in pts]
            hi = [t0 / st["compute"]["min"] for _, st in pts]
            ax.errorbar(ps, med, yerr=errbars(med, lo, hi), color=SERIES_COLORS[i], marker=MARKERS[i],
                        markersize=7, capsize=3, label=name)
            last.append((med[-1], f" {med[-1]:.2f}"))
        ax.axhline(1, color=REFERENCE, linewidth=0.8)
        physical_cores_line(ax, cores, pmax)
        ax.set(xlabel="Кількість потоків P", ylabel="Прискорення S(P) = T(V0) / T(P)",
               title="Прискорення відносно послідовної версії V0", xticks=threads_all)
        ax.set_ylim(bottom=0)
        ax.set_xlim(right=pmax * 1.08)
        end_labels(ax, pmax, last)
        legend_below(ax)
        fig.tight_layout()
        fig.savefig(out_dir / "fig1_speedup.png", dpi=200)
        saved.append("fig1_speedup.png")
        plt.close(fig)

        # 2. Ефективність
        fig, ax = plt.subplots(figsize=(7, 5))
        ax.axhline(1, color=REFERENCE, linestyle="--", linewidth=1.5, label="ідеальна E = 1")
        for i, (name, v, k, m, pts) in enumerate(series):
            ps = [p for p, _ in pts]
            eff = [t0 / st["compute"]["median"] / p for p, st in pts]
            ax.plot(ps, eff, color=SERIES_COLORS[i], marker=MARKERS[i], markersize=7, label=name)
        physical_cores_line(ax, cores, ax.get_ylim()[1])
        ax.set(xlabel="Кількість потоків P", ylabel="Ефективність E(P) = S(P) / P",
               title="Ефективність паралельних версій", xticks=threads_all)
        ax.set_ylim(bottom=0)
        legend_below(ax)
        fig.tight_layout()
        fig.savefig(out_dir / "fig2_efficiency.png", dpi=200)
        saved.append("fig2_efficiency.png")
        plt.close(fig)

    # 3. V3 залежно від K
    p_k, pts_k = k_sweep(res)
    if pts_k:
        fig, ax = plt.subplots(figsize=(7, 4.5))
        ks = [k for k, _ in pts_k]
        med = [s["compute"]["median"] / 1000 for _, s in pts_k]
        lo = [s["compute"]["min"] / 1000 for _, s in pts_k]
        hi = [s["compute"]["max"] / 1000 for _, s in pts_k]
        ax.errorbar(ks, med, yerr=errbars(med, lo, hi), color=SERIES_COLORS[1], marker=MARKERS[1],
                    markersize=7, capsize=3, label=f"V3, P = {p_k}")
        if t0:
            ax.axhline(t0 / 1000, color=REFERENCE, linestyle="--", linewidth=1.5, label="V0 (послідовна)")
        pk = plateau_k(pts_k)
        pk_med = dict(zip(ks, med))[pk]
        ax.annotate(f"плато з K = {pk}", (pk, pk_med), textcoords="offset points", xytext=(0, 18),
                    ha="center", color=TEXT, fontsize=9, arrowprops={"arrowstyle": "-", "color": REFERENCE})
        ax.set_xscale("log", base=2)
        ax.set_xticks(ks)
        ax.set_xticklabels([str(k) for k in ks])
        ax.set(xlabel="Кількість блокувальних змінних K (логарифмічна шкала)", ylabel="Час обчислення, с",
               title="V3: час виконання залежно від кількості блокувальних змінних")
        ax.set_ylim(bottom=0)
        ax.legend(loc="upper right")
        fig.tight_layout()
        fig.savefig(out_dir / "fig3_v3_k.png", dpi=200)
        saved.append("fig3_v3_k.png")
        plt.close(fig)

    if fs:
        fs_threads = sorted({p for _, p in fs})
        # 4. Хибне розділення: A і B
        fig, ax = plt.subplots(figsize=(7, 5))
        for i, (impl, name) in enumerate([("A", "A — елементи поспіль (8 Б)"),
                                          ("B", "B — окремий рядок кешу (64 Б)")]):
            ps = [p for p in fs_threads if (impl, p) in fs]
            med = [fs[(impl, p)]["median"] for p in ps]
            lo = [fs[(impl, p)]["min"] for p in ps]
            hi = [fs[(impl, p)]["max"] for p in ps]
            ax.errorbar(ps, med, yerr=errbars(med, lo, hi), color=SERIES_COLORS[i], marker=MARKERS[i],
                        markersize=7, capsize=3, label=name)
        physical_cores_line(ax, cores, ax.get_ylim()[1])
        ax.set(xlabel="Кількість потоків P", ylabel="Час, мс",
               title="Хибне розділення: 10 млн інкрементів на потік", xticks=fs_threads)
        ax.set_ylim(bottom=0)
        legend_below(ax, ncol=2)
        fig.tight_layout()
        fig.savefig(out_dir / "fig4_false_sharing.png", dpi=200)
        saved.append("fig4_false_sharing.png")
        plt.close(fig)

        # 5. Розмір елемента
        impls = sorted(fs_sizes, key=lambda i: fs_sizes[i])
        sizes = [fs_sizes[i] for i in impls]
        fig, ax = plt.subplots(figsize=(7, 5))
        for i, p in enumerate([p for p in fs_threads if p > 1][-4:]):
            med = [fs[(impl, p)]["median"] if (impl, p) in fs else math.nan for impl in impls]
            ax.plot(sizes, med, color=SERIES_COLORS[i], marker=MARKERS[i], markersize=7, label=f"P = {p}")
        ax.set_xticks(sizes)
        ax.set(xlabel="Розмір елемента масиву, байтів (8 + заповнювач)", ylabel="Час, мс",
               title="Вплив розміру заповнювача на хибне розділення")
        ax.set_ylim(bottom=0)
        ax.axvline(64, color=REFERENCE, linewidth=1, linestyle=":")
        ax.text(64, ax.get_ylim()[1], "рядок кешу 64 Б ", color=TEXT_SECONDARY, fontsize=8, va="top", ha="right")
        legend_below(ax)
        fig.tight_layout()
        fig.savefig(out_dir / "fig5_padding.png", dpi=200)
        saved.append("fig5_padding.png")
        plt.close(fig)

    # 6. Злиття V4
    rows = [(p, res.get(("V4", p, None, "seq")), res.get(("V4", p, None, "tree"))) for p in threads_all]
    rows = [r for r in rows if r[1] and r[2] and r[0] > 1]
    if rows:
        fig, ax = plt.subplots(figsize=(7, 5))
        ps = [p for p, _, _ in rows]
        for i, (idx, name) in enumerate([(1, "послідовне (P − 1 кроків)"), (2, "деревом (⌈log₂P⌉ кроків)")]):
            med = [r[idx]["merge"]["median"] for r in rows]
            lo = [r[idx]["merge"]["min"] for r in rows]
            hi = [r[idx]["merge"]["max"] for r in rows]
            ax.errorbar(ps, med, yerr=errbars(med, lo, hi), color=SERIES_COLORS[2 + i], marker=MARKERS[2 + i],
                        markersize=7, capsize=3, label=name)
        ax.set(xlabel="Кількість потоків P", ylabel="Час злиття, мс",
               title="V4: час злиття локальних індексів", xticks=ps)
        ax.set_ylim(bottom=0)
        legend_below(ax, ncol=2)
        fig.tight_layout()
        fig.savefig(out_dir / "fig6_merge.png", dpi=200)
        saved.append("fig6_merge.png")
        plt.close(fig)
    return saved


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", default=str(ROOT / "results" / "results.csv"))
    ap.add_argument("--fs-csv", default=str(ROOT / "results" / "false_sharing.csv"))
    ap.add_argument("--out-dir", default=str(ROOT / "results"))
    ap.add_argument("--cores", type=int, default=4, help="кількість фізичних ядер (позначка на графіках)")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    res = load_index_results(Path(args.csv))
    fs, fs_sizes = load_fs_results(Path(args.fs_csv)) if Path(args.fs_csv).exists() else ({}, {})

    analysis = out_dir / "analysis.md"
    write_analysis(analysis, res, fs, fs_sizes)
    print(f"Аналіз: {analysis}")
    try:
        saved = plot_all(out_dir, res, fs, fs_sizes, args.cores)
        print("Графіки: " + ", ".join(saved))
    except ImportError:
        print("matplotlib не встановлено — графіки пропущено (pip install -r requirements.txt)")


if __name__ == "__main__":
    main()
