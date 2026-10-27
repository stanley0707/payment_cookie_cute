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
            x_death = message.headers.get("x-death", [])
            retry_count = x_death[0]["count"] if x_death else 0

            if retry_count >= 3:
                await logger.aerror(
                    "consumer.message_exhausted",
                    extra={"payload": payload, "retries": retry_count},
                )
                raise RejectMessage()

            try:
                await processor.process(payload)
            except Exception as exc:
                await logger.aexception(
                    "consumer.processing_failed",
                    extra={"error": str(exc), "retry": retry_count},
                )
                raise exc

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
