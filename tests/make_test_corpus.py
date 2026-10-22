"""Створює невеликий тестовий корпус tests/corpus із граничними випадками нормалізації:
кирилиця (Ї, Є, Ґ, І), апострофи, наголоси, BOM, CRLF, некоректний UTF-8,
німецька ß, грецька, емодзі, цифри, однакові кількості в doc2 і doc10."""

from pathlib import Path

OUT = Path(__file__).resolve().parent / "corpus"

TEXTS = [
    "Привіт, Світе! ПРИВІТ світе. Їжак, Єнот, Ґанок, Іній — ЇЖАК.",
    "The quick brown fox jumps over the lazy dog. THE DOG, the Fox.",
    "спільне спільне слово слово",                       # doc2: однакові кількості
    "п'ять п’ять пʼять м'ясо — апострофи різних видів",
    "Запа́м'ятати нагол́ос; ще раз: наголос.",              # комбінований наголос U+0301
    "Straße STRASSE Größe ÄRGER äRgEr",
    "Ελληνικά ΚΕΙΜΕΝΟ κείμενο Σίσυφος ΣΊΣΥΦΟΣ",
    "Числа 123 4567 2024рік abc123 12 ab a",
    "emoji 😀😀 тест🙂тест слово👍слово",
    "tabs\tand\r\nwindows\r\nline endings\r\n",
    "спільне спільне слово слово",                       # doc10: ті самі кількості, що й doc2
    "ПРИВІТ привіт Привіт",
]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for i, text in enumerate(TEXTS):
        (OUT / f"t{i:02d}.txt").write_bytes(text.encode("utf-8"))
    # BOM і некоректні послідовності UTF-8 (надлишкове кодування, сурогат, обрізаний символ)
    raw = ("﻿bom перевірка ".encode("utf-8")
           + b"abc\xc1\x81def ghi\xed\xa0\x80jkl mno\xe2\x82 \xffpqr "
           + "кінець".encode("utf-8") + b"\xd0")
    (OUT / f"t{len(TEXTS):02d}.txt").write_bytes(raw)
    print(f"{len(TEXTS) + 1} files in {OUT}")


if __name__ == "__main__":
    main()
