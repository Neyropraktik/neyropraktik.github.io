# НейроПрактик 2026 — сайт курса и Telegram-бот продаж

Репозиторий курса «НейроПрактик 2026»: статический сайт (лендинг + 5 модулей уроков), Telegram-бот продаж и PDF-материалы.

## Структура

```
index.html              Лендинг курса (3D-дизайн)
kurs/                   Страницы программы и 5 модулей
assets/css, assets/js   Дизайн-система и 3D-поведение (+ course.css/course.js)
assets/brand/, img/     Бренд-книжка, баннер/аватар канала, фавикон
bot/tg_bot.py           Telegram-бот: каталог, оплата, выдача доступа
bot/telegram_net.py     Автоподбор рабочего IP Telegram API (обход блокировок провайдера)
scripts/                publish.py (посты в канал), setup_channel.py, build_pdf.py
products/, pdf/         Исходники и собранные PDF-материалы
content/                Markdown-исходники курса, закреп и посты канала
config/.env.example     Шаблон конфигурации (скопировать в config/.env)
```

## Сайт

Статические файлы, сборка не нужна. Локально: открыть `index.html`.
Деплой: GitHub Pages — Settings → Pages → Source: **Deploy from a branch** → `main` / `/(root)`. Каждый пуш в `main` обновляет сайт автоматически.

### Интерактив (2.0)

- **Интерактивные тесты** — на страницах модулей тест превращается в квиз: варианты, проверка, подсветка правильных/ошибочных, результат. 5/5 → тест считается пройденным, срабатывает конфетти. Без JS статичный вариант с ответами остаётся как fallback.
- **Трекер прогресса** — `localStorage` (`np-progress-v1`): кольцо-процент и счётчики по модулям в оглавлении, чипы «Отметить пройденным» у уроков/заданий/тестов, галочки в TOC, обзор и кнопка «Продолжить: модуль N» на странице программы. Кнопка «Сбросить прогресс» там же.
- **Копирование промптов** — кнопка «⧉ Копировать» у всех цитат с промптами и блоков кода.
- **Тёмная тема** — кнопка 🌙/☀️ в шапке, выбор сохраняется (`np-theme`), учитывается `prefers-color-scheme` при первом визите.
- Прочее: уведомления-тосты («модуль пройден»), анимированные счётчики в герое, кнопка «наверх».

Файлы: `assets/js/course.js` + `assets/css/course.css` (подключаются после `app.js`/`style.css`).

### Единый стиль (бренд)

Оформление сайта, бота, канала и PDF ведётся по бренд-книжке: `assets/brand/README.md`.

- **Палитра**: неон-маджента `#d331e8` (тёмная тема `#e44dff`) + неон-циан `#3ddbe8`; тёмный фон сайта `#0d0916`, карточки `#1b1428`. Свечения — маджента (никаких синих/жёлтых).
- **Теглайн**: «ИИ • Идеи • Практика • Результат» — в гером лендинга, футерах, приветствии и каталоге бота, описании канале и закрепе.
- **Фавикон**: `assets/img/favicon.svg` (кружок+«НП» в брендовом градиенте).
- **Соцпревью**: `index.html` ссылается на `assets/brand/banner.jpg` — положите файл баннера, превью заработает.
- **PDF**: заголовки H1/H2/H3 печатаются брендовой маджентой (`scripts/build_pdf.py`).

## Бот

```bash
# заполнить config/.env (токен, chat_id канала, COURSE_URL, ADMIN_CHAT_ID, BOOSTY_URL)
python3 bot/tg_bot.py
```

- `/start` — меню, `/catalog` — тарифы, `/checklist` — бесплатный чек-лист PDF
- Меню: теглайн-брендинг, кнопка «💜 Boosty — посты и разборы» (появляется при заполненном `BOOSTY_URL`)
- Оплата: Telegram Stars (XTR) или перевод; после оплаты бот присылает доступ и PDF-материалы
- Заказы: `bot/orders.json`; `/orders` — для админа
- **Обход блокировок**: некоторые провайдеры блокируют часть IP-адресов Telegram — `bot/telegram_net.py` при старте проверяет штатный маршрут и при необходимости подключается через резервный IP, а после серии сетевых сбоев переподбирает адрес автоматически. Подключается также в `scripts/publish.py` и `scripts/setup_channel.py`.

⚠️ **Токен бота скомпрометирован**: раньше он попал в `config/.env.example` и историю git. Перегенерировать: @BotFather → /mybots → выбрать бота → API Token → Revoke. Новый токен-record — только в `config/.env` (не в .example, не коммитить).

## Публикация в канал

```bash
python3 scripts/publish.py content/posts/post.md            # опубликовать
python3 scripts/publish.py content/posts/post.md --dry-run  # проверить
python3 scripts/publish.py content/posts/post.md --photo assets/brand/banner.jpg  # с обложкой

python3 scripts/setup_channel.py --check                       # состояние канала
python3 scripts/setup_channel.py --apply                       # брендовое имя/описание/закреп
python3 scripts/setup_channel.py --apply --avatar assets/brand/avatar.png    # аватар канала
python3 scripts/setup_channel.py --apply --banner assets/brand/banner.jpg    # баннер-пост
```

## PDF

```bash
bash scripts/build_all.sh   # products/*.md -> pdf/
```

Требуется `fpdf2` (`pip install fpdf2`) и шрифты DejaVu.

---

Материалы обновлены: октябрь 2026. Лицензия: Apache-2.0.
