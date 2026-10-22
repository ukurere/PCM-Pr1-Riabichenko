"""Спільні функції для запуску invidx і false_sharing зі скриптів."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXE_SUFFIX = ".exe" if sys.platform == "win32" else ""
INVIDX = ROOT / "build" / f"invidx{EXE_SUFFIX}"
FALSE_SHARING = ROOT / "build" / f"false_sharing{EXE_SUFFIX}"


def parse_kv(line: str) -> dict:
    """'a=1 b=2.5' -> {'a': '1', 'b': '2.5'}"""
    return dict(tok.split("=", 1) for tok in line.split() if "=" in tok)


def run_invidx(exe, mode, threads, input_dir, output, k=None, merge=None) -> dict:
    cmd = [str(exe), "--mode", mode, "--threads", str(threads),
           "--input", str(input_dir), "--output", str(output)]
    if k is not None:
        cmd += ["--k", str(k)]
    if merge is not None:
        cmd += ["--merge", merge]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)} failed ({res.returncode}): {res.stderr.strip()}")
    return parse_kv(res.stdout.strip().splitlines()[-1])


def run_false_sharing(exe, threads, pad, reps) -> list:
    cmd = [str(exe), "--threads", str(threads), "--pad", str(pad), "--reps", str(reps)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)} failed ({res.returncode}): {res.stderr.strip()}")
    return [parse_kv(line) for line in res.stdout.strip().splitlines()]


def int_list(s: str) -> list:
    return [int(x) for x in s.split(",") if x.strip()]
