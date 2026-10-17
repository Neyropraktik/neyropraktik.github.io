#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Telegram-бот продаж курса «НейроПрактик 2026».

Возможности:
  /start      — приветствие и меню
  /catalog    — 4 тарифа курса с ценами
  /buy        — выбор тарифа и оплаты (Telegram Stars или перевод)
  /faq        — частые вопросы
  /orders     — история заказов (только для админа)

Оплата Stars (XTR): нативные платежи Telegram, без внешних провайдеров.
Fallback — перевод с реквизитами (PAYMENT_MANUAL_TEXT в config/.env).
После успешной оплаты бот выдаёт доступ: ссылка на лендинг + программа.

Запуск:  python3 bot/tg_bot.py
Останов: Ctrl+C (offset сохраняется в bot/state.json — дубли не прилетят)
"""

import http.client
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from telegram_net import init_telegram_net, refresh_telegram_ip

BASE_DIR = Path(__file__).resolve().parents[1]
ORDERS_FILE = BASE_DIR / "bot" / "orders.json"
STATE_FILE = BASE_DIR / "bot" / "state.json"

# ── Тарифы курса ─────────────────────────────────────────────────────────────
# stars — цена в звёздах Telegram (целое число). 1 звезда ≈ 2 ₽ на стороне
# пользователя; скорректируй под свой курс. Курс меняется — правила простые:
# цена в рублях из README курса, звёзды подбирай так, чтобы сумма была ≈ той же.
TIERS = [
    {
        "id": "basic",
        "title": "Базовый",
        "price_rub": 1490,
        "stars": 950,
        "desc": "PDF-гайд по нейросетям + 4 пакета промптов",
        "features": ["PDF-гайд по нейросетям", "4 пакета промптов", "Пожизненный доступ"],
    },
    {
        "id": "standard",
        "title": "Стандарт",
        "price_rub": 3900,
        "stars": 2500,
        "desc": "Всё из «Базового» + 5 модулей курса",
        "features": ["Всё из «Базового»", "5 модулей курса", "Уроки, задания, тесты", "Финальный проект"],
        "popular": True,
    },
    {
        "id": "premium",
        "title": "Премиум",
        "price_rub": 7900,
        "stars": 5000,
        "desc": "Всё из «Стандарта» + проверка заданий автором",
        "features": ["Всё из «Стандарта»", "Проверка заданий автором", "Ответ в течение 48 часов"],
    },
    {
        "id": "vip",
        "title": "VIP",
        "price_rub": 19900,
        "stars": 12500,
        "desc": "Всё из «Премиума» + 2 созвона 1-на-1",
        "features": ["Всё из «Премиума»", "2 созвона 1-на-1 (60 мин)", "Личный разбор проекта"],
    },
]

FAQ = [
    ("Нужен ли опыт?", "Нет. Модуль 1 объясняет базу с нуля: что такое нейросеть, почему она «врёт» и как выбрать модель."),
    ("Сколько времени?", "Около 3 часов 15 минут на уроки плюс задания. Урок читается за 8–12 минут, дедлайнов нет."),
    ("Как получить доступ?", "Сразу после оплаты бот присылает ссылку на лендинг со всеми уроками и материалами."),
    ("Что если устареет?", "Разделы с моделями и ценами проверяются раз в месяц. Обновления приходят всем купившим."),
    ("Вернёте деньги?", "Да, в течение 14 дней после покупки — напишите в поддержку, вернём полную сумму."),
]

def new_order_id() -> str:
    """Уникальный номер заказа: NP-<мсек>."""
    return f"NP-{int(time.time() * 1000) % 10_000_000}"


def manager_username(env: dict) -> str:
    """Личный аккаунт менеджера (без @) — сюда ведут кнопки связи."""
    return env.get("MANAGER_USERNAME", "").strip().lstrip("@")


def manager_url(env: dict) -> str:
    """Ссылка на личку менеджера; если не задан — на канал курса."""
    name = manager_username(env)
    if name:
        return f"https://t.me/{name}"
    channel = env.get("TELEGRAM_CHANNEL_USERNAME", "")
    return f"https://t.me/{channel}" if channel else "https://t.me/neuropraktik_ru"


def manager_mention(env: dict) -> str:
    """Упоминание менеджера для текстов: @username или слово «менеджеру»."""
    name = manager_username(env)
    return f"@{name}" if name else "менеджеру"


def menu_keyboard(env: dict) -> dict:
    """Главное меню бота. Если задан BOOSTY_URL — добавляется кнопка канала."""
    buttons = [
        [{"text": "🛒 Купить курс", "callback_data": "catalog"}],
        [{"text": "🆓 Бесплатный чек-лист", "callback_data": "checklist"}],
        [{"text": "📚 Программа", "callback_data": "program"},
         {"text": "❓ Вопросы", "callback_data": "faq"}],
        [{"text": "✍️ Написать менеджеру", "url": manager_url(env)}],
    ]
    boosty = env.get("BOOSTY_URL", "")
    if boosty.startswith("http"):
        buttons.append([{"text": "💜 Boosty — посты и разборы", "url": boosty}])
    return {"inline_keyboard": buttons}

# PDF-материалы, которые бот прикрепляет
CHECKLIST_PDF = BASE_DIR / "pdf" / "NeyroPraktik-Checklist-10-shagov.pdf"
TIER_PDFS = {
    "basic": [
        BASE_DIR / "pdf" / "NeyroPraktik-Guide-2026.pdf",
        BASE_DIR / "pdf" / "Prompts-HR.pdf",
        BASE_DIR / "pdf" / "Prompts-Marketing.pdf",
        BASE_DIR / "pdf" / "Prompts-Jobseeker.pdf",
    ],
}
# Стандарт и выше получают тот же набор материалов + доступ к курсу на сайте
for _t in ("standard", "premium", "vip"):
    TIER_PDFS[_t] = TIER_PDFS["basic"]


# ── Конфиг и хранилище ───────────────────────────────────────────────────────

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


def load_json(path: Path, default):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return default
    return default


def save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ── Telegram API ─────────────────────────────────────────────────────────────

def call(token: str, method: str, **params) -> dict:
    payload = json.dumps(params).encode("utf-8")
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/{method}",
        data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=70) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        print(f"API error {method}: {e.code} {body}", file=sys.stderr)
        return {"ok": False, "error_code": e.code, "description": body}
    except (urllib.error.URLError, http.client.HTTPException, OSError) as e:
        print(f"Network error {method}: {e}", file=sys.stderr)
        return {"ok": False, "network_error": True}


# ── Тексты ───────────────────────────────────────────────────────────────────

def tier_card(t: dict) -> str:
    flag = " 🔥 <b>Выбирают</b>" if t.get("popular") else ""
    features = "\n".join(f"• {f}" for f in t["features"])
    return (
        f"<b>{t['title']}{flag}</b>\n"
        f"{t['desc']}\n\n"
        f"{features}\n\n"
        f"<b>{t['price_rub']:,} ₽</b> разово · ~{t['stars']:,} ⭐".replace(",", " ")
    )


def catalog_text() -> str:
    return (
        "<b>Курс «НейроПрактик 2026»</b>\n"
        "ИИ • Идеи • Практика • Результат\n"
        "5 модулей · 17 уроков · 9 заданий · 5 тестов · финальный проект\n\n"
        "Выберите тариф — после оплаты бот сразу пришлёт доступ:"
    )


def program_text() -> str:
    return (
        "<b>Программа курса</b>\n\n"
        "<b>1. База</b> — как работают нейросети, модели и цены, выбор модели (3 урока)\n"
        "<b>2. Формула промпта</b> — 5 шагов, роль, референс, факт-чек (4 урока)\n"
        "<b>3. Промпты под профессии</b> — HR, маркетинг, соискатели (4 урока)\n"
        "<b>4. Автоматизация</b> — контент-завод, расписания, безопасность (3 урока)\n"
        "<b>5. Монетизация</b> — воронка, упаковка, B2B (3 урока + финальный проект)\n\n"
        "Полная программа и первые уроки — на лендинге."
    )


def payment_choice_text(t: dict) -> str:
    return (
        f"<b>Тариф «{t['title']}» — {t['price_rub']:,} ₽</b>\n\n"
        "Выберите способ оплаты:".replace(",", " ")
    )


def access_text(t: dict, course_url: str) -> str:
    link = course_url if course_url.startswith("http") else "ссылка будет отправлена отдельно"
    return (
        f"<b>Оплата получена. Тариф «{t['title']}» активирован ✅</b>\n\n"
        f"Ваш доступ: {link}\n\n"
        "<b>Что внутри:</b>\n"
        "• Все 5 модулей и 17 уроков\n"
        "• Задания с критериями готовности\n"
        "• Тесты с ответами\n"
        "• PDF-гайд и пакеты промптов\n\n"
        "Если что-то не открывается — напишите менеджеру, поможем."
    )


# ── Обработчики ──────────────────────────────────────────────────────────────

def upload(token: str, method: str, chat_id, file_path: Path, caption: str = "") -> dict:
    """Отправляет документ (multipart)."""
    if not file_path.exists():
        print(f"Файл не найден: {file_path}", file=sys.stderr)
        return {"ok": False}
    boundary = "----npbot-boundary"
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
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"Upload error: {e.code} {e.read().decode('utf-8', 'replace')}", file=sys.stderr)
        return {"ok": False}


def send(token: str, chat_id, text: str, keyboard: dict | None = None) -> dict:
    params = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if keyboard:
        params["reply_markup"] = keyboard
    return call(token, "sendMessage", **params)


def send_welcome(token: str, env: dict, chat_id) -> None:
    text = (
        "<b>НейроПрактик 2026</b> — курс от промпта до автоматизации.\n"
        "ИИ • Идеи • Практика • Результат\n\n"
        "5 модулей, 17 уроков, 9 заданий, 5 тестов и финальный проект. "
        "Без вебинаров — учитесь в своём темпе.\n\n"
        "Выберите действие:"
    )
    send(token, chat_id, text, menu_keyboard(env))


def send_checklist(token: str, chat_id, env: dict) -> None:
    """Бесплатный чек-лист: текст + PDF-файл."""
    send(token, chat_id,
         "<b>Чек-лист «10 шагов к идеальному промпту»</b>\n\n"
         "Пришлю PDF. Внутри: 10 пунктов проверки, шаблон промпта на один экран "
         "и разбор до/после. Распечатайте и держите рядом с рабочим местом.")
    if CHECKLIST_PDF.exists():
        res = upload(token, "sendDocument", chat_id, CHECKLIST_PDF)
        if not res.get("ok"):
            send(token, chat_id,
                 f"Не смог отправить файл. Напишите {manager_mention(env)} — пришлём вручную.")
    else:
        send(token, chat_id, f"PDF временно недоступен — напишите {manager_mention(env)}.")


def send_catalog(token: str, chat_id) -> None:
    keyboard = {"inline_keyboard": []}
    for t in TIERS:
        label = f"{'🔥 ' if t.get('popular') else ''}{t['title']} — {t['price_rub']:,} ₽".replace(",", " ")
        keyboard["inline_keyboard"].append([{"text": label, "callback_data": f"tier:{t['id']}"}])
    keyboard["inline_keyboard"].append([{"text": "❓ Вопросы", "callback_data": "faq"}])
    send(token, chat_id, catalog_text(), keyboard)


def send_payment_choice(token: str, chat_id, tier_id: str) -> None:
    tier = next((t for t in TIERS if t["id"] == tier_id), None)
    if not tier:
        return
    keyboard = {"inline_keyboard": [
        [{"text": f"⭐ Telegram Stars ({tier['stars']:,})".replace(",", " "),
          "callback_data": f"pay_stars:{tier_id}"}],
        [{"text": "💳 Переводом", "callback_data": f"pay_manual:{tier_id}"}],
        [{"text": "‹ Назад к тарифам", "callback_data": "catalog"}],
    ]}
    send(token, chat_id, payment_choice_text(tier), keyboard)


def send_stars_invoice(token: str, env: dict, chat_id, tier_id: str) -> None:
    tier = next((t for t in TIERS if t["id"] == tier_id), None)
    if not tier:
        return
    res = call(
        token, "sendInvoice",
        chat_id=chat_id,
        title=f"Курс «НейроПрактик 2026» — {tier['title']}",
        description=tier["desc"],
        payload=f"course:{tier['id']}",
        currency="XTR",
        prices=[{"label": tier["title"], "amount": tier["stars"]}],
    )
    if not res.get("ok"):
        send(token, chat_id,
             "Не удалось создать счёт. Напишите менеджеру — оформим доступ вручную.",
             {"inline_keyboard": [[{"text": "✍️ Написать менеджеру", "url": manager_url(env)}]]})


def start_manual_payment(token: str, env: dict, chat_id, tier_id: str) -> None:
    tier = next((t for t in TIERS if t["id"] == tier_id), None)
    if not tier:
        return
    orders = load_json(ORDERS_FILE, [])
    order = {
        "order_id": new_order_id(),
        "chat_id": chat_id,
        "tier": tier["id"],
        "amount_rub": tier["price_rub"],
        "status": "waiting_payment",
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    orders.append(order)
    save_json(ORDERS_FILE, orders)
    manual_text = env.get("PAYMENT_MANUAL_TEXT", "Оплата переводом: напишите менеджеру — пришлём реквизиты.")
    keyboard = {"inline_keyboard": [
        [{"text": "✍️ Написать менеджеру", "url": manager_url(env)}],
    ]}
    send(token, chat_id,
         f"<b>Заказ {order['order_id']}</b>\nТариф «{tier['title']}» — {order['amount_rub']:,} ₽\n\n"
         f"{manual_text}\n\n"
         "После оплаты пришлите сюда скриншот чека — доступ откроем вручную.".replace(",", " "),
         keyboard)
    admin = env.get("ADMIN_CHAT_ID")
    if admin:
        send(token, admin,
             f"🧾 Новый заказ {order['order_id']}\n"
             f"Тариф: {tier['title']} ({order['amount_rub']:,} ₽)\n"
             f"Покупатель: chat_id={chat_id}\n"
             "Статус: ожидает оплаты переводом".replace(",", " "))


def deliver(token: str, env: dict, chat_id, tier_id: str, charge_id: str = "") -> None:
    tier = next((t for t in TIERS if t["id"] == tier_id), TIERS[0])
    course_url = env.get("COURSE_URL", "")
    send(token, chat_id, access_text(tier, course_url), menu_keyboard(env))
    for pdf in TIER_PDFS.get(tier_id, []):
        upload(token, "sendDocument", chat_id, pdf)
    send(token, chat_id,
         "Файлы материалов прикреплены выше. Курс и бонусы — по ссылке доступа. "
         "Если что-то не открылось, напишите менеджеру.")
    orders = load_json(ORDERS_FILE, [])
    orders.append({
        "order_id": new_order_id(),
        "chat_id": chat_id,
        "tier": tier["id"],
        "amount_rub": tier["price_rub"],
        "amount_stars": tier["stars"],
        "status": "paid",
        "charge_id": charge_id,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    })
    save_json(ORDERS_FILE, orders)
    admin = env.get("ADMIN_CHAT_ID")
    if admin:
        send(token, admin,
             f"✅ Оплата Stars\nТариф: {tier['title']} ({tier['price_rub']:,} ₽ / {tier['stars']:,} ⭐)\n"
             f"Покупатель: chat_id={chat_id}\ncharge_id: {charge_id}".replace(",", " "))


def send_faq(token: str, env: dict, chat_id) -> None:
    text = "<b>Частые вопросы</b>\n\n" + "\n\n".join(f"<b>{q}</b>\n{a}" for q, a in FAQ)
    text += "\n\nОстались вопросы — напишите менеджеру."
    send(token, chat_id, text, menu_keyboard(env))


def send_program(token: str, env: dict, chat_id) -> None:
    text = program_text()
    url = env.get("COURSE_URL", "")
    if url.startswith("http"):
        text += f"\n\n{url}"
    send(token, chat_id, text, menu_keyboard(env))


def send_orders(token: str, env: dict, chat_id) -> None:
    admin = env.get("ADMIN_CHAT_ID")
    if not admin or str(chat_id) != str(admin):
        send(token, chat_id, "Команда доступна только администратору.")
        return
    orders = load_json(ORDERS_FILE, [])
    if not orders:
        send(token, chat_id, "Заказов пока нет.")
        return
    lines = [f"<b>Заказы ({len(orders)})</b>"]
    for o in orders[-20:]:
        lines.append(
            f"• {o['order_id']} · {o['tier']} · {o.get('amount_rub', '—')} ₽ · {o['status']} · "
            f"chat {o.get('chat_id')}"
        )
    send(token, chat_id, "\n".join(lines))


def handle_update(env: dict, update: dict) -> None:
    token = env["TELEGRAM_BOT_TOKEN"]

    # Оплата Stars
    message = update.get("message") or {}
    if message.get("successful_payment"):
        sp = message["successful_payment"]
        payload = sp.get("invoice_payload", "")
        chat_id = message["chat"]["id"]
        if payload.startswith("course:"):
            deliver(token, env, chat_id, payload.split(":", 1)[1],
                    charge_id=sp.get("telegram_payment_charge_id", ""))
        return

    # Предчековые проверки
    pre = update.get("pre_checkout_query")
    if pre:
        call(token, "answerPreCheckoutQuery",
             pre_checkout_query_id=pre["id"], ok=True)
        return

    # Нажатия на кнопки
    cb = update.get("callback_query")
    if cb:
        chat_id = cb["message"]["chat"]["id"]
        data = cb.get("data", "")
        call(token, "answerCallbackQuery", callback_query_id=cb["id"])
        if data == "catalog":
            send_catalog(token, chat_id)
        elif data == "checklist":
            send_checklist(token, chat_id, env)
        elif data == "program":
            send_program(token, env, chat_id)
        elif data == "faq":
            send_faq(token, env, chat_id)
        elif data.startswith("tier:"):
            send_payment_choice(token, chat_id, data.split(":", 1)[1])
        elif data.startswith("pay_stars:"):
            send_stars_invoice(token, env, chat_id, data.split(":", 1)[1])
        elif data.startswith("pay_manual:"):
            start_manual_payment(token, env, chat_id, data.split(":", 1)[1])
        return

    # Команды и текст
    text = (message.get("text") or "").strip()
    chat_id = (message.get("chat") or {}).get("id")
    if not chat_id:
        return
    parts = text.split()
    cmd = parts[0].split("@", 1)[0] if parts else ""
    payload = parts[1].lower() if len(parts) > 1 else ""
    if cmd in ("/start", "/menu"):
        # Диплинки с лендинга: ?start=checklist, ?start=buy, ?start=buy_standard…
        if payload == "checklist":
            send_checklist(token, chat_id, env)
        elif payload in ("buy", "catalog", "course"):
            send_catalog(token, chat_id)
        elif payload.startswith("buy_"):
            send_payment_choice(token, chat_id, payload[4:])
        elif payload == "program":
            send_program(token, env, chat_id)
        elif payload == "faq":
            send_faq(token, env, chat_id)
        else:
            send_welcome(token, env, chat_id)
    elif cmd in ("/catalog", "/buy"):
        send_catalog(token, chat_id)
    elif cmd == "/checklist":
        send_checklist(token, chat_id, env)
    elif cmd == "/program":
        send_program(token, env, chat_id)
    elif cmd == "/faq":
        send_faq(token, env, chat_id)
    elif cmd == "/orders":
        send_orders(token, env, chat_id)
    elif text:
        send(token, chat_id,
             "Нажмите /start — открою меню курса: тарифы, программа, вопросы.",
             menu_keyboard(env))


def main() -> None:
    env = load_env()
    if not env.get("TELEGRAM_BOT_TOKEN"):
        print("Не задан TELEGRAM_BOT_TOKEN (config/.env)", file=sys.stderr)
        sys.exit(1)

    init_telegram_net()

    me = call(env["TELEGRAM_BOT_TOKEN"], "getMe")
    if not me.get("ok"):
        # Возможно, маршрут через системный DNS не работает — переподбор
        new_ip = refresh_telegram_ip()
        if new_ip:
            print(f"Повторная попытка через IP {new_ip}", file=sys.stderr)
            me = call(env["TELEGRAM_BOT_TOKEN"], "getMe")
    if not me.get("ok"):
        print("Не удалось подключиться к Bot API", file=sys.stderr)
        sys.exit(1)
    print(f"Бот @{me['result']['username']} запущен. Останов — Ctrl+C.")

    state = load_json(STATE_FILE, {"offset": 0})
    offset = state.get("offset", 0)
    net_fail_streak = 0
    while True:
        res = call(env["TELEGRAM_BOT_TOKEN"], "getUpdates",
                   offset=offset, timeout=50, allowed_updates=["message", "callback_query", "pre_checkout_query"])
        if not res.get("ok"):
            if res.get("network_error"):
                net_fail_streak += 1
                if net_fail_streak >= 3:
                    new_ip = refresh_telegram_ip()
                    if new_ip:
                        print(f"Сеть недоступна — переключаюсь на IP {new_ip}", file=sys.stderr)
                    net_fail_streak = 0
            time.sleep(3)
            continue
        net_fail_streak = 0
        for update in res.get("result", []):
            offset = update["update_id"] + 1
            try:
                handle_update(env, update)
            except Exception as e:  # одна ошибка не должна ронять цикл
                print(f"Handler error: {e}", file=sys.stderr)
        save_json(STATE_FILE, {"offset": offset})


if __name__ == "__main__":
    main()
