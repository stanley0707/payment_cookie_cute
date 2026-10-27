import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from payment_cookie_cute.dto import (
    AggregateType,
    EventType,
    OutboxStatus,
    PaymentCreatedPayload,
    PaymentDTO,
    PaymentDTORead,
    PaymentStatus,
)
from payment_cookie_cute.repositories import (
    OutboxRepository,
    PaymentRepository,
)


class PaymentService:
    def __init__(
        self,
        session: AsyncSession,
        payments_repository: PaymentRepository,
        outbox_repository: OutboxRepository,
    ) -> None:
        self._session = session
        self._payments_repository = payments_repository
        self._outbox_repository = outbox_repository

    async def create(
        self,
        data: PaymentDTO,
        idempotency_key: str,
    ) -> PaymentDTORead:
        """
        Retrieve payment process as entry!
        :param data:
        :param idempotency_key:
        :return:
        """
        existing = await self._payments_repository.get_by_idempotency_key(idempotency_key)
        if existing:
            return existing

        try:
            payment = await self._payments_repository.create(
                id=uuid.uuid4(),
                amount=data.amount,
                currency=data.currency.value,
                description=data.description,
                meta=data.meta,
                status=PaymentStatus.PENDING.value,
                idempotency_key=idempotency_key,
                webhook_url=str(data.webhook_url),
            )

            payload = PaymentCreatedPayload(
                payment_id=payment.id,
                amount=payment.amount,
                currency=payment.currency,
                webhook_url=payment.webhook_url,
            ).model_dump(mode="json")

            await self._outbox_repository.create(
                aggregate_type=AggregateType.PAYMENT.value,
                aggregate_id=payment.id,
                event_type=EventType.PAYMENT_CREATED.value,
                payload=payload,
                status=OutboxStatus.PENDING.value,
            )
            return payment

        except IntegrityError:
            await self._session.rollback()
            existing = await self._payments_repository.get_by_idempotency_key(idempotency_key)
            if existing:
                return existing
            raise

    async def get(self, payment_id: uuid.UUID) -> PaymentDTORead | None:
        return await self._payments_repository.get(payment_id)
