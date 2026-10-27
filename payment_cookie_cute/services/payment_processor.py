import asyncio
import random
import uuid
from datetime import UTC, datetime

import httpx
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
)

from payment_cookie_cute.dto import (
    PaymentDTORead,
    PaymentStatus,
)
from payment_cookie_cute.repositories import PaymentRepository
from payment_cookie_cute.utils import get_logger

logger = get_logger(__name__)


class PaymentProcessor:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        http_client: httpx.AsyncClient,
        webhook_max_retries: int = 3,
    ) -> None:
        self._session_factory = session_factory
        self._http = http_client
        self._webhook_max_retries = webhook_max_retries

    async def process(self, payload: dict) -> None:
        async with self._session_factory() as session:
            payments_repository = PaymentRepository(session)
            payment_id = uuid.UUID(payload["payment_id"])

            async with session.begin():
                payment = await payments_repository.get(payment_id, for_update=True)
                if payment is None:
                    raise ValueError(f"payment {payment_id} not found")
                if payment.status != PaymentStatus.PENDING:
                    logger.info(
                        "payment.already_processed",
                        extra={"payment_id": str(payment_id)},
                    )
                    return

                await asyncio.sleep(random.uniform(2, 5))

                new_status = (
                    PaymentStatus.SUCCESS if random.random() < 0.9 else PaymentStatus.FAILURE
                )
                updated = await payments_repository.update_status(
                    payment.id,
                    new_status,
                    processed_at=datetime.now(UTC),
                )

            await self._send_webhook(updated, new_status)

    async def _send_webhook(
        self,
        payment: PaymentDTORead | None,
        status: PaymentStatus,
    ) -> None:
        if payment is None:
            return
        payload = {
            "payment_id": str(payment.id),
            "status": status.value,
            "processed_at": payment.processed_at.isoformat() if payment.processed_at else None,
        }
        for attempt in range(self._webhook_max_retries):
            try:
                resp = await self._http.post(payment.webhook_url, json=payload)
                resp.raise_for_status()
                return
            except httpx.HTTPError as exc:
                await logger.awarning(
                    "webhook.attempt_failed",
                    extra={"attempt": attempt + 1, "error": str(exc)},
                )
                await asyncio.sleep(2**attempt)
        await logger.aerror(
            "webhook.give_up",
            extra={"payment_id": str(payment.id)},
        )
