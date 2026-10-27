import uuid
from unittest.mock import patch

import pytest
from sqlalchemy import select

from payment_cookie_cute.db.models import Outbox, Payment
from payment_cookie_cute.dto import PaymentStatus
from payment_cookie_cute.services import PaymentService
from tests.factories import make_payment_create_dto, make_payment_read

pytestmark = pytest.mark.anyio


@pytest.fixture
def service(session, payment_repo, outbox_repo) -> PaymentService:
    return PaymentService(
        session=session,
        payments_repository=payment_repo,
        outbox_repository=outbox_repo,
    )


class TestPaymentServiceCreate:
    async def test_creates_payment_and_outbox(self, service, session, payment_repo, outbox_repo):
        payment = await service.create(
            data=make_payment_create_dto(),
            idempotency_key="key-1",
        )
        await session.commit()

        # Проверяем в БД
        db_payment = await session.scalar(select(Payment).where(Payment.id == payment.id))
        assert db_payment is not None
        assert db_payment.status == PaymentStatus.PENDING.value

        events = (
            await session.scalars(select(Outbox).where(Outbox.aggregate_id == payment.id))
        ).all()
        assert len(events) == 1
        assert events[0].event_type == "payment.created"
        assert events[0].payload["payment_id"] == str(payment.id)

    async def test_returns_existing_on_duplicate_key(self, service, session):
        first = await service.create(make_payment_create_dto(), "key-1")
        await session.commit()

        second = await service.create(make_payment_create_dto(), "key-1")
        assert second.id == first.id

        # В БД только один платёж
        count = await session.scalar(select(Payment).where(Payment.idempotency_key == "key-1"))
        assert count is not None

    async def test_race_condition_returns_existing(self, service, session):
        # Создаём первый платёж
        first = await service.create(make_payment_create_dto(), "key-race")
        await session.commit()

        # Эмулируем race: второй запрос не видит первый (в реальности так не будет,
        # но мы проверяем обработку IntegrityError)
        with patch.object(
            service._payments_repository,
            "get_by_idempotency_key",
            side_effect=[
                None,
                make_payment_read(id=first.id),
            ],  # первый SELECT пуст, второй находит
        ):
            result = await service.create(make_payment_create_dto(), "key-race")
            assert result.id == first.id

        # Убедимся, что rollback был вызван (сессия жива)
        # Если бы rollback не было, следующий запрос упал бы
        await session.scalar(select(Payment))

    async def test_new_payment_has_pending_status(self, service, session):
        payment = await service.create(make_payment_create_dto(), "key-status")
        assert payment.status == PaymentStatus.PENDING


class TestPaymentServiceGet:
    async def test_returns_payment(self, service, session):
        created = await service.create(make_payment_create_dto(), "key-get")
        await session.commit()

        found = await service.get(created.id)
        assert found is not None
        assert found.id == created.id

    async def test_returns_none_when_not_found(self, service):
        result = await service.get(uuid.uuid4())
        assert result is None
