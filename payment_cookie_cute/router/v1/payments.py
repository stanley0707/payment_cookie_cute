import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, status

from payment_cookie_cute.dto import PaymentDTO, PaymentDTORead
from payment_cookie_cute.router.dependencies.services import get_payment_service
from payment_cookie_cute.services.payment import PaymentService

payments_router = APIRouter(
    prefix="/payments",
    tags=["payments"],
)


@payments_router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=PaymentDTORead,
    summary="Создать платёж",
    description=(
        "Создаёт платёж и ставит событие `payment.created` в outbox. "
        "Атомарно: либо и платёж, и событие, либо ничего. "
        "Требует `Idempotency-Key` для защиты от дублей."
    ),
)
async def create_payment(
    data: PaymentDTO,
    idempotency_key: str = Header(
        ...,
        alias="Idempotency-Key",
        min_length=1,
        max_length=255,
    ),
    service: PaymentService = Depends(get_payment_service),
) -> PaymentDTORead:
    return await service.create(data, idempotency_key)


@payments_router.get(
    "/{payment_id}",
    response_model=PaymentDTORead,
    summary="Получить платёж",
    responses={
        404: {"description": "Платёж не найден"},
    },
)
async def get_payment(
    payment_id: uuid.UUID,
    service: PaymentService = Depends(get_payment_service),
) -> PaymentDTORead:
    payment = await service.get(payment_id)
    if payment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Payment {payment_id} not found",
        )
    return payment
