
# Архитектура сервиса

Документ описывает ключевые архитектурные решения, паттерны и жизненный цикл данных в сервисе.

## Компоненты системы

1. **API (FastAPI)** - принимает запросы, валидирует их и сохраняет в БД.
2. **PostgreSQL** - основное хранилище (таблицы `payments` и `outbox`).
3. **Outbox Relay** - фоновый воркер, вычитывает события из таблицы `outbox` и публикует их в RabbitMQ.
4. **RabbitMQ** - брокер сообщений (очереди `payments.new` и `payments.new.dlq`).
5. **Consumer (FastStream)** - фоновый воркер, забирает сообщения из RabbitMQ, эмулирует обработку платежа и отправляет Webhook.

## Паттерн Transactional Outbox

Прямая отправка сообщения в RabbitMQ из API-метода.
**Решение:** При создании платежа записи в таблицы `payments` и `outbox` создаются в **одной транзакции** БД.
Событие в `outbox` имеет статус `pending`. Воркер `Outbox Relay` использует конструкцию `SELECT ... FOR UPDATE SKIP LOCKED`, забирает пачку событий и отправляет их в брокер.
Только после успешной отправки статус меняется на `published`.

## Схема обработки платежа

```mermaid
sequenceDiagram
    participant Client
    participant API
    participant DB as PostgreSQL
    participant Relay as Outbox Relay
    participant MQ as RabbitMQ
    participant Consumer
    participant Webhook

    Client->>API: POST /api/v1/payments (Idempotency-Key)
    API->>DB: BEGIN
    API->>DB: INSERT INTO payments (status=pending)
    API->>DB: INSERT INTO outbox (status=pending)
    API->>DB: COMMIT
    API-->>Client: 202 Accepted (payment_id)

    loop Poll (каждую 1 сек)
        Relay->>DB: SELECT outbox FOR UPDATE SKIP LOCKED
        Relay->>MQ: Publish to payments.new
        Relay->>DB: UPDATE outbox SET status=published
    end

    MQ->>Consumer: Deliver message
    Consumer->>DB: SELECT payment FOR UPDATE
    Note over Consumer: Проверка идемпотентности<br/>(если status != pending, ACK)
    Consumer->>Consumer: sleep(random 2-5s)
    Consumer->>Consumer: roll(90% success, 10% fail)
    Consumer->>DB: UPDATE payments SET status=succeeded/failed
    Consumer->>Webhook: POST /webhook (retry 3x)
    Consumer-->>MQ: ACK
```