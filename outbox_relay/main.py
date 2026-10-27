import asyncio

from faststream.rabbit import RabbitBroker
from sqlalchemy.ext.asyncio import async_sessionmaker

from payment_cookie_cute.db.engine import engine
from payment_cookie_cute.services.outbox_publisher import OutboxPublisher
from payment_cookie_cute.settings import QueueSettings, Settings, get_settings
from payment_cookie_cute.utils import get_logger

logger = get_logger(__name__)


async def main() -> None:
    settings = get_settings(QueueSettings)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    broker = RabbitBroker(settings.rabbitmq_url)
    logger.info("outbox_relay.started")
    async with broker:
        await OutboxPublisher(
            session_factory=session_factory,
            broker=broker,
            queue_settings=settings,
            max_retries=get_settings(Settings).webhook_max_retries,
            poll_interval=1.0,
        ).run_forever()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("outbox_relay.stopped")
