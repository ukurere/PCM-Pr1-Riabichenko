"""Частка загальної кількості оновлень індексу, що припадає на N найчастотніших
слів (п. 3.4 і контрольне питання 4).

У V1–V3 кожне входження слова — одна операція оновлення індексу, тому кількість
оновлень слова дорівнює його загальній кількості входжень у вихідному файлі V0.

Результати: results/zipf_top20.csv (ранг, слово, кількість, частка, накопичена частка)
і зведення в stdout.

Запуск: python scripts/zipf_top20.py [--index out/verify/v0.tsv] [--top 20]"""

import argparse
import csv
import sys
from pathlib import Path

from runner import ROOT


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--index", default=str(ROOT / "out" / "verify" / "v0.tsv"), help="вихідний файл V0")
    ap.add_argument("--top", type=int, default=20)
    ap.add_argument("--out", default=str(ROOT / "results" / "zipf_top20.csv"))
    args = ap.parse_args()

    index = Path(args.index)
    if not index.exists():
        sys.exit(f"{index} не знайдено: спершу запустіть V0, напр. "
                 f"build\\invidx --mode v0 --input data\\corpus_en --output {index}")

    counts = []
    with open(index, encoding="utf-8") as f:
        for line in f:
            word, total, _ = line.split("\t", 2)
            counts.append((int(total), word))
    counts.sort(key=lambda c: (-c[0], c[1].encode("utf-8")))
    total = sum(c for c, _ in counts)

    rows, cumulative = [], 0
    for rank, (c, w) in enumerate(counts[: args.top], 1):
        cumulative += c
        rows.append({"rank": rank, "word": w, "count": c,
                     "share_percent": round(100 * c / total, 3),
                     "cumulative_percent": round(100 * cumulative / total, 3)})

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    print(f"Слів у словнику:          {len(counts)}")
    print(f"Усього оновлень індексу:  {total}")
    print(f"Частка {args.top} найчастотніших:  {100 * cumulative / total:.2f}%\n")
    print(f"{'ранг':>4}  {'слово':<10} {'кількість':>10} {'частка':>8} {'накопич.':>9}")
    running = 0
    for r in rows:
        running += r["count"]
        print(f"{r['rank']:>4}  {r['word']:<10} {r['count']:>10} {100 * r['count'] / total:>7.2f}% "
              f"{100 * running / total:>8.2f}%")

    # Для довідки: як концентровані оновлення в інших точках розподілу
    for n in (1, 10, 100, 1000):
        share = 100 * sum(c for c, _ in counts[:n]) / total
        print(f"Частка top-{n:<5} {share:6.2f}%")
    singles = sum(1 for c, _ in counts if c == 1)
    print(f"Слів, що трапляються один раз: {singles} ({100 * singles / len(counts):.1f}% словника)")
    print(f"\nРезультати: {out}")


if __name__ == "__main__":
    main()
