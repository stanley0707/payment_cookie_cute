import asyncio

import httpx
from faststream.exceptions import RejectMessage
from faststream.rabbit import (
    RabbitMessage,
    RabbitQueue,
)
from faststream.rabbit.annotations import RabbitBroker
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import async_sessionmaker

from payment_cookie_cute.db.engine import engine
from payment_cookie_cute.dto import PaymentCreatedPayload, WebhookCreatePayload
from payment_cookie_cute.repositories import OutboxRepository
from payment_cookie_cute.services.payment_processor import PaymentProcessor
from payment_cookie_cute.services.webhook_processor import WebhookProcessor
from payment_cookie_cute.settings import QueueSettings, Settings, get_settings
from payment_cookie_cute.utils import get_logger

logger = get_logger(__name__)


PAYMENTS_QUEUE = RabbitQueue(
    get_settings(QueueSettings).event_queue_name,
    durable=True,
    arguments={
        "x-dead-letter-exchange": "",
        "x-dead-letter-routing-key": get_settings(QueueSettings).dlq_event_queue_name,
    },
)

RETRY_PAYMENTS_QUEUE = RabbitQueue(
    get_settings(QueueSettings).retry_event_queue_name,
    durable=True,
    arguments={
        "x-dead-letter-exchange": "",
        "x-dead-letter-routing-key": get_settings(QueueSettings).event_queue_name,
    },
)

WEBHOOK_QUEUE = RabbitQueue(
    get_settings(QueueSettings).event_wh_queue_name,
    durable=True,
    arguments={
        "x-dead-letter-exchange": "",
        "x-dead-letter-routing-key": get_settings(QueueSettings).dlq_event_queue_name,
    },
)

RETRY_WH_WEBHOOK_QUEUE = RabbitQueue(
    get_settings(QueueSettings).retry_wh_event_queue_name,
    durable=True,
    arguments={
        "x-dead-letter-exchange": "",
        "x-dead-letter-routing-key": get_settings(QueueSettings).event_wh_queue_name,
    },
)

DLQ_QUEUE = RabbitQueue(get_settings(QueueSettings).dlq_event_queue_name, durable=True)


def retry_on_error(queue_to_retry: RabbitQueue, dto: type[BaseModel], max_retries: int = 3):
    def decorator(func):
        async def wrapper(payload: dto, message: RabbitMessage, broker: RabbitBroker):
            current_retry = message.headers.get("x-retry-count", 0)
            if current_retry >= max_retries:
                await logger.aerror("message_exhausted", extra={"payload": payload})
                raise RejectMessage()

            try:
                await func(payload, message)
            except Exception as exc:
                new_headers = {**message.headers, "x-retry-count": current_retry + 1}
                delay = 5 * (5**current_retry)
                body = payload.model_dump() if isinstance(payload, BaseModel) else payload
                await broker.publish(
                    body,
                    queue=queue_to_retry,
                    headers=new_headers,
                    expiration=delay,
                )
                await logger.aexception("retry_failed", extra={"error": str(exc)})

        return wrapper

    return decorator


async def main() -> None:
    settings = get_settings(QueueSettings)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    broker = RabbitBroker(settings.rabbitmq_url)

    @broker.subscriber(WEBHOOK_QUEUE)
    @retry_on_error(RETRY_WH_WEBHOOK_QUEUE, dto=WebhookCreatePayload)
    async def handle_webhook(payload: WebhookCreatePayload, message: RabbitMessage, **_):
        async with httpx.AsyncClient(timeout=10.0) as http_client:
            wh_processor = WebhookProcessor(
                session_factory=session_factory,
                http_client=http_client,
                webhook_max_retries=get_settings(Settings).webhook_max_retries,
            )
            await wh_processor.process(
                payload, current_retry=message.headers.get("x-retry-count", 0)
            )

    @broker.subscriber(PAYMENTS_QUEUE)
    @retry_on_error(RETRY_PAYMENTS_QUEUE, dto=PaymentCreatedPayload)
    async def handle_payment(payload: PaymentCreatedPayload, message: RabbitMessage, **_) -> None:
        processor = PaymentProcessor(
            session_factory=session_factory,
            broker=broker,
        )
        await processor.process(payload, current_retry=message.headers.get("x-retry-count", 0))

    @broker.subscriber(DLQ_QUEUE)
    async def handle_dlq(payload: dict) -> None:
        await logger.aerror("dlq.message_received", extra={"payload": payload})

        outbox_id = payload.get("outbox_id")
        if outbox_id:
            async with session_factory() as session:
                outbox_repository = OutboxRepository(session)
                async with session.begin():
                    await outbox_repository.mark_failed(
                        outbox_id, "Exhausted all retries, moved to DLQ"
                    )

    await broker.start()
    await asyncio.Event().wait()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("consumer.stopped")
