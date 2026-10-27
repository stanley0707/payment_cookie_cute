import uuid
from datetime import UTC, datetime
from decimal import Decimal

from payment_cookie_cute.dto import (
    Currency,
    PaymentDTORead,
    PaymentStatus,
)


def make_payment_read(**overrides) -> PaymentDTORead:
    """
    PaymentDTORead / overrides.
    """
    defaults = dict(
        id=uuid.uuid4(),
        amount=Decimal("100.00"),
        currency=Currency.RUB,
        description="Test payment",
        meta={"order_id": "123"},
        status=PaymentStatus.PENDING,
        webhook_url="https://example.com/webhook",
        created_at=datetime.now(UTC),
        processed_at=None,
    )
    defaults.update(overrides)
    return PaymentDTORead(**defaults)


def make_payment_create_payload(**overrides) -> dict:
    """
    JSON POST /api/v1/payments.
    """
    defaults = {
        "amount": "100.00",
        "currency": "RUB",
        "description": "Test payment",
        "meta": {"order_id": "123"},
        "webhook_url": "https://example.com/webhook",
    }
    defaults.update(overrides)
    return defaults


def make_payment_create_dto(**overrides):
    from payment_cookie_cute.dto import PaymentDTO

    return PaymentDTO(**make_payment_create_payload(**overrides))
