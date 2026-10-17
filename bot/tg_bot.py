#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Telegram-бот продаж курса «НейроПрактик 2026».

Возможности:
  /start      — приветствие и меню
  /catalog    — 4 тарифа курса с ценами
  /buy        — выбор тарифа и оплаты (Telegram Stars или перевод)
  /faq        — частые вопросы
  /orders     — история заказов (только для админа)
  /grant      — (админ) выдать доступ по номеру заказа: /grant NP-1234567

Перевод: покупатель оформляет заказ и присылает чек в бот — админу приходит
чек с кнопками «выдать доступ» / «не подтверждаю». Кнопка выдаёт материалы
и ссылку-доступ покупателю. Запасной путь — команда /grant.

Оплата Stars (XTR): нативные платежи Telegram, без внешних провайдеров.
Fallback — перевод с реквизитами (PAYMENT_MANUAL_TEXT в config/.env).
После оплаты бот присылает PDF-материалы и открывает доступ к урокам:
ссылка с кодом (COURSE_ACCESS_KEY из config/.env) открывает модули 2–5
на сайте курса. Программа и модуль 1 «База» — бесплатны для всех.

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
USERS_FILE = BASE_DIR / "bot" / "users.json"

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
        "desc": "PDF-гайд по нейросетям + 4 пакета промптов (95 шаблонов)",
        "features": ["PDF-гайд по нейросетям", "4 пакета промптов — 95 шаблонов", "Пожизненный доступ"],
    },
    {
        "id": "standard",
        "title": "Стандарт",
        "price_rub": 3900,
        "stars": 2500,
        "desc": "Всё из «Базового» + доступ к модулям 2–5 на сайте",
        "features": ["Всё из «Базового»", "Модули 2–5 на сайте", "Задания, тесты, финальный проект"],
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
    ("Нужен ли опыт?", "Нет. Модуль 1 объясняет базу с нуля: что такое нейросеть, почему она «врёт» и как выбрать модель. Модуль 1 открыт бесплатно для всех."),
    ("Сколько времени?", "Около 3 часов 15 минут на уроки плюс задания. Урок читается за 8–12 минут, дедлайнов нет."),
    ("Что приходит после оплаты?", "PDF-материалы (гайд и 4 пакета промптов) и доступ к урокам: модули 2–5 на сайте, задания, тесты и финальный проект. Программа и модуль 1 доступны всем без покупки."),
    ("Как открыть модули 2–5?", "После оплаты бот присылает ссылку-доступ — открывается в один клик. Запасной способ: код из бота можно ввести вручную в форме «Уже купили?» на странице курса."),
    ("Что если устареет?", "Разделы с моделями и ценами проверяются раз в месяц. Обновления открываются всем купившим автоматически."),
    ("Вернёте деньги?", "Возврат не предусмотрен: материалы цифровые и выдаются сразу после оплаты. Чтобы не ошибиться — сначала посмотрите программу, пройдите бесплатный модуль 1 и чек-лист, задайте вопросы менеджеру."),
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


def course_site_url(env: dict, path: str = "kurs/") -> str:
    """Ссылка на страницу сайта курса (пусто, если COURSE_URL не задан)."""
    base = env.get("COURSE_URL", "").rstrip("/")
    return f"{base}/{path}" if base.startswith("http") else ""


def access_link(env: dict) -> str:
    """Персональная ссылка-доступ: открывает модули 2–5 сразу (?k=…)."""
    key = env.get("COURSE_ACCESS_KEY", "").strip()
    site = course_site_url(env)
    return f"{site}?k={key}" if key and site else ""


def menu_keyboard(env: dict) -> dict:
    """Главное меню бота. Если задан BOOSTY_URL — добавляется кнопка канала."""
    buttons = [
        [{"text": "🛒 Купить курс", "callback_data": "catalog"}],
        [{"text": "🆓 Бесплатный чек-лист", "callback_data": "checklist"}],
    ]
    site = course_site_url(env)
    if site:
        buttons.append([{"text": "🎓 Программа и уроки", "url": site}])
    buttons += [
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
        BASE_DIR / "pdf" / "Prompts-Universal.pdf",
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
        "Выберите тариф — после оплаты бот сразу пришлёт материалы и доступ к урокам:"
    )


def program_text() -> str:
    return (
        "<b>Программа курса</b>\n\n"
        "<b>1. База</b> — как работают нейросети, модели и цены, выбор модели (3 урока)\n"
        "<b>2. Формула промпта</b> — 5 шагов, роль, референс, факт-чек (4 урока)\n"
        "<b>3. Промпты под профессии</b> — HR, маркетинг, соискатели (4 урока)\n"
        "<b>4. Автоматизация</b> — контент-завод, расписания, безопасность (3 урока)\n"
        "<b>5. Монетизация</b> — воронка, упаковка, B2B (3 урока + финальный проект)\n\n"
        "Полная программа открыта на сайте. Модуль 1 «База» можно пройти бесплатно — остальные открываются после покупки."
    )


def payment_choice_text(t: dict) -> str:
    return (
        f"<b>Тариф «{t['title']}» — {t['price_rub']:,} ₽</b>\n\n"
        "Выберите способ оплаты:".replace(",", " ")
    )


def access_text(t: dict, env: dict) -> str:
    link = access_link(env)
    key = env.get("COURSE_ACCESS_KEY", "").strip()
    parts = [
        f"<b>Доступ к курсу открыт — тариф «{t['title']}» ✅</b>",
        "",
    ]
    if link:
        parts += [
            "Ваша ссылка (сохраните её):",
            link,
            "",
            "Она открывает модули 2–5 на любом устройстве — телефон, компьютер, планшет.",
            f"Если понадобится ввести код вручную (форма «Уже купили?» на сайте): <code>{key}</code>",
        ]
    else:
        parts += ["Ссылка-доступ придёт отдельным сообщением. Если её нет — напишите менеджеру."]
    parts += [
        "",
        "<b>Что внутри доступа:</b>",
        "• Модули 2–5: уроки, задания с критериями, тесты",
        "• Финальный проект «Моя ИИ-воронка за 7 дней»",
        "",
        "Ссылка персональная — пожалуйста, не пересылайте её. Вопросы — менеджеру, поможем.",
    ]
    return "\n".join(parts)


def basic_access_text(env: dict) -> str:
    mod1 = course_site_url(env, "kurs/modul-1.html")
    text = ("<b>Материалы готовы</b> — файлы пришли выше, сохраните их.\n\n"
            "Бонус: модуль 1 «База» открыт бесплатно для всех")
    text += f":\n{mod1}" if mod1 else "."
    text += ("\n\nХотите пройти курс целиком? Модули 2–5, задания, тесты и финальный проект "
             "открываются на тарифе «Стандарт» — нажмите «🛒 Купить курс» в меню.")
    return text


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
        "Без вебинаров — учитесь в своём темпе. Модуль 1 открыт бесплатно.\n\n"
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


def start_manual_payment(token: str, env: dict, chat_id, tier_id: str,
                         user: dict | None = None) -> None:
    tier = next((t for t in TIERS if t["id"] == tier_id), None)
    if not tier:
        return
    user = user or {}
    orders = load_json(ORDERS_FILE, [])
    order = {
        "order_id": new_order_id(),
        "chat_id": chat_id,
        "tier": tier["id"],
        "amount_rub": tier["price_rub"],
        "status": "waiting_payment",
        "username": user.get("username", ""),
        "name": " ".join(x for x in (user.get("first_name"), user.get("last_name")) if x),
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    orders.append(order)
    save_json(ORDERS_FILE, orders)
    manual_text = env.get("PAYMENT_MANUAL_TEXT", "Оплата переводом: напишите менеджеру — пришлём реквизиты.")
    price = f"{order['amount_rub']:,}".replace(",", " ")
    keyboard = {"inline_keyboard": [
        [{"text": "✍️ Написать менеджеру", "url": manager_url(env)}],
    ]}
    send(token, chat_id,
         f"<b>Заказ {order['order_id']}</b>\nТариф «{tier['title']}» — {price} ₽\n\n"
         f"{manual_text}\n\n"
         "<b>Как получить доступ:</b>\n"
         "1. Переведите оплату по реквизитам (в комментарии к переводу можно указать номер заказа).\n"
         "2. Вернитесь в этот чат и отправьте фото или скриншот чека.\n"
         "3. Проверю оплату и открою доступ — файлы и ссылка на уроки придут сюда же.\n\n"
         "Чек можно прислать и менеджеру, но быстрее всего — прямо сюда.",
         keyboard)
    admin = env.get("ADMIN_CHAT_ID")
    if admin:
        who = f"@{order['username']}" if order["username"] else (order["name"] or "без имени")
        send(token, admin,
             f"🧾 Новый заказ {order['order_id']}\n"
             f"Тариф: {tier['title']} ({price} ₽)\n"
             f"Покупатель: {who} · chat_id={chat_id}\n"
             "Статус: ждём оплату переводом. Когда пришлёт чек — придёт кнопка «выдать доступ».")


def deliver(token: str, env: dict, chat_id, tier_id: str, charge_id: str = "",
            existing_order_id: str = "") -> None:
    tier = next((t for t in TIERS if t["id"] == tier_id), TIERS[0])
    send(token, chat_id,
         f"<b>Оплата получена — тариф «{tier['title']}» активирован ✅</b>\n\n"
         "Сейчас пришлю материалы: файлы придут следующими сообщениями, "
         "а после них — доступ к урокам.")
    for pdf in TIER_PDFS.get(tier_id, []):
        upload(token, "sendDocument", chat_id, pdf)
    if tier_id == "basic":
        send(token, chat_id, basic_access_text(env), menu_keyboard(env))
    else:
        link = access_link(env)
        if link:
            send(token, chat_id, access_text(tier, env), {"inline_keyboard": [
                [{"text": "🚀 Открыть курс", "url": link}],
                [{"text": "✍️ Написать менеджеру", "url": manager_url(env)}],
            ]})
        else:
            send(token, chat_id, access_text(tier, env), menu_keyboard(env))
    orders = load_json(ORDERS_FILE, [])
    order = next((o for o in orders
                  if existing_order_id
                  and str(o.get("order_id", "")).lower() == str(existing_order_id).lower()), None)
    if order:
        order["status"] = "paid"
        order["paid_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        if charge_id:
            order["charge_id"] = charge_id
    else:
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
    if admin and not existing_order_id:
        price = f"{tier['price_rub']:,}".replace(",", " ")
        stars = f"{tier['stars']:,}".replace(",", " ")
        send(token, admin,
             f"✅ Оплата Stars\nТариф: {tier['title']} ({price} ₽ / {stars} ⭐)\n"
             f"Покупатель: chat_id={chat_id}\ncharge_id: {charge_id}")


def send_faq(token: str, env: dict, chat_id) -> None:
    text = "<b>Частые вопросы</b>\n\n" + "\n\n".join(f"<b>{q}</b>\n{a}" for q, a in FAQ)
    text += "\n\nОстались вопросы — напишите менеджеру."
    send(token, chat_id, text, menu_keyboard(env))


def send_program(token: str, env: dict, chat_id) -> None:
    text = program_text()
    url = course_site_url(env)
    if url:
        text += f"\n\nОткрыть программу: {url}"
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
    marks = {"paid": "✅", "waiting_payment": "⏳", "rejected": "❌"}
    lines = [f"<b>Заказы ({len(orders)})</b>"]
    for o in orders[-20:]:
        who = f" @{o['username']}" if o.get("username") else ""
        mark = marks.get(o.get("status"), "•")
        lines.append(
            f"{mark} {o['order_id']} · {o['tier']} · {o.get('amount_rub', '—')} ₽ · "
            f"chat {o.get('chat_id')}{who}"
        )
    send(token, chat_id, "\n".join(lines))


# ── Ручная выдача: чек → админ → доступ ─────────────────────────────────────

def is_admin(env: dict, chat_id) -> bool:
    admin = env.get("ADMIN_CHAT_ID")
    return bool(admin) and str(chat_id) == str(admin)


def remember_user(from_user: dict) -> None:
    """Запоминает контакт пользователя (локальный файл, не в git)."""
    uid = (from_user or {}).get("id")
    if not uid:
        return
    users = load_json(USERS_FILE, {})
    users[str(uid)] = {
        "username": from_user.get("username", ""),
        "first_name": from_user.get("first_name", ""),
        "last_name": from_user.get("last_name", ""),
        "last_seen": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    save_json(USERS_FILE, users)


def find_order(order_id: str) -> dict | None:
    orders = load_json(ORDERS_FILE, [])
    return next((o for o in orders
                 if str(o.get("order_id", "")).lower() == str(order_id).lower()), None)


def handle_receipt(token: str, env: dict, message: dict) -> None:
    """Покупатель прислал чек (фото/файл): пересылаем админу с кнопками."""
    chat_id = message["chat"]["id"]
    user = message.get("from") or {}
    orders = load_json(ORDERS_FILE, [])
    order = next((o for o in reversed(orders)
                  if str(o.get("chat_id")) == str(chat_id)
                  and o.get("status") == "waiting_payment"), None)
    if order:
        order["receipt"] = {
            "message_id": message.get("message_id"),
            "at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        save_json(ORDERS_FILE, orders)

    admin = env.get("ADMIN_CHAT_ID")
    if not admin:
        send(token, chat_id,
             "Чек получил ✅ Напишите менеджеру — он проверит оплату и откроет доступ.",
             menu_keyboard(env))
        return

    who = (f"@{user.get('username')}" if user.get("username")
           else (user.get("first_name") or "без имени"))
    if order:
        tier = next((t for t in TIERS if t["id"] == order.get("tier")), None)
        price = f"{order.get('amount_rub', 0):,}".replace(",", " ")
        caption = (f"🧾 Чек по заказу {order['order_id']}\n"
                   f"Тариф: {tier['title'] if tier else order.get('tier')} — {price} ₽\n"
                   f"Покупатель: {who} · chat_id={chat_id}\n\n"
                   "Проверьте оплату и нажмите кнопку ниже.")
        keyboard = {"inline_keyboard": [
            [{"text": "✅ Оплата получена — выдать доступ",
              "callback_data": f"grant:{order['order_id']}"}],
            [{"text": "❌ Не подтверждаю", "callback_data": f"reject:{order['order_id']}"}],
        ]}
    else:
        caption = (f"🧾 Файл от {who} · chat_id={chat_id}\n"
                   "Заказ в боте не найден — если это оплата, оформите /catalog.")
        keyboard = None

    params = dict(chat_id=admin, from_chat_id=chat_id,
                  message_id=message["message_id"], caption=caption)
    if keyboard:
        params["reply_markup"] = keyboard
    res = call(token, "copyMessage", **params)
    if not res.get("ok"):
        call(token, "forwardMessage", chat_id=admin, from_chat_id=chat_id,
             message_id=message["message_id"])
        send(token, admin, caption, keyboard)

    if order:
        send(token, chat_id,
             "<b>Чек получил ✅</b>\nПроверяю оплату — обычно это занимает несколько минут. "
             "Доступ придёт сюда же: файлы и ссылка на уроки.")
    else:
        send(token, chat_id,
             "Файл передал администратору. Если это оплата курса — оформите заказ через /catalog, "
             "тогда доступ откроется после проверки.",
             menu_keyboard(env))


def grant_by_order_id(token: str, env: dict, admin_chat, order_id: str,
                      cb_message: dict | None = None) -> None:
    """Админ подтвердил оплату — выдаём доступ покупателю."""
    if not is_admin(env, admin_chat):
        return
    order = find_order(order_id)
    if not order:
        send(token, admin_chat, f"Заказ {order_id} не найден. Список — /orders")
        return
    if order.get("status") == "paid":
        send(token, admin_chat, f"По заказу {order_id} доступ уже выдан.")
        return
    deliver(token, env, order["chat_id"], order["tier"],
            charge_id=f"manual:{order.get('order_id')}",
            existing_order_id=order.get("order_id"))
    who = f"@{order['username']}" if order.get("username") else (order.get("name") or "")
    send(token, admin_chat,
         f"✅ Доступ выдан по заказу {order.get('order_id')} ({order.get('tier')})"
         + (f" — {who}" if who else ""))
    if cb_message:
        call(token, "editMessageReplyMarkup", chat_id=admin_chat,
             message_id=cb_message["message_id"],
             reply_markup={"inline_keyboard": [
                 [{"text": "✅ Доступ выдан", "callback_data": "noop"}]]})


def reject_order(token: str, env: dict, admin_chat, order_id: str,
                 cb_message: dict | None = None) -> None:
    """Админ не подтвердил оплату."""
    if not is_admin(env, admin_chat):
        return
    orders = load_json(ORDERS_FILE, [])
    target = next((o for o in orders
                   if str(o.get("order_id", "")).lower() == str(order_id).lower()), None)
    if not target:
        send(token, admin_chat, f"Заказ {order_id} не найден.")
        return
    target["status"] = "rejected"
    target["rejected_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    save_json(ORDERS_FILE, orders)
    send(token, target["chat_id"],
         f"Оплата по заказу {target.get('order_id')} не подтверждена. "
         "Если это ошибка — напишите менеджеру, разберёмся.",
         menu_keyboard(env))
    send(token, admin_chat, f"❌ Заказ {target.get('order_id')} отклонён, покупатель уведомлён.")
    if cb_message:
        call(token, "editMessageReplyMarkup", chat_id=admin_chat,
             message_id=cb_message["message_id"],
             reply_markup={"inline_keyboard": [
                 [{"text": "❌ Отклонён", "callback_data": "noop"}]]})


def handle_update(env: dict, update: dict) -> None:
    token = env["TELEGRAM_BOT_TOKEN"]

    # Оплата Stars
    message = update.get("message") or {}
    if message.get("from"):
        remember_user(message["from"])
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

    # Чек от покупателя (фото или файл): пересылаем админу с кнопкой выдачи
    if message.get("chat") and (message.get("photo") or message.get("document")):
        handle_receipt(token, env, message)
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
            start_manual_payment(token, env, chat_id, data.split(":", 1)[1], cb.get("from"))
        elif data.startswith("grant:"):
            grant_by_order_id(token, env, chat_id, data.split(":", 1)[1], cb.get("message"))
        elif data.startswith("reject:"):
            reject_order(token, env, chat_id, data.split(":", 1)[1], cb.get("message"))
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
    elif cmd == "/grant":
        if is_admin(env, chat_id):
            if len(parts) > 1:
                grant_by_order_id(token, env, chat_id, parts[1])
            else:
                send(token, chat_id,
                     "Формат: /grant NP-1234567 — выдать доступ по заказу. Список заказов: /orders")
    elif text:
        orders = load_json(ORDERS_FILE, [])
        waiting = any(str(o.get("chat_id")) == str(chat_id) and o.get("status") == "waiting_payment"
                      for o in orders)
        if waiting:
            send(token, chat_id,
                 "Если вы уже перевели оплату — отправьте сюда фото или скриншот чека, "
                 "и доступ откроется после проверки. Реквизиты — в сообщении с заказом выше.",
                 menu_keyboard(env))
        else:
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
