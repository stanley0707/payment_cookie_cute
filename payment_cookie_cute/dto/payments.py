from datetime import datetime
from decimal import Decimal
from typing import Annotated, Sequence

from pydantic import (
    UUID4,
    ConfigDict,
    Field,
    HttpUrl,
)

from payment_cookie_cute.core import (
    BaseDto,
    BaseListDto,
)
from payment_cookie_cute.dto.enums import Currency, PaymentStatus

Amount = Annotated[Decimal, Field(gt=0, decimal_places=2, max_digits=18)]


class PaymentDTO(BaseDto):
    model_config = ConfigDict(from_attributes=False, extra="forbid")

    amount: Amount
    currency: Currency
    description: str | None = Field(None, max_length=1024)
    meta: dict = Field(default_factory=dict)
    webhook_url: HttpUrl


class PaymentDTORead(BaseDto):
    id: UUID4
    amount: Decimal
    currency: Currency
    description: str | None
    meta: dict
    status: PaymentStatus
    webhook_url: str
    created_at: datetime
    processed_at: datetime | None


class PaymentDTOList(BaseListDto):
    root: Sequence[PaymentDTORead]
