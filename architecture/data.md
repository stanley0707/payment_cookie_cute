
## Модели данных

### Payments
| Поле | Тип | Ограничения | Описание |
|---|---|---|---|
| `id` | `UUID` | PK, `default=uuid4` | Непредсказуемый ID, безопасен для внешних ссылок |
| `amount` | `Numeric(18, 2)` | `NOT NULL` | Сумма. Никогда `Float` — теряет копейки |
| `currency` | `Currency` (`VARCHAR(3)`) | `NOT NULL` | Валюта, check constraint по enum |
| `description` | `String(1024)` | nullable | Описание платежа |
| `meta` (колонка `metadata`) | `JSONB` | `NOT NULL`, default `'{}'` | Произвольные метаданные, индексируется GIN |
| `status` | `PaymentStatus` | `NOT NULL`, default `pending`, index | Бизнес-статус, меняет consumer |
| `idempotency_key` | `String(255)` | `NOT NULL`, UNIQUE, index | Защита от дублей входящих запросов |
| `webhook_url` | `String(2048)` | `NOT NULL` | Куда отправить уведомление |
| `created_at` | `DateTime(timezone=True)` | `NOT NULL`, `server_default=now()` | Время создания (время БД) |
| `processed_at` | `DateTime(timezone=True)` | nullable | Заполняется consumer'ом после обработки |

### Outbox
| Поле | Тип | Ограничения | Описание |
|---|---|---|---|
| `id` | `BigInteger` | PK, autoincrement | `bigserial`, монотонная упорядоченность для relay |
| `aggregate_type` | `String(50)` | `NOT NULL` | Тип агрегата: `payment`, `refund`, `webhook_sent` … |
| `aggregate_id` | `UUID` | `NOT NULL` | ID агрегата (без FK — outbox не зависит от бизнес-схемы) |
| `event_type` | `String(100)` | `NOT NULL` | Тип события: `payment.created` … |
| `payload` | `JSONB` | `NOT NULL` | Денормализованное событие |
| `status` | `OutboxStatus` | `NOT NULL`, default `pending` | `pending` → `published` / `failed` |
| `retry_count` | `Integer` | `NOT NULL`, default `0` | Сколько раз relay пытался опубликовать |
| `last_error` | `String(2048)` | nullable | Текст последней ошибки публикации |
| `created_at` | `DateTime(timezone=True)` | `NOT NULL`, `server_default=now()` | Время создания события |
| `published_at` | `DateTime(timezone=True)` | nullable | Время успешной публикации в брокер |

### Enums
| Enum | Значения | Назначение |
|---|---|---|
| `Currency` | `RUB` · `USD` · `EUR` | Валюта платежа (`native_enum=False` — добавление валюты без `ALTER TYPE`) |
| `PaymentStatus` | `pending` · `succeeded` · `failed` | Бизнес-исход обработки, меняет только consumer |
| `OutboxStatus` | `pending` · `published` · `failed` | Статус публикации события, меняет только relay |

### Ответственность статусов «кто меняет статус»
| Процесс \ Сущность | `payments.status`                   | `outbox.status`                     |
|---|-------------------------------------|-------------------------------------|
| **API** (создание) | `pending` (INSERT)                  | `pending` (INSERT)                  |
| **Outbox Relay** | —                                   | `pending` > `published` \| `failed` |
| **Consumer** | `pending` > `succeeded` \| `failed` | —                                   |

### легенды матрицы состояний
| Обозначение | Смысл | Действие |
|---|---|---|
| Норма | Штатное состояние | — |
| Транзиент | Кратковременное, разрешается само (или идемпотентностью) | — |
| Проблема | Финансовый риск: платёж не будет обработан | Alert + `UPDATE outbox SET status='pending', retry_count=0` |
| Edge case | Риск дубля, закрывается идемпотентностью | Ручной разбор |

### Матрица состояний payments × outbox

| `payments` \ `outbox` | `pending` | `published` | `failed` |
|---|---|---|---|
| **`pending`** | Норма: создан, relay ещё не забрал (или ждёт retry) | Норма: опубликовано, consumer в процессе | Зависший платёж: не уйдёт в брокер, нужен ручной reset |
| **`succeeded`** | Транзиент: relay опубликовал, но упал до UPDATE outbox → будет дубль | Норма: бизнес-успех, всё корректно | Edge case: обработан, но relay «сдался» — ручной разбор |
| **`failed`** | Транзиент: то же, что succeeded × pending | Норма: бизнес-неудача, всё корректно | Edge case: то же, что succeeded × failed |


### Матрица «событие > статус > DLQ

| Событие | `payments.status` | `outbox.status` | RabbitMQ         | В DLQ?                                 |
|---|---|---|------------------|----------------------------------------|
| Платёж создан | `pending` | `pending` | —                | no                                     |
| Relay опубликовал | `pending` | `published` | в `payments.new` | no                                     |
| Consumer: 90% успех | `succeeded` | `published` | `ack`            | no                                     |
| Consumer: 10% бизнес-отказ | `failed` | `published` | `ack`            | no (бизнес-исход, не технический сбой) |
| Consumer: webhook не ушёл после 3 retry | `succeeded` \| `failed` | `published` | `nack` > DLQ     | yes                                    |
| Consumer: exception в коде | `pending` (не обновлён) | `published` | `nack` > DLQ     | yes                                    |
| Relay: RabbitMQ недоступен 3 раза | `pending` | `failed` | —                | no (нечего класть — сообщение не ушло) |