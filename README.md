# Payment Cookie Cute — Асинхронный сервис процессинга платежей

Микросервис для асинхронной обработки платежей с гарантированной доставкой событий через паттерн **Transactional Outbox**, защитой от дублей и Dead Letter Queue (DLQ).

> Подробное описание архитектуры, паттернов и схемы БД доступно в [ARCHITECTURE.md](./ARCHITECTURE.md).

## 🚀 Стек технологий
*   **API**: FastAPI + Pydantic v2
*   **База данных**: PostgreSQL, SQLAlchemy 2.0 (async), Alembic
*   **Брокер сообщений**: RabbitMQ, FastStream
*   **Тестирование**: Pytest, Anyio, Ruff
*   **Инфраструктура**: Docker, Docker Compose

## 📦 Быстрый старт

1. Склонируйте репозиторий и создайте `.env` файл:
```bash
cp .env.example .env
```
2. Запустите инфраструктуру (API, БД, RabbitMQ, Consumer, Relay):
```bash
docker compose up -d --build
```
3. Доступы:
- API (Swagger): http://localhost:8000/docs
- RabbitMQ Management: http://localhost:15672 (логин/пароль: test-user / test-user)


### Запуск тестов
Тесты запускаются в изолированном окружении с чистой БД (в памяти) и автоматически применяют миграции перед запуском.
```bash
./scripts/test.sh
```

### Примеры API запросов
1) Создание платежа (с идемпотентностью)

```bash
curl -X POST http://localhost:8000/api/v1/payments \
  -H "X-API-Key: dev-secret-key" \
  -H "Idempotency-Key: $(uuidgen)" \
  -H "Content-Type: application/json" \
  -d '{
    "amount": "1500.50",
    "currency": "RUB",
    "description": "Оплата подписки",
    "metadata": {"order_id": "12345"},
    "webhook_url": "https://webhook.site/your-unique-url"
  }'
```

2) Получение информации о платеже
```bash
curl -X GET http://localhost:8000/api/v1/payments/{payment_id} \
  -H "X-API-Key: dev-secret-key"
```

### Разработка и линтеры
```bash
make format
make lint
```

### структура проекта
```
├── payment_cookie_cute/      # Исходный код API
│   ├── core/                 # Базовые классы (Repository, DTO)
│   ├── db/                   # Модели SQLAlchemy, Engine, Mixins
│   ├── dto/                  # Pydantic-схемы и Enum'ы
│   ├── repositories/         # Слой работы с БД
│   ├── router/               # FastAPI роутеры и DI
│   ├── services/             # Бизнес-логика
│   └── settings.py           # Pydantic Settings (12-factor)
├── consumer/                 # FastStream консюмер (обработка событий из RabbitMQ)
├── outbox_relay/             # Воркер публикации событий из БД в RabbitMQ
├── alembic/                  # Миграции БД
├── tests/                    # Pytest тесты (Unit + Integration)
├── Dockerfile                # Multi-stage сборка
├── docker-compose.yml        # Основная инфраструктура
└── docker-compose.test.yml   # Инфраструктура для тестов
```