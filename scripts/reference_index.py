"""Незалежна (повільна) реалізація побудови індексу на Python за тими самими
правилами. Використовується лише для перевірки V0 на невеликому корпусі.

Запуск: python scripts/reference_index.py --input tests/corpus --output out/ref.tsv"""

import argparse
import unicodedata
from collections import defaultdict
from pathlib import Path

MIN_TOKEN_LENGTH = 3


def is_alnum(c: str) -> bool:
    cat = unicodedata.category(c)
    return cat[0] == "L" or cat == "Nd"


def to_lower(c: str) -> str:
    low = c.lower()
    return low if len(low) == 1 else c


def tokens(text: str):
    cur = []
    for c in text:
        if is_alnum(c):
            cur.append(to_lower(c))
        else:
            if len(cur) >= MIN_TOKEN_LENGTH:
                yield "".join(cur)
            cur = []
    if len(cur) >= MIN_TOKEN_LENGTH:
        yield "".join(cur)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    files = sorted((p for p in Path(args.input).iterdir() if p.is_file()), key=lambda p: p.name.encode())
    index = defaultdict(lambda: defaultdict(int))
    for doc, path in enumerate(files):
        text = path.read_bytes().decode("utf-8", errors="replace")
        for w in tokens(text):
            index[w][doc] += 1

    with open(args.output, "wb") as out:
        for word in sorted(index, key=lambda w: w.encode("utf-8")):
            per_doc = index[word]
            total = sum(per_doc.values())
            items = sorted(per_doc.items(), key=lambda kv: (-kv[1], kv[0]))
            postings = ",".join(f"doc{d}:{c}" for d, c in items)
            out.write(f"{word}\t{total}\t{postings}\n".encode("utf-8"))


if __name__ == "__main__":
    main()
