import httpx
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
)

from payment_cookie_cute.dto import (
    EventType,
    OutboxStatus,
    PaymentStatus,
    WebhookCreatePayload,
)
from payment_cookie_cute.repositories import OutboxRepository, PaymentRepository
from payment_cookie_cute.utils import get_logger

logger = get_logger(__name__)


class WebhookProcessor:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        http_client: httpx.AsyncClient,
        webhook_max_retries: int = 3,
    ) -> None:
        self._session_factory = session_factory
        self._http = http_client
        self._webhook_max_retries = webhook_max_retries

    async def validate_request(self, payload: WebhookCreatePayload) -> bool:
        async with self._session_factory() as session:
            payments_repository = PaymentRepository(session)

            if payment := await payments_repository.get(payload.payment_id):
                if payment.status == PaymentStatus.SUCCESS:
                    outbox_repository = OutboxRepository(session)
                    if wh_outbox := await outbox_repository.get(payload.outbox_id):
                        if wh_outbox.status == OutboxStatus.PUBLISHED:
                            return True

        return False

    async def set_to_success(self, payload: WebhookCreatePayload) -> None:
        async with self._session_factory() as session:
            outbox_repository = OutboxRepository(session)

            async with session.begin():
                await outbox_repository.update_by(
                    outbox_repository.model.id == payload.outbox_id,
                    outbox_repository.model.status == OutboxStatus.PENDING,
                    outbox_repository.model.event_type == EventType.WEBHOOK_SENT,
                    data={
                        "status": OutboxStatus.COMPLETED,
                    },
                )

    async def _add_try_count(self, aggregate_id: str, value: int) -> None:
        async with self._session_factory() as session:
            outbox_repository = OutboxRepository(session)
            await outbox_repository.update_by(
                outbox_repository.model.aggregate_id == aggregate_id,
                outbox_repository.model.event_type == EventType.WEBHOOK_SENT,
                data={"retry_count": value},
            )

    async def process(self, payload: WebhookCreatePayload, current_retry: int = 0) -> None:
        if await self.validate_request(payload):
            await self._add_try_count(payload.payment_id, value=current_retry)
            await self._send_webhook(payload)
            await self.set_to_success(payload)

    async def _send_webhook(self, payment: WebhookCreatePayload) -> None:
        if payment is not None:
            resp = await self._http.post(
                payment.webhook_url,
                json={
                    "payment_id": str(payment.payment_id),
                    "status": payment.status,
                    "processed_at": payment.processed_at,
                },
            )

            resp.raise_for_status()
