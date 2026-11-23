# Запуск и разработка

## Локальная среда

Нужны Python 3.13+, [uv](https://docs.astral.sh/uv/) и Docker Compose.

```bash
cp .env.example .env
uv sync --extra dev
uv run uvicorn medication_reminder.main:app --reload
```

Сервис отвечает на `http://localhost:8000/health`. Для работы бота, worker и
инфраструктуры запустите полный стек:

```bash
docker compose up --build
```

Для запуска без Docker после отдельного запуска PostgreSQL, Redis и миграций:

```bash
uv run alembic upgrade head
uv run python -m medication_reminder.telegram
uv run python -m medication_reminder.reminders
```

## Локальный Mini App

Изолированный демо-стенд поднимает временную PostgreSQL-базу с фиктивными
назначениями. Он не читает `.env`, не использует Telegram-бота и публикует порт только
на `127.0.0.1`:

```bash
docker compose -f compose.demo.yaml up --build
```

Страница: `http://127.0.0.1:8002/mini-app`.

Остановка и удаление стенда:

```bash
docker compose -f compose.demo.yaml down
```

Для локальной проверки настоящей Telegram Mini App можно запустить узкую HTTP-поверхность
и опубликовать её через HTTPS-туннель:

```bash
uv run uvicorn medication_reminder.mini_app_local:app --host 127.0.0.1 --port 8001
cloudflared tunnel --url http://127.0.0.1:8001 --no-autoupdate
```

Укажите полученный URL с суффиксом `/mini-app` в
`MEDICATION_TELEGRAM_MINI_APP_URL`. Не направляйте туннель на основной API.

## Конфигурация и секреты

Скопируйте `.env.example` в `.env` и задайте как минимум
`MEDICATION_TELEGRAM_BOT_TOKEN`. Настоящие `.env`-файлы, приватные ключи, дампы и
резервные копии не должны попадать в Git.

В production-стеке используются переменные из `.env.production`; он требует
`POSTGRES_PASSWORD` и `APP_HOST`:

```bash
docker compose -f compose.vps.yaml up -d --build
```

## Проверки

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy
```

Интеграционные тесты используют отдельную базу:

```bash
docker compose --profile test up -d test-postgres
MEDICATION_TEST_DATABASE_URL=postgresql+asyncpg://medication:medication@localhost:55432/medication_test uv run pytest -m integration
docker compose --profile test down
```
