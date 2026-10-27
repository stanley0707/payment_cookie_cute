import datetime
import uuid

from sqlalchemy import (
    BigInteger,
    DateTime,
    Index,
    Integer,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)
from sqlalchemy_utils import ChoiceType

from payment_cookie_cute.db.base import Base
from payment_cookie_cute.db.mixins import created_timestamp
from payment_cookie_cute.dto import (
    AggregateType,
    EventType,
    OutboxStatus,
)


class Outbox(Base):
    __tablename__ = "outbox"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    aggregate_type: Mapped[AggregateType] = mapped_column(
        ChoiceType(AggregateType, impl=String(100)),
        nullable=False,
        index=True,
    )
    aggregate_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    event_type: Mapped[EventType] = mapped_column(
        ChoiceType(EventType, impl=String(100)),
        nullable=False,
    )
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)

    status: Mapped[OutboxStatus] = mapped_column(
        ChoiceType(OutboxStatus, impl=String(100)),
        nullable=False,
        default=OutboxStatus.PENDING,
        server_default=OutboxStatus.PENDING,
    )
    retry_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    last_error: Mapped[str | None] = mapped_column(String(2048), nullable=True)

    published_at: Mapped[datetime.datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[created_timestamp] = mapped_column()
    updated_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True),
        server_default=None,
        onupdate=func.now(),
    )

    __table_args__ = (
        Index(
            "ix_outbox_status_created_at",
            "status",
            "created_at",
            postgresql_where=text("status = 'pending'"),
        ),
    )
