import asyncio

from faststream.rabbit import RabbitBroker
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from payment_cookie_cute.dto import EventType
from payment_cookie_cute.repositories import OutboxRepository
from payment_cookie_cute.settings import QueueSettings
from payment_cookie_cute.utils import get_logger

logger = get_logger(__name__)


class OutboxPublisher:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        broker: RabbitBroker,
        queue_settings: QueueSettings,
        max_retries: int = 3,
        poll_interval: float = 1.0,
    ) -> None:
        self._session_factory = session_factory
        self._broker = broker
        self._queue = queue_settings.event_queue_name
        self._queue_wh = queue_settings.event_wh_queue_name
        self._max_retries = max_retries
        self._poll_interval = poll_interval

    async def process_batch(self, limit: int = 100) -> int:
        """
        Return successfully processed payment event batch.
        """
        async with self._session_factory() as session:
            outbox_repository = OutboxRepository(session)
            published = 0

            async with session.begin():
                events = await outbox_repository.fetch_pending(limit=limit)
                for event in events:
                    try:
                        if event.event_type == EventType.PAYMENT_CREATED:
                            await self._broker.publish(event.payload, queue=self._queue)
                        elif event.event_type == EventType.WEBHOOK_SENT:
                            await self._broker.publish(event.payload, queue=self._queue_wh)

                        await outbox_repository.mark_published(event.id)
                        published += 1

                    except Exception as exc:
                        await logger.aexception(
                            "outbox.publish_failed",
                            extra={"outbox_id": event.id},
                        )
                        new_retry = await outbox_repository.increment_retry(
                            event.id,
                            str(exc),
                        )
                        if new_retry >= self._max_retries:
                            await outbox_repository.mark_failed(event.id, str(exc))
                            logger.error(
                                "outbox.give_up",
                                extra={
                                    "outbox_id": event.id,
                                    "aggregate_id": str(event.aggregate_id),
                                },
                            )
            return published

    async def run_forever(self) -> None:
        await logger.ainfo("outbox_publisher.started", extra={"queue": self._queue})
        while True:
            try:
                await self.process_batch()
            except Exception as exc:
                await logger.aexception("outbox_publisher.loop_error, %r", exc)
            await asyncio.sleep(self._poll_interval)
