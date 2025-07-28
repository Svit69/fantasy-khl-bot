# Fantasy KHL Bot

Телеграм-бот для Fantasy KHL.

## Запуск

1. Установите зависимости:
   ```bash
   pip install -r requirements.txt
   ```
2. Заполните настройки в `config.py`.
3. Запустите:
   ```bash
   python bot.py
   ```

## Структура проекта
- `bot.py` — точка входа
- `handlers/` — обработчики команд
- `db/` — работа с базой данных
- `utils/` — утилиты
- `tests/` — тесты
- `config.py` — конфигурация
- `requirements.txt` — зависимости
- `Dockerfile` — контейнеризация

## Docker

Пример запуска:
```bash
docker build -t fantasy-khl-bot .
docker run --env TELEGRAM_TOKEN=... --env ADMIN_ID=... fantasy-khl-bot
```
