# Шрифты PDF-продуктов

Статические начертания (кириллица), используемые в `scripts/build_pdf.py`:

| Файл | Шрифт | Лицензия |
|------|-------|----------|
| `Unbounded-*.ttf` | Unbounded (заголовки) | SIL OFL 1.1 |
| `Inter-*.ttf` | Inter (текст) | SIL OFL 1.1 |
| `JetBrainsMono-*.ttf` | JetBrains Mono (промпты) | SIL OFL 1.1 |

Источники: `github.com/google/fonts` (Unbounded, Inter) и
`github.com/JetBrains/JetBrainsMono`. Вариативные оригиналы нарезаны в
статические начертания (Regular / SemiBold / Bold / ExtraBold) через
`fontTools.varLib.instancer`.
