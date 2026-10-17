#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Сборка PDF-продуктов «НейроПрактик 2026» из Markdown.

Дизайн: тёмная неоновая обложка в стиле сайта, аккуратные страницы с
колонтитулами, карточки промптов, брендовые таблицы, подвал с ботом.
Рендер: WeasyPrint (HTML + CSS) — типографика Unbounded / Inter / JetBrains
Mono (шрифты в assets/fonts, кириллица).

Установка зависимостей (один раз):
    python3 -m pip install --user --break-system-packages weasyprint markdown

Usage:
    python3 scripts/build_pdf.py products/checklist.md pdf/NeyroPraktik-Checklist-10-shagov.pdf
    bash scripts/build_all.sh
"""

import argparse
import html as html_lib
import re
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
FONT_DIR = BASE_DIR / "assets" / "fonts"
STYLE_FILE = Path(__file__).with_name("pdf_style.css")

try:
    import markdown as md_lib
except ImportError:
    print("Требуется пакет markdown: python3 -m pip install --user --break-system-packages markdown",
          file=sys.stderr)
    sys.exit(1)

try:
    import weasyprint
except ImportError:
    print("Требуется пакет weasyprint: python3 -m pip install --user --break-system-packages weasyprint",
          file=sys.stderr)
    sys.exit(1)

# ── Метаданные продуктов ─────────────────────────────────────────────────────
# Обложка: рубрика (kicker), чипы-факты и CSS-класс контента.

PRODUCTS = {
    "checklist.md": {
        "kicker": "Бесплатный чек-лист",
        "chips": ["10 шагов", "Проверка до отправки", "Распечатай и держи рядом"],
        "content_class": "doc-checklist",
    },
    "guide.md": {
        "kicker": "PDF-гайд курса",
        "chips": ["5 модулей", "17 уроков", "9 заданий", "5 тестов"],
        "content_class": "chapters doc-guide",
    },
    "prompts-hr.md": {
        "kicker": "Библиотека промптов · HR",
        "chips": ["10 шаблонов", "Найм и отбор", "Онбординг"],
        "content_class": "chapters doc-prompts",
    },
    "prompts-marketing.md": {
        "kicker": "Библиотека промптов · Маркетинг",
        "chips": ["10 шаблонов", "Контент и реклама", "Аналитика и A/B"],
        "content_class": "chapters doc-prompts",
    },
    "prompts-jobseeker.md": {
        "kicker": "Библиотека промптов · Поиск работы",
        "chips": ["10 шаблонов", "Резюме и письма", "Собеседования"],
        "content_class": "chapters doc-prompts",
    },
}
DEFAULT_META = {
    "kicker": "PDF-продукт курса",
    "chips": [],
    "content_class": "",
}

FONT_FILES = {
    "__FONT_UNBOUNDED_400__": "Unbounded-Regular.ttf",
    "__FONT_UNBOUNDED_600__": "Unbounded-SemiBold.ttf",
    "__FONT_UNBOUNDED_800__": "Unbounded-ExtraBold.ttf",
    "__FONT_INTER_400__": "Inter-Regular.ttf",
    "__FONT_INTER_600__": "Inter-SemiBold.ttf",
    "__FONT_INTER_700__": "Inter-Bold.ttf",
    "__FONT_MONO_400__": "JetBrainsMono-Regular.ttf",
    "__FONT_MONO_700__": "JetBrainsMono-Bold.ttf",
}

# ── Подготовка Markdown ──────────────────────────────────────────────────────

# Плейсхолдеры в промптах: [ДОЛЖНОСТЬ], [в скобках] и т.п. (2–44 символа)
PLACEHOLDER_RE = re.compile(r"\[([^\[\]<>{}]{2,44})\]")


def split_title_lead(md_text: str) -> tuple[str, str, str]:
    """Вынимает H1-заголовок и первый абзац — они станут обложкой."""
    lines = md_text.splitlines()
    title, idx = "", None
    for i, ln in enumerate(lines):
        if ln.startswith("# "):
            title, idx = ln[2:].strip(), i
            break
    if idx is None:
        return "", "", md_text

    i = idx + 1
    while i < len(lines) and not lines[i].strip():
        i += 1
    lead_parts = []
    while i < len(lines):
        s = lines[i].strip()
        if not s or s == "---" or s.startswith("#"):
            break
        lead_parts.append(s)
        i += 1
    lead = " ".join(lead_parts)
    rest = "\n".join(lines[i:]).lstrip("\n")
    return title, lead, rest


def convert_bullets(md_text: str) -> str:
    """Строки «• …» превращает в markdown-список (вне блоков кода)."""
    out, in_fence = [], False
    for line in md_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            out.append(line)
            continue
        if not in_fence and (stripped.startswith("• ") or stripped == "•"):
            item = "- " + stripped[2:].strip() if stripped.startswith("• ") else "-"
            if out and out[-1].strip() and not out[-1].strip().startswith(("- ", "* ")):
                out.append("")
            out.append(item)
        else:
            out.append(line)
    return "\n".join(out)


def wrap_placeholders(html: str) -> str:
    """Подсвечивает [ПОДСТАВКИ] внутри <code>-блоков циановым."""
    def repl(match: re.Match) -> str:
        inner = PLACEHOLDER_RE.sub(
            lambda g: f'<span class="ph">[{g.group(1)}]</span>', match.group(1))
        return f"<code>{inner}</code>"

    return re.sub(r"<code>(.*?)</code>", repl, html, flags=re.S)


def md_to_html(md_text: str, meta: dict) -> tuple[str, str, str]:
    """Markdown → (заголовок, лид, HTML-контент) в брендовом оформлении."""
    title, lead, rest = split_title_lead(md_text)
    content = md_lib.markdown(
        convert_bullets(rest),
        extensions=["tables", "fenced_code", "sane_lists"],
        output_format="html5",
    )
    # Таблица-чек-лист: [ ] / [x] → нарисованные галочки
    content = content.replace("<td>[ ]</td>", '<td><span class="cb"></span></td>')
    content = content.replace("<td>[x]</td>", '<td><span class="cb on"></span></td>')
    content = content.replace("<th>[x]</th>", "<th></th>")
    if "doc-checklist" in meta["content_class"]:
        content = content.replace(
            "<table>",
            '<table><colgroup><col style="width:7%"><col style="width:26%"><col></colgroup>',
            1,
        )
    content = wrap_placeholders(content)
    # Библиотеки промптов: номера шаблонов уходят в водяной знак страницы
    if "doc-prompts" in meta["content_class"]:
        content = re.sub(r"<h2>(\d+)\.\s*", "<h2>", content)
        content = content.replace(
            "</pre>",
            "</pre>\n<p class=\"prompt-note\">Замени [подстановки в скобках] "
            "своими данными — и отправь промпт в чат с нейросетью.</p>",
        )
    # Гайд: «Модуль N.» превращаем в крупный номер на странице модуля
    if "doc-guide" in meta["content_class"]:
        content = re.sub(
            r"<h2>Модуль (\d+)\.\s*(.+?)</h2>",
            lambda m: (f'<h2 class="module-h"><span class="modnum">'
                       f"{int(m.group(1)):02d}</span>{m.group(2)}</h2>"),
            content,
        )
    # Последний абзац «Бот курса: …» — аккуратная подпись в конце
    content = re.sub(r"<p>(<strong>Бот курса:.*?)</p>",
                     r'<p class="doc-end">\1</p>', content, flags=re.S)
    content = re.sub(r"<p>(Бот курса:.*?)</p>",
                     r'<p class="doc-end">\1</p>', content, flags=re.S)

    lead_html = md_lib.markdown(lead).strip()
    if lead_html.startswith("<p>") and lead_html.endswith("</p>"):
        lead_html = lead_html[3:-4]
    return title, lead_html, content


# ── Шаблон страницы ──────────────────────────────────────────────────────────

def cover_html(title: str, lead_html: str, meta: dict) -> str:
    n = len(title)
    size_class = "t-xl" if n <= 36 else ("t-l" if n <= 47 else "t-m")
    chips = "".join(f'<span class="pill">{html_lib.escape(c)}</span>'
                    for c in meta["chips"])
    return f"""
