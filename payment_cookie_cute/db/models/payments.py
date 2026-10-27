import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Numeric,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)
from sqlalchemy_utils import ChoiceType

from payment_cookie_cute.db.base import Base
from payment_cookie_cute.db.mixins import BaseMixin
from payment_cookie_cute.dto import (
    Currency,
    PaymentStatus,
)


class Payment(BaseMixin, Base):
    __tablename__ = "payments"

    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[Currency] = mapped_column(
        ChoiceType(Currency, impl=String(100)),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    meta: Mapped[dict] = mapped_column(
        "meta",
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    status: Mapped[PaymentStatus] = mapped_column(
        ChoiceType(PaymentStatus, impl=String(100)),
        nullable=False,
        default=PaymentStatus.PENDING,
        server_default=PaymentStatus.PENDING,
        index=True,
    )

    idempotency_key: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
    )
    webhook_url: Mapped[str] = mapped_column(String(2048), nullable=False)

    processed_at: Mapped[datetime.datetime | None] = mapped_column(nullable=True)

    __table_args__ = (CheckConstraint("amount > 0", name="amount_positive"),)
