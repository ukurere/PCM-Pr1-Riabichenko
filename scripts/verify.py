"""Перевірка коректності (виконується до вимірювань продуктивності).

Вихідні файли V2, V3 (усі K) і V4 (seq, tree) за всіх P мають побайтово
збігатися з результатом V0. V1 запускається для довідки: її результат
має відрізнятися. Звіт записується в results/verify.txt.

Запуск: python scripts/verify.py [--input data/corpus_en] [--threads 1,2,4,8]
Код завершення 1, якщо хоча б одна коректна версія не збіглася з V0."""

import argparse
import filecmp
import sys
import time
from pathlib import Path

from runner import INVIDX, ROOT, int_list, run_invidx


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--exe", default=str(INVIDX))
    ap.add_argument("--input", default=str(ROOT / "data" / "corpus_en"))
    ap.add_argument("--threads", default="1,2,4,8", help="кількості потоків через кому")
    ap.add_argument("--ks", default="1,4,16,64,256,1024,4096", help="значення K для V3")
    ap.add_argument("--out-dir", default=str(ROOT / "out" / "verify"))
    ap.add_argument("--report", default=str(ROOT / "results" / "verify.txt"))
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    threads = int_list(args.threads)
    ks = int_list(args.ks)

    configs = [("v2", p, None, None) for p in threads]
    configs += [("v3", p, k, None) for p in threads for k in ks]
    configs += [("v4", p, None, m) for p in threads for m in ("seq", "tree")]

    lines = []

    def log(s: str) -> None:
        print(s, flush=True)
        lines.append(s)

    log(f"Корпус: {args.input}")
    started = time.time()
    ref = out_dir / "v0.tsv"
    r0 = run_invidx(args.exe, "v0", 1, args.input, ref)
    ref_total = int(r0["total_occurrences"])
    log(f"V0: total_occurrences={ref_total}, файл {ref.stat().st_size} байтів")

    failures = 0
    for i, (mode, p, k, merge) in enumerate(configs, 1):
        out = out_dir / "candidate.tsv"
        r = run_invidx(args.exe, mode, p, args.input, out, k=k, merge=merge)
        same = filecmp.cmp(ref, out, shallow=False)
        failures += not same
        label = f"{mode.upper()} P={p}" + (f" K={k}" if k else "") + (f" merge={merge}" if merge else "")
        log(f"[{i:2d}/{len(configs)}] {label:<26} {'збігається' if same else 'НЕ ЗБІГАЄТЬСЯ'}"
            f"  (total_occurrences={r['total_occurrences']})")

    r1 = run_invidx(args.exe, "v1", max(threads), args.input, out_dir / "v1.tsv")
    v1_total = int(r1["total_occurrences"])
    v1_same = filecmp.cmp(ref, out_dir / "v1.tsv", shallow=False)
    log(f"V1 P={max(threads)} (довідково): total_occurrences={v1_total}, "
        f"втрачено {ref_total - v1_total}, файл {'збігається' if v1_same else 'відрізняється'} від V0")

    log(f"\nПеревірено конфігурацій: {len(configs)}, розбіжностей: {failures}, "
        f"час {time.time() - started:.0f} с")
    report = Path(args.report)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Звіт: {report}")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
