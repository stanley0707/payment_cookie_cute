from datetime import datetime

from pydantic import UUID4

from payment_cookie_cute.core import BaseRepository
from payment_cookie_cute.db.models import Payment
from payment_cookie_cute.dto import (
    PaymentDTO,
    PaymentDTOList,
    PaymentDTORead,
    PaymentStatus,
)


class PaymentRepository(
    BaseRepository[
        Payment,
        PaymentDTO,
        PaymentDTORead,
        PaymentDTOList,
    ]
):
    dto = PaymentDTO
    read_dto = PaymentDTORead
    list_dto = PaymentDTOList
    model = Payment

    async def get_by_idempotency_key(self, idempotency_key: str) -> PaymentDTORead | None:
        return await self.get_by(self.model.idempotency_key == idempotency_key)

    async def update_status(
        self,
        payment_id: UUID4,
        status: PaymentStatus,
        processed_at: datetime | None = None,
    ) -> PaymentDTORead | None:
        values: dict = {"status": status.value}
        if processed_at is not None:
            values["processed_at"] = processed_at

        return await self.update(payment_id, **values)
