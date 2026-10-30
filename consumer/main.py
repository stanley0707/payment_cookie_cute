import asyncio

import httpx
from faststream.exceptions import RejectMessage
from faststream.rabbit import (
    RabbitBroker,
    RabbitMessage,
    RabbitQueue,
)
from sqlalchemy.ext.asyncio import async_sessionmaker

from payment_cookie_cute.db.engine import engine
from payment_cookie_cute.services.payment_processor import PaymentProcessor
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
        "x-message-ttl": get_settings(QueueSettings).retry_ttl,
        "x-dead-letter-exchange": "",
        "x-dead-letter-routing-key": get_settings(QueueSettings).event_queue_name,
    },
)

DLQ_QUEUE = RabbitQueue(get_settings(QueueSettings).dlq_event_queue_name, durable=True)


async def main() -> None:
    settings = get_settings(QueueSettings)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    broker = RabbitBroker(settings.rabbitmq_url)

    async with httpx.AsyncClient(timeout=10.0) as http_client:
        processor = PaymentProcessor(
            session_factory=session_factory,
            http_client=http_client,
            webhook_max_retries=get_settings(Settings).webhook_max_retries,
        )

        @broker.subscriber(PAYMENTS_QUEUE)
        async def handle_payment(payload: dict, message: RabbitMessage) -> None:
            current_retry = message.headers.get("x-retry-count", 0)

            if current_retry >= 3:
                await logger.aerror(
                    "consumer.message_exhausted",
                    extra={"payload": payload, "retries": current_retry},
                )
                raise RejectMessage()

            try:
                await processor.process(payload)
            except Exception as exc:
                new_headers = {**message.headers, "x-retry-count": current_retry + 1}
                await broker.publish(payload, queue=RETRY_PAYMENTS_QUEUE, headers=new_headers)
                await logger.aexception(
                    "Retry for consumer.processing_failed",
                    extra={"error": str(exc), "retry": current_retry},
                )
                return

        @broker.subscriber(DLQ_QUEUE)
        async def handle_dlq(payload: dict) -> None:
            await logger.aerror("dlq.message_received", extra={"payload": payload})

        await broker.start()
        await asyncio.Event().wait()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("consumer.stopped")
