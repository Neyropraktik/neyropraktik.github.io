#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Настройка Telegram-канала «НейроПрактик» через Bot API.

Usage:
    python3 scripts/setup_channel.py --check     # показать текущее состояние
    python3 scripts/setup_channel.py --apply     # применить title/description/закреп
"""

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
API = "https://api.telegram.org/bot{token}/{method}"

TITLE = "НейроПрактик — курс про нейросети"
DESCRIPTION = (
    "Курс «НейроПрактик 2026»: 5 модулей, 17 уроков, 9 заданий и 5 тестов.\n"
    "Промпты, автоматизация, монетизация — теория → пример → разбор, без вебинаров.\n"
    "Программа, цены и уроки: ссылка на лендинг в закреплённом сообщении."
)
PINNED_FILE = BASE_DIR / "content" / "pinned-course.md"


def load_env() -> dict:
    env_file = BASE_DIR / "config" / ".env"
    data = {}
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                data[k.strip()] = v.strip().strip('"').strip("'")
    return data


def call(token: str, method: str, soft: bool = False, **params) -> dict:
    payload = json.dumps(params).encode("utf-8")
    req = urllib.request.Request(
        API.format(token=token, method=method), data=payload,
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        if soft:
            print(f"⚠ Ошибка Telegram API ({method}): {e.code} {body}", file=sys.stderr)
            return {"ok": False}
        print(f"Ошибка Telegram API ({method}): {e.code} {body}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    ap = argparse.ArgumentParser(description="Настройка канала через Bot API")
    ap.add_argument("--check", action="store_true", help="только показать состояние канала")
    ap.add_argument("--apply", action="store_true", help="применить настройки")
    args = ap.parse_args()

    env = load_env()
    token = os.environ.get("TELEGRAM_BOT_TOKEN") or env.get("TELEGRAM_BOT_TOKEN", "")
    chat = os.environ.get("TELEGRAM_CHAT_ID") or env.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat:
        print("Не заданы TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID (config/.env)", file=sys.stderr)
        sys.exit(1)

    me = call(token, "getMe")
    print(f"Бот: @{me['result']['username']}")

    info = call(token, "getChat", chat_id=chat)["result"]
    print(f"Канал: {info.get('title')} (@{info.get('username')})")
    print(f"Описание: {(info.get('description') or '(пусто)')[:200]}")

    if args.check:
        return

    call(token, "setChatTitle", soft=True, chat_id=chat, title=TITLE)
    print(f"Имя канала: {TITLE}")

    res = call(token, "setChatDescription", soft=True, chat_id=chat, description=DESCRIPTION)
    print("Описание обновлено" if res.get("ok") else "Описание уже актуально")

    if not PINNED_FILE.exists():
        print(f"Нет файла закрепа: {PINNED_FILE}", file=sys.stderr)
        sys.exit(1)

    text = PINNED_FILE.read_text(encoding="utf-8").strip()
    sent = call(token, "sendMessage", chat_id=chat, text=text, parse_mode="HTML")
    msg_id = sent["result"]["message_id"]
    call(token, "pinChatMessage", chat_id=chat, message_id=msg_id, disable_notification=True)
    print(f"Закреплён приветственный пост (message_id={msg_id})")
    print("Готово.")


if __name__ == "__main__":
    main()
