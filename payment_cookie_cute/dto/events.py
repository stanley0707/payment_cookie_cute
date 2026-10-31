from datetime import datetime
from decimal import Decimal

from pydantic import UUID4

from payment_cookie_cute.core import BaseDto
from payment_cookie_cute.dto.enums import Currency


class PaymentCreatedPayload(BaseDto):
    outbox_id: int
    payment_id: UUID4
    amount: Decimal
    currency: Currency
    webhook_url: str


class WebhookCreatePayload(PaymentCreatedPayload):
    status: str | None = None
    processed_at: datetime | None = None