<section class="cover">
  <div class="glow-m"></div><div class="glow-c"></div><div class="dots"></div>
  <div class="streak"></div>
  <div class="year">2026</div>
  <div class="top">
    <span class="chip">НП</span><span class="brand">НейроПрактик</span>
    <span class="brand-sub">Курс о нейросетях — от промпта до автоматизации</span>
  </div>
  <div class="main">
    <div class="kicker">НейроПрактик 2026 · {html_lib.escape(meta["kicker"])}</div>
    <h1 class="{size_class}">{html_lib.escape(title)}</h1>
    <div class="lead">{lead_html}</div>
    <div class="pills">{chips}</div>
  </div>
  <div class="bottom">
    <div class="rule"></div>
    <div class="tagline">ИИ • Идеи • Практика • Результат</div>
    <div class="meta">Текстовый курс: 5 модулей · 17 уроков · 9 заданий · 5 тестов<br>
      Бот курса: @neuropraktik_rubot</div>
  </div>
</section>"""


def style_css() -> str:
    if not STYLE_FILE.exists():
        raise FileNotFoundError(f"Нет файла стилей: {STYLE_FILE}")
    css = STYLE_FILE.read_text(encoding="utf-8")
    for token, filename in FONT_FILES.items():
        font_path = FONT_DIR / filename
        if not font_path.exists():
            raise FileNotFoundError(
                f"Нет шрифта {font_path}. Шрифты лежат в assets/fonts.")
        css = css.replace(token, font_path.as_uri())
    return css


def build_pdf(md_path: str | Path, out_path: str | Path) -> None:
    md_file, out = Path(md_path), Path(out_path)
    if not md_file.exists():
        print(f"Нет входного файла: {md_file}", file=sys.stderr)
        sys.exit(1)

    meta = PRODUCTS.get(md_file.name, DEFAULT_META)
    title, lead_html, content = md_to_html(md_file.read_text(encoding="utf-8"), meta)

    doc = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<title>{html_lib.escape(title)}</title>
<style>{style_css()}</style>
</head>
<body class="{meta['content_class']}">
{cover_html(title, lead_html, meta)}
<main class="content">
{content}
</main>
</body>
</html>"""

    out.parent.mkdir(parents=True, exist_ok=True)
    rendered = weasyprint.HTML(string=doc, base_url=str(BASE_DIR)).render()
    rendered.write_pdf(str(out))
    print(f"PDF сохранён: {out} ({len(rendered.pages)} стр.)")


def main() -> None:
    ap = argparse.ArgumentParser(description="Сборка PDF из Markdown в бренд-стиле (WeasyPrint)")
    ap.add_argument("input", help="Путь к Markdown-файлу")
    ap.add_argument("output", help="Путь к выходному PDF")
    args = ap.parse_args()
    build_pdf(args.input, args.output)


if __name__ == "__main__":
    main()
