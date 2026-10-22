"""Генерує src/common/unicode_tables.h — таблиці для нормалізації тексту.

  isAlnum(cp)  — літера (категорія Unicode L*) або десяткова цифра (Nd);
  toLower(cp)  — простий переклад у нижній регістр: str.lower(), якщо результат
                 є одним символом, інакше символ лишається без змін.

Таблиці двоступеневі (блоки по 256 кодових точок, однакові блоки зберігаються один раз).
Ті самі правила реалізовано в scripts/reference_index.py.

Запуск: python scripts/gen_unicode_tables.py
"""

import sys
import unicodedata
from pathlib import Path

MAX_CP = 0x110000
BLOCK = 256
OUT = Path(__file__).resolve().parent.parent / "src" / "common" / "unicode_tables.h"


def is_alnum(c: str) -> bool:
    cat = unicodedata.category(c)
    return cat[0] == "L" or cat == "Nd"


def to_lower(c: str) -> str:
    low = c.lower()
    return low if len(low) == 1 else c


def dedupe(blocks):
    unique, index, seen = [], [], {}
    for b in blocks:
        key = tuple(b)
        if key not in seen:
            seen[key] = len(unique)
            unique.append(key)
        index.append(seen[key])
    return unique, index


def main() -> None:
    alnum_blocks, delta_blocks = [], []
    for start in range(0, MAX_CP, BLOCK):
        bits = [0] * (BLOCK // 32)
        deltas = []
        for cp in range(start, start + BLOCK):
            c = chr(cp)
            if is_alnum(c):
                bits[(cp - start) >> 5] |= 1 << ((cp - start) & 31)
            deltas.append(ord(to_lower(c)) - cp)
        alnum_blocks.append(bits)
        delta_blocks.append(deltas)

    alnum_unique, alnum_index = dedupe(alnum_blocks)
    delta_unique, delta_index = dedupe(delta_blocks)

    def rows(values, per_line):
        return ",\n    ".join(", ".join(str(v) for v in values[i:i + per_line])
                              for i in range(0, len(values), per_line))

    lines = [
        "// ЗГЕНЕРОВАНО scripts/gen_unicode_tables.py — не редагувати вручну.",
        f"// Unicode {unicodedata.unidata_version} (Python {sys.version.split()[0]}).",
        "#pragma once",
        "",
        "#include <cstdint>",
        "",
        "namespace uni {",
        "",
        f"inline constexpr uint32_t kMaxCodePoint = 0x{MAX_CP:X};",
        "",
        f"inline constexpr uint16_t kAlnumIndex[{len(alnum_index)}] = {{",
        "    " + rows(alnum_index, 24),
        "};",
        "",
        f"inline constexpr uint32_t kAlnumBits[{len(alnum_unique)}][{BLOCK // 32}] = {{",
        ",\n".join("    {" + ", ".join(f"0x{v:08X}u" for v in b) + "}" for b in alnum_unique),
        "};",
        "",
        f"inline constexpr uint16_t kLowerIndex[{len(delta_index)}] = {{",
        "    " + rows(delta_index, 24),
        "};",
        "",
        f"inline constexpr int32_t kLowerDelta[{len(delta_unique)}][{BLOCK}] = {{",
        ",\n".join("    {" + ", ".join(str(v) for v in b) + "}" for b in delta_unique),
        "};",
        "",
        "inline bool isAlnum(uint32_t cp) {",
        "    if (cp >= kMaxCodePoint) return false;",
        "    const uint32_t lo = cp & 0xFF;",
        "    return (kAlnumBits[kAlnumIndex[cp >> 8]][lo >> 5] >> (lo & 31)) & 1u;",
        "}",
        "",
        "inline uint32_t toLower(uint32_t cp) {",
        "    if (cp >= kMaxCodePoint) return cp;",
        "    return static_cast<uint32_t>(static_cast<int32_t>(cp) + kLowerDelta[kLowerIndex[cp >> 8]][cp & 0xFF]);",
        "}",
        "",
        "}  // namespace uni",
        "",
    ]
    OUT.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print(f"{OUT}: {len(alnum_unique)} alnum blocks, {len(delta_unique)} lowercase blocks")


if __name__ == "__main__":
    main()
