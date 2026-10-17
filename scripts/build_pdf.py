#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Генератор PDF из Markdown в бренд-стиле «НейроПрактик 2026».

Обложка в стиле баннера канала (тёмный фон + неон-маджента), цветные
заголовки, тёмные блоки кода, брендовые таблицы и подвал с ботом.

Usage:
    python3 scripts/build_pdf.py products/checklist.md pdf/Checklist.pdf
    python3 scripts/build_all.sh

Требует: fpdf2 (pip install fpdf2) и шрифты DejaVu.
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

# ── Бренд «НейроПрактик» (см. assets/brand/README.md) ────────────────────
BRAND_DARK = (13, 9, 22)        # #0d0916 — фон обложки / блоков кода
BRAND_CARD = (27, 20, 40)       # #1b1428 — карточки / вторичный фон
BRAND_HEADING = (164, 31, 196)  # #a41fc4 — заголовки
BRAND_LIGHT = (228, 77, 255)    # #e44dff — акцентный текст
BRAND_CYAN = (61, 219, 232)     # #3ddbe8 — второй акцент
INK = (23, 19, 15)              # основной текст
MUTED = (125, 118, 105)         # подписи / подвал
PAPER = (246, 244, 239)         # фон страницы
TAGLINE = "ИИ • Идеи • Практика • Результат"
BOT = "@neuropraktik_rubot"


