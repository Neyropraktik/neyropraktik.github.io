# НейроПрактик 2026 — сайт курса и Telegram-бот продаж

Репозиторий курса «НейроПрактик 2026»: статический сайт (лендинг + 5 модулей уроков), Telegram-бот продаж и PDF-материалы.

## Структура

```
index.html              Лендинг курса (3D-дизайн)
kurs/                   Страницы программы и 5 модулей
assets/css, assets/js   Дизайн-система и 3D-поведение
bot/tg_bot.py           Telegram-бот: каталог, оплата, выдача доступа
scripts/                publish.py (посты в канал), setup_channel.py, build_pdf.py
products/, pdf/         Исходники и собранные PDF-материалы
content/                Markdown-исходники курса, закреп и посты канала
config/.env.example     Шаблон конфигурации (скопировать в config/.env)
```

## Сайт

Статические файлы, сборка не нужна. Локально: открыть `index.html`.
Деплой: GitHub Pages (workflow в `.github/workflows/pages.yml`, включается в Settings → Pages → Source: GitHub Actions).

## Бот

```bash
# заполнить config/.env (токен, chat_id канала, COURSE_URL, ADMIN_CHAT_ID)
python3 bot/tg_bot.py
```

- `/start` — меню, `/catalog` — тарифы, `/checklist` — бесплатный чек-лист PDF
- Оплата: Telegram Stars (XTR) или перевод; после оплаты бот присылает доступ и PDF-материалы
- Заказы: `bot/orders.json`; `/orders` — для админа

## Публикация в канал

```bash
python3 scripts/publish.py content/posts/post.md            # опубликовать
python3 scripts/publish.py content/posts/post.md --dry-run  # проверить
python3 scripts/setup_channel.py --apply                    # имя/описание/закреп
```

## PDF

```bash
bash scripts/build_all.sh   # products/*.md -> pdf/
```

Требуется `fpdf2` (`pip install fpdf2`) и шрифты DejaVu.

---

Материалы обновлены: октябрь 2026. Лицензия: Apache-2.0.
