from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from payment_cookie_cute.repositories import OutboxRepository, PaymentRepository
from payment_cookie_cute.router.dependencies import (
    get_outbox_repository,
    get_payment_repository,
)
from payment_cookie_cute.router.dependencies.db import db_session
from payment_cookie_cute.services import PaymentService


async def get_payment_service(
    session: AsyncSession = Depends(db_session),
    payment_repository: PaymentRepository = Depends(get_payment_repository),
    outbox_repository: OutboxRepository = Depends(get_outbox_repository),
) -> PaymentService:
    return PaymentService(
        session=session,
        outbox_repository=outbox_repository,
        payments_repository=payment_repository,
    )