class NPCoursePDF(FPDF):
    """FPDF с бренд-оформлением курса: обложка, шапка, подвал, блоки кода."""

    def header(self) -> None:
        if self.page_no() == 1:
            return  # обложка — без шапки
        self.set_draw_color(*BRAND_HEADING)
        self.set_line_width(0.7)
        self.line(self.l_margin, 10, self.w - self.r_margin, 10)
        self.set_font(SANS, size=8)
        self.set_text_color(*MUTED)
        self.set_xy(self.l_margin, 12)
        self.cell(0, 5, "НейроПрактик 2026", align="L")
        self.set_xy(self.w - self.r_margin - 70, 12)
        self.cell(70, 5, TAGLINE, align="R", new_x="LMARGIN", new_y="NEXT")
        self.set_y(19)

    def footer(self) -> None:
        self.set_y(-14)
        self.set_draw_color(*BRAND_HEADING)
        self.set_line_width(0.4)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.set_font(SANS, size=8)
        self.set_text_color(*MUTED)
        self.cell(
            0, 6,
            f"НейроПрактик 2026 • {BOT}  |  стр. {self.page_no()}",
            align="C",
        )

    # ── брендовые элементы ──────────────────────────────────────────

    def cover(self, title: str) -> None:
        """Рисует обложку в стиле баннера канала."""
        self.add_page()
        self.set_fill_color(*BRAND_DARK)
        self.rect(0, 0, self.w, self.h, "F")

        # акцентная линия маджента
        self.set_draw_color(*BRAND_HEADING)
        self.set_line_width(2.2)
        self.line(40, 95, self.w - 40, 95)

        self.set_font(SANS, "", 25)
        self.set_text_color(255, 255, 255)
        self.set_xy(40, 125)
        self.multi_cell(self.w - 80, 13, title, align="C")

        self.set_font(SANS, "B", 14)
        self.set_text_color(*BRAND_LIGHT)
        self.set_y(self.get_y() + 10)
        self.cell(0, 8, TAGLINE, align="C", new_x="LMARGIN", new_y="NEXT")

        self.set_draw_color(*BRAND_HEADING)
        self.set_line_width(0.8)
        self.line(40, self.get_y() + 5, self.w - 40, self.get_y() + 5)
        self.set_y(self.get_y() + 14)

        self.set_font(SANS, "", 10)
        self.set_text_color(180, 170, 200)
        self.cell(0, 6, f"Бот курса: {BOT}", align="C", new_x="LMARGIN", new_y="NEXT")
        self.cell(0, 6, "PDF-продукт курса «НейроПрактик 2026»", align="C")

    def h1(self, text: str) -> None:
        self.ln(2)
        self.set_font(SANS, "B", 17)
        self.set_text_color(*BRAND_HEADING)
        self.multi_cell(0, 8.5, text, new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(*BRAND_HEADING)
        self.set_line_width(1.1)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(5)
        self.set_text_color(*INK)
        self.set_font(SANS, "", 11)

    def h2(self, text: str) -> None:
        self.ln(1)
        self.set_font(SANS, "B", 13.5)
        self.set_text_color(*BRAND_HEADING)
        self.multi_cell(0, 7, text, new_x="LMARGIN", new_y="NEXT")
        self.ln(2)
        self.set_text_color(*INK)
        self.set_font(SANS, "", 11)

    def h3(self, text: str) -> None:
        self.ln(1)
        self.set_font(SANS, "B", 11.5)
        self.set_text_color(*BRAND_LIGHT)
        self.multi_cell(0, 6.5, text, new_x="LMARGIN", new_y="NEXT")
        self.ln(1)
        self.set_text_color(*INK)
        self.set_font(SANS, "", 11)

    def body(self, text: str) -> None:
        self.set_font(SANS, "", 11)
        self.set_text_color(*INK)
        self.multi_cell(0, 5.5, fit_tokens(self, clean_inline(text), self.epw),
                        new_x="LMARGIN", new_y="NEXT", markdown=True)

    def code_block(self, lines: list[str]) -> None:
        """Тёмный блок кода с маджентовой рамкой."""
        line_h = 4.6
        pad = 3
        h = len(lines) * line_h + pad * 2 + 2
        x = self.l_margin
        y = self.get_y()
        w = self.epw
        # фон + рамка
        self.set_fill_color(*BRAND_CARD)
        self.rect(x, y, w, h, "F")
        self.set_draw_color(*BRAND_HEADING)
        self.set_line_width(0.6)
        self.rect(x, y, w, h, "D")
        # текст
        self.set_font(MONO, "", 8.5)
        self.set_text_color(226, 224, 236)
        self.set_xy(x + pad, y + pad)
        for ln in lines:
            self.multi_cell(w - pad * 2, line_h,
                            fit_tokens(self, ln, w - pad * 2 - 4),
                            new_x="LMARGIN", new_y="NEXT")
        self.set_y(y + h + 3)
        self.set_text_color(*INK)
        self.set_font(SANS, "", 11)

    def blockquote(self, text: str) -> None:
        """Цитата с левым бордюром бренда."""
        line_h = 5.2
        # оценочная высота (приблизительно)
        est_lines = max(1, len(text) // 95 + 1)
        h = est_lines * line_h + 6
        x = self.l_margin
        y = self.get_y()
        w = self.epw
        self.set_fill_color(248, 243, 252)  # светло-фиолетовый фон
        self.rect(x, y, w, h, "F")
        self.set_draw_color(*BRAND_HEADING)
        self.set_line_width(2.5)
        self.line(x, y, x, y + h)
        self.set_font(SANS, "", 10.5)
        self.set_text_color(*INK)
        self.set_xy(x + 7, y + 3)
        self.multi_cell(w - 14, line_h, fit_tokens(self, clean_inline(text), w - 14 - 7),
                        new_x="LMARGIN", new_y="NEXT", markdown=True)
        self.set_y(y + h + 3)
        self.set_text_color(*INK)

    def table_row(self, cells: list[str], is_header: bool = False, line_h: float = 5) -> None:
        """Одна строка таблицы; первая строка — брендная шапка."""
        n = len(cells)
        col_w = self.epw / n
        y = self.get_y()
        # высота строки по самой длинной ячейке (приблизительно)
        max_lines = 1
        for cell in cells:
            est = max(1, len(cell) // int(col_w - 4) + 1)
            max_lines = max(max_lines, est)
        h = max_lines * line_h + 2

        if is_header:
            self.set_fill_color(*BRAND_DARK)
        else:
            self.set_fill_color(255, 255, 255)
        self.rect(self.l_margin, y, self.epw, h, "F")

        self.set_draw_color(200, 192, 180)
        self.set_line_width(0.3)
        for i, cell in enumerate(cells):
            x = self.l_margin + i * col_w
            self.rect(x, y, col_w, h, "D")
            self.set_xy(x + 2, y + 1)
            if is_header:
                self.set_font(SANS, "B", 8.5)
                self.set_text_color(*BRAND_LIGHT)
            else:
                self.set_font(SANS, "", 9)
                self.set_text_color(*INK)
            self.multi_cell(col_w - 4, line_h,
                            fit_tokens(self, clean_inline(cell), col_w - 4 - 2),
                            new_x="LMARGIN", new_y="NEXT")
        self.set_y(y + h + 1.5)
        self.set_text_color(*INK)
        self.set_font(SANS, "", 11)


def find_font_file(name: str) -> str | None:
    for d in FONT_SEARCH_DIRS:
        candidate = Path(d) / name
        if candidate.exists():
            return str(candidate)
    return None


def register_fonts(pdf: FPDF) -> None:
    for family, style, filename in FONTS:
        path = find_font_file(filename)
        if path is None:
            print(f"Шрифт не найден: {filename} (искали в {FONT_SEARCH_DIRS})",
                  file=sys.stderr)
            sys.exit(1)
        pdf.add_font(family, style, path)


def fit_tokens(pdf: FPDF, text: str, max_w: float) -> str:
    """Вставляет разрывы в слишком длинные токены, чтобы перенос не ломался."""
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
    """Готовит строку к markdown-рендеру fpdf2."""
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 (\2)", text)
    text = re.sub(r"^[-*]\s+", "• ", text)
    return text


def is_separator(line: str) -> bool:
    return bool(re.fullmatch(r"[-*_]{3,}", line.strip()))


def build_pdf(md_path: str, out_path: str) -> None:
    md_file = Path(md_path)
    if not md_file.exists():
        print(f"Файл не найден: {md_file}", file=sys.stderr)
        sys.exit(1)

    raw_lines = Path(md_path).read_text(encoding="utf-8").splitlines()

    pdf = NPCoursePDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    register_fonts(pdf)

    # ── обложка по первому # ────────────────────────────────────────
    cover_title = None
    body_start = 0
    for i, raw in enumerate(raw_lines):
        line = raw.strip()
        if line.startswith("# "):
            cover_title = line[2:].strip()
            body_start = i + 1
            break
    if cover_title:
        pdf.cover(cover_title)
    else:
        pdf.add_page()

    # ── тело документа ──────────────────────────────────────────────
    in_code = False
    code_buf: list[str] = []
    table_buf: list[list[str]] = []
    in_table = False

    def flush_code() -> None:
        nonlocal code_buf, in_code
        if code_buf:
            pdf.code_block(code_buf)
            code_buf = []
            in_code = False

    def flush_table() -> None:
        nonlocal table_buf, in_table
        if table_buf:
            for idx, row in enumerate(table_buf):
                pdf.table_row(row, is_header=(idx == 0))
            table_buf = []
            in_table = False

    for raw in raw_lines[body_start:]:
        line = raw.strip()

        if line.startswith("```"):
            flush_table()
            if not in_code:
                in_code = True
                code_buf = []
            else:
                flush_code()
            continue

        if in_code:
            code_buf.append(raw)
            continue

        if line.startswith("|"):
            flush_code()
            cells = [c.strip() for c in line.strip("|").split("|")]
            if all(set(c) <= set("-: ") for c in cells):
                continue  # разделитель |---|---|
            table_buf.append(cells)
            in_table = True
            continue

        flush_table()

        if not line or is_separator(line):
            pdf.ln(5)
            continue

        if line.startswith("# "):
            pdf.h1(line[2:].strip())
        elif line.startswith("## "):
            pdf.h2(line[3:].strip())
        elif line.startswith("### "):
            pdf.h3(line[4:].strip())
        elif line.startswith("> "):
            pdf.blockquote(line[2:].strip())
        else:
            pdf.body(line)

    flush_code()
    flush_table()

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(out))
    print(f"PDF сохранён: {out}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Сборка PDF из Markdown в бренд-стиле")
    ap.add_argument("input", help="Путь к Markdown-файлу")
    ap.add_argument("output", help="Путь к выходному PDF")
    args = ap.parse_args()
    build_pdf(args.input, args.output)


if __name__ == "__main__":
    main()
