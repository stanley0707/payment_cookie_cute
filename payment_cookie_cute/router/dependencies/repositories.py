from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from payment_cookie_cute.repositories import (
    OutboxRepository,
    PaymentRepository,
)
from payment_cookie_cute.router.dependencies.db import db_session


async def get_payment_repository(
    session: AsyncSession = Depends(db_session),
) -> PaymentRepository:
    return PaymentRepository(session)


async def get_outbox_repository(
    session: AsyncSession = Depends(db_session),
) -> OutboxRepository:
    return OutboxRepository(session)
