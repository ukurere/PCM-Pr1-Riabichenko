"""Прогін усіх вимірювань продуктивності.

Конфігурації:
  V0 (P=1); V2, V3 (K = --k-scaling), V4 seq і tree — за кожного P із --threads;
  V3 за P = --k-threads для кожного K із --ks (графік 3);
  false_sharing: заповнювачі 0 (A), 8, 24, 32, 56 (B) за кожного P (графік 4).

Методика (розділ 5 завдання):
  * спершу один попередній прогін кожної конфігурації, що до результатів не входить
    (файли потрапляють у кеш ОС, процесор виходить на робочу частоту);
  * далі --reps повторень; повторення чергуються по колу між конфігураціями,
    щоб повільний дрейф (нагрівання, фонові процеси) розподілявся рівномірно;
  * між запусками пауза --cooldown секунд;
  * вимірюваний час обчислення (compute_ms) не містить читання файлів і запису результату.

Результати дописуються в CSV одразу після кожного запуску:
  results/results.csv        — version, threads, K, merge, rep, read_ms, compute_ms, merge_ms, write_ms, total_occurrences
  results/false_sharing.csv  — impl, pad, element_bytes, threads, rep, time_ms
  results/system_info.txt    — конфігурація системи для звіту

Запуск: python scripts/bench.py [--reps 5] [--only v3,fs]
Перед запуском: закрити сторонні застосунки, підключити живлення, режим «Максимальна продуктивність»."""

import argparse
import csv
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

from runner import FALSE_SHARING, INVIDX, ROOT, int_list, run_false_sharing, run_invidx

CSV_COLUMNS = ["version", "threads", "K", "merge", "rep",
               "read_ms", "compute_ms", "merge_ms", "write_ms", "total_occurrences"]
FS_COLUMNS = ["impl", "pad", "element_bytes", "threads", "rep", "time_ms"]
FS_PADS = {0: "A", 8: "pad8", 24: "pad24", 32: "pad32", 56: "B"}


def build_configs(threads, ks, k_scaling, k_threads):
    configs = [("v0", 1, None, None)]
    configs += [("v2", p, None, None) for p in threads]
    configs += [("v3", p, k_scaling, None) for p in threads]
    configs += [("v3", k_threads, k, None) for k in ks]
    configs += [("v4", p, None, m) for p in threads for m in ("seq", "tree")]
    unique = []
    for c in configs:
        if c not in unique:
            unique.append(c)
    return unique


def label(cfg) -> str:
    mode, p, k, merge = cfg
    return f"{mode.upper()} P={p}" + (f" K={k}" if k else "") + (f" {merge}" if merge else "")


def open_csv(path: Path, columns, append: bool):
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = append and path.exists() and path.stat().st_size > 0
    f = open(path, "a" if exists else "w", newline="", encoding="utf-8")
    w = csv.DictWriter(f, fieldnames=columns)
    if not exists:
        w.writeheader()
    return f, w


