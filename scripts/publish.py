#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Публикация постов в Telegram-канал «НейроПрактик».

Читает config/.env (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID) или переменные окружения.

Usage:
    python3 scripts/publish.py content/posts/post.md            # опубликовать
    python3 scripts/publish.py content/posts/post.md --dry-run  # только показать
    python3 scripts/publish.py content/posts/post.md --ab       # A/B-варианты (маркер ### ВАРИАНТ B ###)
    python3 scripts/publish.py content/posts/post.md --photo cover.png  # с обложкой
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]

# Провайдеры могут блокировать часть IP Telegram — см. bot/telegram_net.py
sys.path.insert(0, str(BASE_DIR / "bot"))
from telegram_net import init_telegram_net  # noqa: E402

init_telegram_net()

SEND_MESSAGE = "https://api.telegram.org/bot{token}/sendMessage"
SEND_PHOTO = "https://api.telegram.org/bot{token}/sendPhoto"
LIMIT = 4096
MARKER = "### ВАРИАНТ B ###"


def load_env() -> dict:
    """Читает config/.env (переменные окружения имеют приоритет)."""
    data = {}
    env_file = BASE_DIR / "config" / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                data[k.strip()] = v.strip().strip('"').strip("'")
    return data


def call(token: str, method: str, **params) -> dict:
    payload = json.dumps(params).encode("utf-8")
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/{method}",
        data=payload, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def upload(token: str, method: str, chat_id: str, file_path: Path, caption: str) -> dict:
    """Загружает файл (multipart) — обложки, документы."""
    boundary = "----np-boundary"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="chat_id"\r\n\r\n{chat_id}\r\n'
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="caption"\r\n\r\n{caption}\r\n'
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="document"; filename="{file_path.name}"\r\n'
        f"Content-Type: application/octet-stream\r\n\r\n"
    ).encode("utf-8") + file_path.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/{method}",
        data=body, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST")
    with urllib.request.urlopen(req, timeout=300) as resp:
        return json.loads(resp.read().decode("utf-8"))


def strip_front_matter(text: str) -> str:
    """Убирает YAML front matter (--- ... ---) из начала файла."""
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            return parts[2].lstrip("\n")
    return text


def escape_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def clean_markdown(text: str) -> str:
    """Готовит текст к Telegram HTML: **жирный** -> <b>, *курсив* -> <i>."""
    text = escape_html(text)
    # Ссылки [текст](url) -> <a href>
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    # Заголовки md -> жирным
    text = re.sub(r"^#{1,6}\s+(.*)$", r"<b>\1</b>", text, flags=re.M)
    # Жирный
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    # Курсив (одиночные * после обработки парных)
    text = re.sub(r"\*([^*\n]+?)\*", r"<i>\1</i>", text)
    return text.strip()


def split_variants(text: str):
    """Делит пост на варианты A и B по маркеру."""
    if MARKER in text:
        a, b = text.split(MARKER, 1)
        return a.strip(), b.strip()
    return text.strip(), None


def split_long_text(text: str, limit: int = LIMIT) -> list:
    if len(text) <= limit:
        return [text]
    parts, cur = [], ""
    for para in text.split("\n\n"):
        candidate = (cur + "\n\n" + para).strip()
        if len(candidate) <= limit:
            cur = candidate
        else:
            if cur:
                parts.append(cur)
            while len(para) > limit:
                parts.append(para[:limit])
                para = para[limit:]
            cur = para
    if cur.strip():
        parts.append(cur)
    return parts


def send_text(token: str, chat_id: str, text: str, dry: bool = False) -> list:
    if dry:
        chunks = split_long_text(text)
        print(f"--- TEXTS (dry): {len(chunks)} часть(ей) ---")
        for i, chunk in enumerate(chunks, 1):
            print(f"[{i}/{len(chunks)}] {chunk[:100]}...")
        return []
    ids = []
    chunks = split_long_text(text)
    for i, chunk in enumerate(chunks, 1):
        res = call(token, "sendMessage", chat_id=chat_id, text=chunk, parse_mode="HTML")
        if not res.get("ok"):
            print(f"ОШИБКА: {res}", file=sys.stderr)
            sys.exit(1)
        ids.append(int(res["result"]["message_id"]))
        print(f"Отправлено: часть {i}/{len(chunks)}, {len(chunk)} символов")
    return ids


def send_photo(token: str, chat_id: str, photo: Path, caption: str, dry: bool = False):
    if dry:
        print(f"--- PHOTO (dry): {photo} (подпись {len(caption)} символов) ---")
        return None
    res = upload(token, "sendPhoto", chat_id, photo, caption)
    if not res.get("ok"):
        print(f"ОШИБКА отправки фото: {res}", file=sys.stderr)
        sys.exit(1)
    print(f"Обложка отправлена: {photo.name} (message_id={res['result']['message_id']})")
    return int(res["result"]["message_id"])


def main() -> None:
    ap = argparse.ArgumentParser(description="Публикация поста в Telegram")
    ap.add_argument("file", help="Путь к Markdown-файлу поста")
    ap.add_argument("--dry-run", action="store_true", help="показать без отправки")
    ap.add_argument("--ab", action="store_true", help="A/B: отправить вариант B отдельным сообщением")
    ap.add_argument("--photo", help="путь к обложке (PNG/JPG)")
    args = ap.parse_args()

    env = load_env()
    token = os.environ.get("TELEGRAM_BOT_TOKEN") or env.get("TELEGRAM_BOT_TOKEN", "")
    chat = os.environ.get("TELEGRAM_CHAT_ID") or env.get("TELEGRAM_CHAT_ID", "")

    path = Path(args.file)
    if not path.exists():
        print(f"Файл не найден: {path}", file=sys.stderr)
        sys.exit(1)

    raw = path.read_text(encoding="utf-8")
    text_a, text_b = split_variants(clean_markdown(strip_front_matter(raw)))

    if args.dry_run:
        send_text(token or "x", chat or "x", text_a, dry=True)
        if args.ab and text_b:
            send_text(token or "x", chat or "x", text_b, dry=True)
        return

    if not token or not chat:
        print("Не заданы TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID (config/.env)", file=sys.stderr)
        sys.exit(1)

    if args.photo:
        send_photo(token, chat, Path(args.photo), "")

    ids_a = send_text(token, chat, text_a)
    print(f"Пост опубликован: {path.name} (message_id={ids_a[-1] if ids_a else '-'})")

    if args.ab and text_b:
        time.sleep(1.5)
        ids_b = send_text(token, chat, text_b)
        print(f"Вариант B опубликован (message_id={ids_b[-1]})")


if __name__ == "__main__":
    main()
