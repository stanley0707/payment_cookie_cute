import asyncio
import random

from faststream.rabbit import RabbitBroker
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
)

from payment_cookie_cute.dto import (
    AggregateType,
    EventType,
    OutboxStatus,
    PaymentCreatedPayload,
    PaymentStatus,
    WebhookCreatePayload,
)
from payment_cookie_cute.repositories import OutboxRepository, PaymentRepository
from payment_cookie_cute.utils import get_logger

logger = get_logger(__name__)


class PaymentProcessor:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        broker: RabbitBroker,
    ) -> None:
        self._session_factory = session_factory
        self._broker = broker

    async def _get_wh_from_event(self, payload: PaymentCreatedPayload) -> str | None:
        async with self._session_factory() as session:
            payments_repository = PaymentRepository(session)
            if payment := await payments_repository.get(payload.payment_id):
                if payment.status != PaymentStatus.PENDING:
                    await logger.ainfo(
                        "payment.already_processed",
                        extra={"payment_id": str(payload.payment_id)},
                    )
                    return None

                return payment.webhook_url

            raise ValueError(f"payment {payload.payment_id} not found")

    async def _init_wh(self, payload: PaymentCreatedPayload, webhook: str) -> None:
        async with self._session_factory() as session:
            payments_repository = PaymentRepository(session)
            outbox_repository = OutboxRepository(session)

            new_status = PaymentStatus.SUCCESS if random.random() < 0.9 else PaymentStatus.FAILURE

            async with session.begin():
                outbox_id = await outbox_repository.get_incr_id()
                wh_payload = WebhookCreatePayload(
                    payment_id=payload.payment_id,
                    webhook_url=webhook,
                    status=new_status,
                    outbox_id=outbox_id,
                    currency=payload.currency,
                    amount=payload.amount,
                )
                if payment := await payments_repository.update_by(
                    payments_repository.model.id == payload.payment_id,
                    payments_repository.model.status == PaymentStatus.PENDING,
                    data={
                        "status": wh_payload.status,
                        "processed_at": wh_payload.processed_at,
                    },
                ):
                    outbox = await outbox_repository.create(
                        id=wh_payload.outbox_id,
                        aggregate_type=AggregateType.WEBHOOK,
                        aggregate_id=payment.id,
                        event_type=EventType.WEBHOOK_SENT,
                        payload=wh_payload.model_dump(mode="json"),
                        status=OutboxStatus.PENDING,
                    )
                    logger.info(f"outbox {outbox.published_at}")

    async def set_to_success(self, payload: PaymentCreatedPayload) -> None:
        async with self._session_factory() as session:
            outbox_repository = OutboxRepository(session)

            async with session.begin():
                await outbox_repository.update_by(
                    outbox_repository.model.id == payload.outbox_id,
                    outbox_repository.model.status == OutboxStatus.PENDING,
                    outbox_repository.model.event_type == EventType.PAYMENT_CREATED,
                    data={
                        "status": OutboxStatus.COMPLETED,
                    },
                )

    async def _add_try_count(self, aggregate_id: str, value: int) -> None:
        async with self._session_factory() as session:
            outbox_repository = OutboxRepository(session)
            await outbox_repository.update_by(
                outbox_repository.model.aggregate_id == aggregate_id,
                outbox_repository.model.event_type == EventType.PAYMENT_CREATED,
                data={"retry_count": value},
            )

    async def process(self, payload: PaymentCreatedPayload, current_retry: int = 0) -> None:
        if wh := await self._get_wh_from_event(payload):
            await self._add_try_count(payload.payment_id, value=current_retry)
            await self.make_payment()
            await self._init_wh(payload, webhook=wh)
            await self.set_to_success(payload)

    @staticmethod
    async def make_payment():
        # make payment here
        await asyncio.sleep(random.uniform(2, 5))
