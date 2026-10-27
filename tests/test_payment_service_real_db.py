import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from payment_cookie_cute.db.models import Outbox, Payment
from payment_cookie_cute.repositories import OutboxRepository
from tests.factories import make_payment_create_dto

pytestmark = pytest.mark.anyio


class TestAtomicity:
    async def test_payment_and_outbox_created_together(self, session, payment_repo, outbox_repo):
        from payment_cookie_cute.services import PaymentService

        service = PaymentService(session, payment_repo, outbox_repo)
        payment = await service.create(make_payment_create_dto(), "key-1")
        await session.commit()

        db_payment = await session.scalar(select(Payment).where(Payment.id == payment.id))
        assert db_payment is not None

        events = (
            await session.scalars(select(Outbox).where(Outbox.aggregate_id == payment.id))
        ).all()
        assert len(events) == 1
        assert events[0].event_type == "payment.created"

    async def test_unique_idempotency_key_raises(self, session):
        session.add(
            Payment(
                id=uuid.uuid4(),
                amount=100,
                currency="RUB",
                meta={},
                status="pending",
                idempotency_key="same-key",
                webhook_url="https://example.com/wh",
            )
        )
        await session.commit()

        session.add(
            Payment(
                id=uuid.uuid4(),
                amount=200,
                currency="USD",
                meta={},
                status="pending",
                idempotency_key="same-key",
                webhook_url="https://example.com/wh",
            )
        )
        with pytest.raises(IntegrityError):
            await session.flush()
        await session.rollback()

    async def test_outbox_skips_locked_rows(self, session, second_session):
        from payment_cookie_cute.db.models import Outbox

        for i in range(5):
            session.add(
                Outbox(
                    aggregate_type="payment",
                    aggregate_id=uuid.uuid4(),
                    event_type="payment.created",
                    payload={"n": i},
                    status="pending",
                )
            )
        await session.commit()

        repo1 = OutboxRepository(session)
        repo2 = OutboxRepository(second_session)

        async with session.begin():
            batch1 = await repo1.fetch_pending(limit=10)
            async with second_session.begin():
                batch2 = await repo2.fetch_pending(limit=10)

            ids1 = {e.id for e in batch1}
            ids2 = {e.id for e in batch2}
            assert ids1.isdisjoint(ids2), "Оба relay схватили одни и те же строки!"
            assert len(ids1) + len(ids2) == 5
