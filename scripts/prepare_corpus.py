"""Підготовка корпусу з дампу Вікіпедії (англійської або української).

Читає *wiki-*-pages-articles*.xml.bz2 потоково (без розпакування на диск),
бере статті основного простору імен (без перенаправлень), прибирає вікі-розмітку
і розкладає текст у файли ~1 МБ (межі файлів — між статтями), доки загальний
обсяг не досягне --target-mb. Наприкінці друкує опис корпусу для звіту.

Запуск: python scripts/prepare_corpus.py --dump data/enwiki-latest-pages-articles1.xml-p1p41242.bz2
        --dst data/corpus_en --prefix en
"""

import argparse
import bz2
import html
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

RE_COMMENT = re.compile(r"<!--.*?-->", re.S)
RE_REF = re.compile(r"<ref[^>/]*?/>|<ref[^>]*?>.*?</ref>", re.S | re.I)
RE_NOWIKI_BLOCKS = re.compile(r"<(math|gallery|syntaxhighlight|source|pre|score|timeline)[^>]*>.*?</\1>", re.S | re.I)
RE_TEMPLATE = re.compile(r"\{\{[^{}]*\}\}")
RE_TABLE = re.compile(r"\{\|[^{}]*?\|\}", re.S)
RE_FILE_LINK = re.compile(r"\[\[(?:Файл|Зображення|File|Image|Категорія|Category|Медіа|Media):[^\[\]]*(?:\[\[[^\[\]]*\]\][^\[\]]*)*\]\]", re.I)
RE_INTERWIKI = re.compile(r"\[\[[a-z\-]{2,12}:[^\[\]]*\]\]")
RE_LINK_PIPED = re.compile(r"\[\[[^\[\]|]*\|([^\[\]]*)\]\]")
RE_LINK = re.compile(r"\[\[([^\[\]]*)\]\]")
RE_EXT_LINK = re.compile(r"\[(?:https?:)?//[^\s\]]+\s*([^\]]*)\]")
RE_URL = re.compile(r"https?://\S+")
RE_TAG = re.compile(r"</?[a-zA-Z][^>]*>")
RE_BOLD_ITALIC = re.compile(r"'{2,}")
RE_HEADING = re.compile(r"^=+\s*(.*?)\s*=+\s*$", re.M)
RE_LIST_MARK = re.compile(r"^[*#:;]+\s*", re.M)
RE_MAGIC = re.compile(r"__[A-ZА-ЯІЇЄҐ_]+__")
RE_BLANK = re.compile(r"\n{3,}")


def strip_nested(pattern: re.Pattern, text: str) -> str:
    """Прибирає вкладені конструкції, починаючи з найглибших."""
    while True:
        new = pattern.sub("", text)
        if new == text:
            return text
        text = new


def clean_wikitext(text: str) -> str:
    text = RE_COMMENT.sub("", text)
    text = RE_NOWIKI_BLOCKS.sub("", text)
    text = RE_REF.sub("", text)
    text = strip_nested(RE_TEMPLATE, text)
    text = strip_nested(RE_TABLE, text)
    text = RE_FILE_LINK.sub("", text)
    text = RE_INTERWIKI.sub("", text)
    text = RE_LINK_PIPED.sub(r"\1", text)
    text = RE_LINK.sub(r"\1", text)
    text = RE_EXT_LINK.sub(r"\1", text)
    text = RE_URL.sub("", text)
    text = html.unescape(text)
    text = RE_TAG.sub("", text)
    text = RE_BOLD_ITALIC.sub("", text)
    text = RE_HEADING.sub(r"\1", text)
    text = RE_LIST_MARK.sub("", text)
    text = RE_MAGIC.sub("", text)
    text = RE_BLANK.sub("\n\n", text)
    return text.strip()


def iter_articles(dump: Path):
    """Повертає (заголовок, вікітекст) статей основного простору імен."""
    with bz2.open(dump, "rb") as f:
        ns_tag = None
        try:
            for _, elem in ET.iterparse(f, events=("end",)):
                tag = elem.tag.rsplit("}", 1)[-1]
                if tag != "page":
                    continue
                if ns_tag is None:
                    ns_tag = elem.tag[: -len("page")]
                ns = elem.findtext(f"{ns_tag}ns")
                redirect = elem.find(f"{ns_tag}redirect")
                title = elem.findtext(f"{ns_tag}title") or ""
                text = elem.findtext(f"{ns_tag}revision/{ns_tag}text") or ""
                elem.clear()
                if ns == "0" and redirect is None and text:
                    yield title, text
        except (EOFError, ET.ParseError) as e:
            print(f"warning: dump ended early ({type(e).__name__}: {e})")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dump", required=True, help="файл ukwiki-*-pages-articles*.xml.bz2")
    ap.add_argument("--dst", default="data/corpus", help="цільовий каталог корпусу")
    ap.add_argument("--prefix", default="doc", help="префікс імен файлів (ASCII), напр. en або uk")
    ap.add_argument("--target-mb", type=float, default=220, help="загальний обсяг корпусу, МБ")
    ap.add_argument("--file-mb", type=float, default=1.0, help="приблизний розмір одного файлу, МБ")
    ap.add_argument("--min-article-chars", type=int, default=500, help="коротші статті пропускаються")
    args = ap.parse_args()

    dst = Path(args.dst)
    dst.mkdir(parents=True, exist_ok=True)
    for old in dst.glob(f"{args.prefix}_*.txt"):
        old.unlink()

    target = int(args.target_mb * 1024 * 1024)
    file_size = int(args.file_mb * 1024 * 1024)
    total = 0
    articles = 0
    n_files = 0
    buf = []
    buf_size = 0

    def flush():
        nonlocal n_files, buf, buf_size, total
        if not buf:
            return
        data = "\n\n".join(buf).encode("utf-8")
        (dst / f"{args.prefix}_{n_files:04d}.txt").write_bytes(data)
        n_files += 1
        total += len(data)
        buf, buf_size = [], 0

    for title, wikitext in iter_articles(Path(args.dump)):
        body = clean_wikitext(wikitext)
        if len(body) < args.min_article_chars:
            continue
        article = f"{title}\n\n{body}"
        buf.append(article)
        buf_size += len(article.encode("utf-8"))
        articles += 1
        if buf_size >= file_size:
            flush()
            if total >= target:
                break
            if n_files % 20 == 0:
                print(f"{n_files} files, {total / 2**20:.0f} MB, {articles} articles")
    flush()

    mb = total / 2**20
    print(f"\nCorpus: {dst}")
    print(f"  files:    {n_files}")
    print(f"  size:     {mb:.1f} MB ({total} bytes)")
    print(f"  articles: {articles}")
    if n_files < 200 or mb < 200:
        print("  WARNING: вимога — не менше 200 файлів і 200 МБ")


if __name__ == "__main__":
    main()
