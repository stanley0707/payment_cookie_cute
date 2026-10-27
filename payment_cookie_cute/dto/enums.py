from enum import StrEnum


class OutboxStatus(StrEnum):
    PENDING = "pending"
    PUBLISHED = "published"
    FAILED = "failed"


class Currency(StrEnum):
    RUB = "RUB"
    USD = "USD"
    EUR = "EUR"


class PaymentStatus(StrEnum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILURE = "failure"


class AggregateType(StrEnum):
    PAYMENT = "payment"
    REFUND = "refund"
    WEBHOOK = "webhook"


class EventType(StrEnum):
    PAYMENT_CREATED = "payment.created"
    PAYMENT_SUCCEEDED = "payment.succeeded"
    PAYMENT_FAILED = "payment.failed"
    REFUND_ISSUED = "refund.issued"
    WEBHOOK_SENT = "webhook.sent"
