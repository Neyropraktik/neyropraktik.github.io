#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Сетевой помощник для Telegram Bot API.

Провайдеры (особенно в РФ) блокируют часть IP-адресов Telegram. Системный
DNS может выдать недоступный адрес api.telegram.org — тогда все запросы
бота виснут и падают с таймаутом. Модуль подбирает рабочий IP из списка
известных адресов Telegram и перенаправляет TCP-подключения к
api.telegram.org на него. SNI и проверка TLS-сертификата остаются по имени
хоста, поэтому соединение защищено как обычно.

Использование:
    from telegram_net import init_telegram_net, refresh_telegram_ip
    init_telegram_net()          # при старте
    refresh_telegram_ip()        # при серии сетевых ошибок
"""

import socket

TELEGRAM_API_HOST = "api.telegram.org"

# Официальные адреса Telegram Bot API (проверяются по очереди).
TELEGRAM_API_IPS = [
    "149.154.167.220",
    "149.154.167.222",
    "149.154.167.197",
    "149.154.166.110",
    "149.154.175.53",
    "91.108.56.130",
]

_state = {"ip": None, "patched": False}


def _try_ip(ip: str, timeout: float = 2.5) -> bool:
    """Проверяет, открывается ли TCP-соединение до IP (порт 443)."""
    try:
        with socket.create_connection((ip, 443), timeout=timeout):
            return True
    except OSError:
        return False


def _standard_route_works() -> bool:
    """Работает ли штатный маршрут через системный DNS."""
    try:
        infos = socket.getaddrinfo(TELEGRAM_API_HOST, 443)
    except OSError:
        return False
    for info in infos:
        ip = info[4][0]
        if _try_ip(ip):
            return True
    return False


def find_telegram_ip(exclude: str | None = None) -> str | None:
    """Возвращает первый доступный IP Telegram или None."""
    for ip in TELEGRAM_API_IPS:
        if ip == exclude:
            continue
        if _try_ip(ip):
            return ip
    return None


def _apply_patch() -> None:
    """Направляет TCP-подключения к api.telegram.org на выбранный IP."""
    if _state["patched"]:
        return
    original = socket.getaddrinfo

    def patched(host, port, *args, **kwargs):
        if host == TELEGRAM_API_HOST and _state["ip"]:
            host = _state["ip"]
        return original(host, port, *args, **kwargs)

    socket.getaddrinfo = patched
    _state["patched"] = True


def init_telegram_net() -> str | None:
    """Подбирает рабочий IP и включает перенаправление.

    Если штатный маршрут (системный DNS) работает — ничего не меняет.
    Возвращает выбранный IP или None (когда вмешательство не нужно).
    """
    if _state["ip"]:
        return _state["ip"]
    if _standard_route_works():
        return None
    ip = find_telegram_ip()
    if ip:
        _state["ip"] = ip
        _apply_patch()
        print(f"Telegram API: соединение через резервный IP {ip}")
    else:
        print("Telegram API: рабочий IP не найден — пробуем штатный маршрут",
              flush=True)
    return ip


def refresh_telegram_ip() -> str | None:
    """Переподбор IP: например, когда прежний адрес перестал отвечать."""
    old = _state["ip"]
    ip = find_telegram_ip(exclude=old)
    if ip:
        _state["ip"] = ip
        _apply_patch()
        return ip
    return old
