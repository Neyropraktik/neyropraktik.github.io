#!/usr/bin/env bash
# Сборка всех PDF-продуктов курса в pdf/
set -e

cd "$(dirname "$0")/.."
OUT_DIR="pdf"
mkdir -p "$OUT_DIR"

echo "> checklist"
python3 scripts/build_pdf.py products/checklist.md "$OUT_DIR/NeyroPraktik-Checklist-10-shagov.pdf"

echo "> guide"
python3 scripts/build_pdf.py products/guide.md "$OUT_DIR/NeyroPraktik-Guide-2026.pdf"

echo "> prompts-hr"
python3 scripts/build_pdf.py products/prompts-hr.md "$OUT_DIR/Prompts-HR.pdf"

echo "> prompts-marketing"
python3 scripts/build_pdf.py products/prompts-marketing.md "$OUT_DIR/Prompts-Marketing.pdf"

echo "> prompts-jobseeker"
python3 scripts/build_pdf.py products/prompts-jobseeker.md "$OUT_DIR/Prompts-Jobseeker.pdf"

echo ""
echo "Готово. Продукты в $OUT_DIR/"
ls -lh "$OUT_DIR"
