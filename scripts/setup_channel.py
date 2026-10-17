#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Настройка Telegram-канала «НейроПрактик» через Bot API.

Usage:
    python3 scripts/setup_channel.py --check                  # показать текущее состояние
    python3 scripts/setup_channel.py --apply                  # title/description/закреп
    python3 scripts/setup_channel.py --apply --avatar путь.png # установить аватар канала
    python3 scripts/setup_channel.py --apply --banner путь.jpg # опубликовать баннер в канал
"""

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
API = "https://api.telegram.org/bot{token}/{method}"

# Бренд см. assets/brand/README.md: неон-маджента, теглайн «ИИ • Идеи • Практика • Результат»
TITLE = "НейроПрактик | ИИ • Практика • Результат"
DESCRIPTION = (
    "НейроПрактик 2026 — текстовый курс: от промпта до автоматизации.\n"
    "ИИ • Идеи • Практика • Результат\n\n"
    "5 модулей, 17 уроков, 9 заданий и 5 тестов. Промпты, автоматизация, "
    "монетизация — без вебинаров, в своём темпе.\n\n"
    "Бот курса: @neuropraktik_rubot · программа и цены — в закрепе."
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


def upload_photo(token: str, method: str, chat: str, path: Path, caption: str = "") -> dict:
    """setChatPhoto / sendPhoto через multipart-загрузку файла."""
    field = "photo"
    filetype = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    boundary = "----npchannel-boundary"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="chat_id"\r\n\r\n{chat}\r\n'
    ).encode("utf-8")
    if caption:
        body += (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="caption"\r\n\r\n{caption}\r\n'
        ).encode("utf-8")
    body += (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{field}"; filename="{path.name}"\r\n'
        f"Content-Type: {filetype}\r\n\r\n"
    ).encode("utf-8") + path.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        API.format(token=token, method=method),
        data=body, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"⚠ Ошибка загрузки фото ({e.code}): {e.read().decode('utf-8', 'replace')}", file=sys.stderr)
        return {"ok": False}


def main() -> None:
    ap = argparse.ArgumentParser(description="Настройка канала через Bot API")
    ap.add_argument("--check", action="store_true", help="только показать состояние канала")
    ap.add_argument("--apply", action="store_true", help="применить настройки")
    ap.add_argument("--avatar", help="PNG-картинка для аватара канала (квадрат ≥512×512)")
    ap.add_argument("--banner", help="картинка баннера — опубликовать постом в канал")
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

    if args.banner:
        banner = BASE_DIR / args.banner if not Path(args.banner).exists() else Path(args.banner)
        if banner.exists():
            res = upload_photo(token, "sendPhoto", chat, banner,
                               caption="ИИ • Идеи • Практика • Результат\n\n"
                                       "Курс «НейроПрактик 2026» — бот курса: @neuropraktik_rubot")
            print("Баннер опубликован постом" if res.get("ok") else "Баннер не отправился")
        else:
            print(f"Баннер не найден: {banner}", file=sys.stderr)

    if args.avatar:
        avatar = BASE_DIR / args.avatar if not Path(args.avatar).exists() else Path(args.avatar)
        if avatar.exists():
            res = upload_photo(token, "setChatPhoto", chat, avatar)
            print("Аватар канала установлен" if res.get("ok") else "Аватар не установился")
        else:
            print(f"Аватар не найден: {avatar}", file=sys.stderr)

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
