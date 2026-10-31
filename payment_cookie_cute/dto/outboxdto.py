import uuid
from datetime import datetime
from typing import Any, Sequence

from payment_cookie_cute.core import (
    BaseDto,
    BaseListDto,
)
from payment_cookie_cute.dto.enums import (
    AggregateType,
    EventType,
    OutboxStatus,
    WebhookStatus,
)
from payment_cookie_cute.dto.events import (
    PaymentCreatedPayload,
    WebhookCreatePayload,
)


class OutboxDTO(BaseDto):
    aggregate_type: AggregateType
    aggregate_id: uuid.UUID
    event_type: EventType
    payload: PaymentCreatedPayload | WebhookCreatePayload
    status: OutboxStatus = OutboxStatus.PENDING
    webhook_status: WebhookStatus = WebhookStatus.PENDING
    retry_count: int = 0
    last_error: str | None = None
    published_at: datetime | None = None


class OutboxDTORead(BaseDto):
    id: int
    aggregate_type: AggregateType
    aggregate_id: uuid.UUID
    event_type: EventType
    payload: dict[str, Any]
    status: OutboxStatus
    webhook_status: WebhookStatus = WebhookStatus.PENDING
    retry_count: int
    last_error: str | None
    created_at: datetime
    published_at: datetime | None


class OutboxDTOList(BaseListDto):
    root: Sequence[OutboxDTORead]