def write_system_info(path: Path, args) -> None:
    lines = [f"Дата: {time.strftime('%Y-%m-%d %H:%M')}",
             f"ОС: {platform.platform()}",
             f"Процесор: {platform.processor()}",
             f"Логічних процесорів: {os.cpu_count()}"]
    if sys.platform == "win32":
        try:
            ps = ("[Console]::OutputEncoding = [Text.Encoding]::UTF8; "
                  "Get-CimInstance Win32_Processor | ForEach-Object { \"$($_.Name); фізичних ядер: "
                  "$($_.NumberOfCores); логічних: $($_.NumberOfLogicalProcessors); L2 (сумарно): "
                  "$($_.L2CacheSize) КБ; L3: $($_.L3CacheSize) КБ\" }; "
                  "\"ОЗП: $([math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory/1GB,1)) ГБ\"")
            out = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                                 capture_output=True, text=True, encoding="utf-8", errors="replace")
            lines += [l.strip() for l in out.stdout.splitlines() if l.strip()]
        except OSError:
            pass
    try:
        info = subprocess.run([str(FALSE_SHARING), "--info"], capture_output=True, text=True).stdout
        lines.append(f"false_sharing --info: {info.strip()}")
    except OSError:
        pass
    try:
        gxx = subprocess.run(["g++", "--version"], capture_output=True, text=True).stdout.splitlines()[0]
        lines.append(f"Компілятор: {gxx}")
    except (OSError, IndexError):
        pass
    lines += ["Параметри збирання: -std=c++17 -O2 -Wall -Wextra -pthread",
              f"Корпус: {args.input}",
              f"Повторень: {args.reps} (+1 попередній прогін), пауза між запусками: {args.cooldown} с"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def bench_index(args, configs) -> None:
    out_file = ROOT / "out" / "bench.tsv"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    f, w = open_csv(Path(args.out), CSV_COLUMNS, args.append)
    total_runs = len(configs) * (args.reps + 1)
    done = 0
    started = time.time()

    def run(cfg, rep):
        nonlocal done
        mode, p, k, merge = cfg
        r = run_invidx(args.exe, mode, p, args.input, out_file, k=k, merge=merge)
        done += 1
        eta = (time.time() - started) / done * (total_runs - done)
        tag = "попередній" if rep is None else f"rep {rep}"
        print(f"[{done:3d}/{total_runs}] {label(cfg):<20} {tag:<11} compute_ms={float(r['compute_ms']):9.1f}"
              f"   залишилось ~{eta / 60:.0f} хв", flush=True)
        time.sleep(args.cooldown)
        return r

    try:
        for cfg in configs:
            run(cfg, None)
        for rep in range(args.reps):
            for cfg in configs:
                mode, p, k, merge = cfg
                r = run(cfg, rep)
                w.writerow({"version": mode.upper(), "threads": p, "K": k or "", "merge": merge or "",
                            "rep": rep, "read_ms": r["read_ms"], "compute_ms": r["compute_ms"],
                            "merge_ms": r["merge_ms"], "write_ms": r["write_ms"],
                            "total_occurrences": r["total_occurrences"]})
                f.flush()
    finally:
        f.close()


def bench_false_sharing(args, threads) -> None:
    f, w = open_csv(Path(args.fs_out), FS_COLUMNS, args.append)
    try:
        for p in threads:
            for pad, impl in FS_PADS.items():
                rows = run_false_sharing(args.fs_exe, p, pad, args.reps)
                for r in rows:
                    w.writerow({"impl": impl, "pad": pad, "element_bytes": r["element_bytes"],
                                "threads": p, "rep": r["rep"], "time_ms": r["time_ms"]})
                f.flush()
                times = sorted(float(r["time_ms"]) for r in rows)
                print(f"false_sharing P={p} {impl:<6} median={times[len(times) // 2]:.1f} ms", flush=True)
                time.sleep(args.cooldown)
    finally:
        f.close()


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--exe", default=str(INVIDX))
    ap.add_argument("--fs-exe", default=str(FALSE_SHARING))
    ap.add_argument("--input", default=str(ROOT / "data" / "corpus_en"))
    ap.add_argument("--threads", default="1,2,4,8", help="кількості потоків через кому")
    ap.add_argument("--ks", default="1,4,16,64,256,1024,4096", help="значення K для графіка 3")
    ap.add_argument("--k-scaling", type=int, default=1024, help="K для V3 у графіках масштабування")
    ap.add_argument("--k-threads", type=int, default=8, help="P для дослідження залежності від K")
    ap.add_argument("--reps", type=int, default=5)
    ap.add_argument("--cooldown", type=float, default=2.0, help="пауза між запусками, с")
    ap.add_argument("--only", default="", help="обмежити версіями, напр. v3,v4,fs")
    ap.add_argument("--append", action="store_true", help="дописувати до наявних CSV")
    ap.add_argument("--out", default=str(ROOT / "results" / "results.csv"))
    ap.add_argument("--fs-out", default=str(ROOT / "results" / "false_sharing.csv"))
    args = ap.parse_args()

    threads = int_list(args.threads)
    only = {s.strip().lower() for s in args.only.split(",") if s.strip()}
    configs = build_configs(threads, int_list(args.ks), args.k_scaling, args.k_threads)
    if only:
        configs = [c for c in configs if c[0] in only]

    write_system_info(ROOT / "results" / "system_info.txt", args)
    if configs:
        print(f"Конфігурацій: {len(configs)}, запусків: {len(configs) * (args.reps + 1)}", flush=True)
        bench_index(args, configs)
    if not only or "fs" in only:
        bench_false_sharing(args, threads)
    print("Готово.")


if __name__ == "__main__":
    main()
