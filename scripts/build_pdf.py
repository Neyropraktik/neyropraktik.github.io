#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Генератор PDF из Markdown (рендерер с таблицами, жирным, кодом; требует fpdf2 + DejaVu).

Usage:
    python3 scripts/build_pdf.py products/checklist.md pdf/Checklist.pdf
    python3 scripts/build_all.sh

Требует: fpdf2 (pip install fpdf2) и шрифты DejaVu (обычно есть в системе)
"""

import argparse
import re
import sys
from pathlib import Path

try:
    from fpdf import FPDF
except ImportError:
    print("Требуется fpdf2: pip install fpdf2", file=sys.stderr)
    sys.exit(1)

BASE_DIR = Path(__file__).resolve().parents[1]

FONT_SEARCH_DIRS = [
    "/usr/share/fonts/truetype/dejavu",
    "/usr/share/fonts/dejavu",
    "/usr/share/fonts/TTF",
    Path.home() / ".fonts",
]

FONTS = [
    ("DejaVu Sans", "", "DejaVuSans.ttf"),
    ("DejaVu Sans", "B", "DejaVuSans-Bold.ttf"),
    ("DejaVu Sans Mono", "", "DejaVuSansMono.ttf"),
    ("DejaVu Sans Mono", "B", "DejaVuSansMono-Bold.ttf"),
]

SANS = "DejaVu Sans"
MONO = "DejaVu Sans Mono"


def find_font_file(name: str):
    for d in FONT_SEARCH_DIRS:
        candidate = Path(d) / name
        if candidate.exists():
            return str(candidate)
    return None


def register_fonts(pdf: FPDF) -> None:
    for family, style, filename in FONTS:
        path = find_font_file(filename)
        if path is None:
            print(f"Шрифт не найден: {filename} (искали в {FONT_SEARCH_DIRS})", file=sys.stderr)
            sys.exit(1)
        pdf.add_font(family, style, path)


def fit_tokens(pdf: FPDF, text: str, max_w: float) -> str:
    """Вставляет пробелы в токены длиннее max_w, чтобы перенос не падал."""
    words = text.split(" ")
    out = []
    for word in words:
        if not word or pdf.get_string_width(word) <= max_w:
            out.append(word)
            continue
        chunk = ""
        for ch in word:
            if chunk and pdf.get_string_width(chunk + ch) > max_w:
                out.append(chunk)
                chunk = ch
            else:
                chunk += ch
        if chunk:
            out.append(chunk)
    return " ".join(out)


def clean_inline(text: str) -> str:
    """Готовит строку к markdown-рендеру fpdf2: ссылки -> 'текст (url)', буллеты -> '•'."""
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 (\2)", text)
    text = re.sub(r"^[-*]\s+", "• ", text)
    return text


def is_separator(line: str) -> bool:
    return bool(re.fullmatch(r"[-*_]{3,}", line.strip()))


def render_cell(pdf: FPDF, cell: str, x: float, y: float, col_w: float, line_h: float) -> float:
    """Рисует одну ячейку таблицы в своей колонке, возвращает y после ячейки."""
    pdf.set_xy(x, y)
    pdf.multi_cell(col_w, line_h, fit_tokens(pdf, clean_inline(cell), col_w - 1),
                   border=1, markdown=True)
    return pdf.get_y()


def build_pdf(md_path: str, out_path: str) -> None:
    md_file = Path(md_path)
    if not md_file.exists():
        print(f"Файл не найден: {md_file}", file=sys.stderr)
        sys.exit(1)

    text = md_file.read_text(encoding="utf-8")
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    register_fonts(pdf)

    full_w = pdf.w - pdf.l_margin - pdf.r_margin
    pdf.set_font(SANS, size=12)
    in_code = False

    for raw_line in text.splitlines():
        line = raw_line.strip()

        if line.startswith("```"):
            in_code = not in_code
            pdf.set_font(MONO if in_code else SANS, size=9 if in_code else 11)
            continue

        if in_code:
            pdf.set_xy(pdf.l_margin, pdf.get_y())
            pdf.multi_cell(0, 4.5, fit_tokens(pdf, line, full_w), new_x="LMARGIN")
            continue

        if not line or is_separator(line):
            pdf.ln(5)
            continue

        if line.startswith("# "):
            pdf.set_font(SANS, size=18, style="B")
            pdf.multi_cell(0, 8, fit_tokens(pdf, line[2:].strip(), full_w),
                           align="C", new_x="LMARGIN")
            pdf.ln(3)
            pdf.set_font(SANS, size=12)

        elif line.startswith("## "):
            pdf.set_font(SANS, size=14, style="B")
            pdf.multi_cell(0, 7, fit_tokens(pdf, line[3:].strip(), full_w), new_x="LMARGIN")
            pdf.ln(2)
            pdf.set_font(SANS, size=12)

        elif line.startswith("### "):
            pdf.set_font(SANS, size=12, style="B")
            pdf.multi_cell(0, 6, fit_tokens(pdf, line[4:].strip(), full_w), new_x="LMARGIN")

        elif line.startswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if all(set(c) <= set("-: ") for c in cells):
                continue  # разделитель |---|---|
            col_w = full_w / len(cells)
            y_row_start = pdf.get_y()
            max_y = y_row_start
            for i, cell in enumerate(cells):
                x = pdf.l_margin + i * col_w
                y_after = render_cell(pdf, cell, x, y_row_start, col_w, 5)
                max_y = max(max_y, y_after)
            pdf.set_xy(pdf.l_margin, max_y)
            pdf.ln(2)

        else:
            pdf.set_font(SANS, size=11)
            pdf.multi_cell(0, 5.5, fit_tokens(pdf, clean_inline(line), full_w),
                           new_x="LMARGIN", markdown=True)

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(out))
    print(f"PDF сохранён: {out}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Сборка PDF из Markdown")
    ap.add_argument("input", help="Путь к Markdown-файлу")
    ap.add_argument("output", help="Путь к выходному PDF")
    args = ap.parse_args()
    build_pdf(args.input, args.output)


if __name__ == "__main__":
    main()
