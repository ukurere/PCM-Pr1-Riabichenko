"""V1: відтворюваність некоректного результату (п. 3.2 завдання).

Виконує --runs запусків V1 на однакових даних за однакової кількості потоків,
порівнює сумарну кількість входжень з еталонним значенням V0 і для кожного
запуску рахує, скільки слів мають неправильну загальну кількість.
Наприкінці — слова з найбільшими сумарними втратами (найчастотніші слова
оновлюються найчастіше, тому й суміщення операцій на них найімовірніше).

Результати: results/v1_runs.csv, results/v1_lost_words.csv, таблиця в stdout.

Запуск: python scripts/v1_runs.py [--threads 8] [--runs 10]"""

import argparse
import csv
import statistics
import sys
from collections import Counter
from pathlib import Path

from runner import INVIDX, ROOT, run_invidx


def read_totals(path: Path) -> dict:
    totals = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            word, total, _ = line.split("\t", 2)
            totals[word] = int(total)
    return totals


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--exe", default=str(INVIDX))
    ap.add_argument("--input", default=str(ROOT / "data" / "corpus_en"))
    ap.add_argument("--threads", type=int, default=8)
    ap.add_argument("--runs", type=int, default=10)
    ap.add_argument("--out", default=str(ROOT / "results" / "v1_runs.csv"))
    ap.add_argument("--words-out", default=str(ROOT / "results" / "v1_lost_words.csv"))
    ap.add_argument("--top", type=int, default=10, help="скільки слів із найбільшими втратами показати")
    args = ap.parse_args()

    work = ROOT / "out" / "v1"
    work.mkdir(parents=True, exist_ok=True)

    ref_path = work / "v0.tsv"
    r0 = run_invidx(args.exe, "v0", 1, args.input, ref_path)
    ref_total = int(r0["total_occurrences"])
    ref_words = read_totals(ref_path)
    print(f"V0 (еталон): total_occurrences = {ref_total}, слів = {len(ref_words)}\n")

    rows = []
    lost_by_word = Counter()
    for run in range(1, args.runs + 1):
        out_path = work / "v1.tsv"
        r = run_invidx(args.exe, "v1", args.threads, args.input, out_path)
        total = int(r["total_occurrences"])
        words = read_totals(out_path)
        affected = 0
        for w, t in words.items():
            if t != ref_words[w]:
                affected += 1
                lost_by_word[w] += ref_words[w] - t
        lost = ref_total - total
        rows.append({"run": run, "threads": args.threads, "total_occurrences": total,
                     "reference": ref_total, "lost": lost,
                     "lost_percent": round(100 * lost / ref_total, 4),
                     "words_affected": affected, "compute_ms": r["compute_ms"]})
        print(f"запуск {run:2d}: {total}  втрачено {lost:7d} ({100 * lost / ref_total:.3f}%), "
              f"слів із неправильною кількістю: {affected}", flush=True)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    lost = [r["lost"] for r in rows]
    totals = [r["total_occurrences"] for r in rows]
    print(f"\nP = {args.threads}, запусків: {args.runs}")
    print(f"Еталон V0:            {ref_total}")
    print(f"Отримано (мін – макс): {min(totals)} – {max(totals)}  (розкид {max(totals) - min(totals)})")
    print(f"Втрачено:             мін {min(lost)}, макс {max(lost)}, медіана {statistics.median(lost):.0f}, "
          f"середнє {statistics.mean(lost):.0f} ± {statistics.stdev(lost) if len(lost) > 1 else 0:.0f}")
    print(f"Різних результатів:   {len(set(totals))} з {args.runs}")

    sum_lost = sum(lost_by_word.values())
    with open(args.words_out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["word", "reference_total", "lost_all_runs", "share_of_lost_percent"])
        for word, l in lost_by_word.most_common():
            w.writerow([word, ref_words[word], l, round(100 * l / sum_lost, 4)])

    print(f"\nСлова з найбільшими втратами (сумарно за {args.runs} запусків):")
    for word, l in lost_by_word.most_common(args.top):
        print(f"  {word:<10} еталон {ref_words[word]:>9}  втрачено {l:>7}  ({100 * l / sum_lost:.1f}% усіх втрат)")
    print(f"\nРезультати: {out}, {args.words_out}")


if __name__ == "__main__":
    main()
