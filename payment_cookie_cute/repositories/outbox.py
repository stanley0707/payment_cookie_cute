from sqlalchemy import (
    func,
    select,
    update,
)

from payment_cookie_cute.core import BaseRepository
from payment_cookie_cute.db.models import Outbox
from payment_cookie_cute.dto import (
    OutboxDTO,
    OutboxDTOList,
    OutboxDTORead,
    OutboxStatus,
)


class OutboxRepository(
    BaseRepository[
        Outbox,
        OutboxDTO,
        OutboxDTORead,
        OutboxDTOList,
    ]
):
    dto = OutboxDTO
    read_dto = OutboxDTORead
    list_dto = OutboxDTOList
    model = Outbox

    async def fetch_pending(self, limit: int = 100) -> OutboxDTOList:
        stmt = (
            select(self.model)
            .where(self.model.status == OutboxStatus.PENDING)
            .order_by(self.model.id)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        models = (await self._session.scalars(stmt)).all()
        return self.list_dto.model_validate(models)

    async def mark_published(self, outbox_id: int) -> None:
        stmt = (
            update(self.model)
            .where(self.model.id == outbox_id)
            .values(
                status=OutboxStatus.PUBLISHED,
                published_at=func.now(),
            )
        )
        await self._session.execute(stmt)

    async def mark_failed(self, outbox_id: int, error: str) -> None:
        stmt = (
            update(self.model)
            .where(self.model.id == outbox_id)
            .values(
                status=OutboxStatus.FAILED,
                last_error=error[:2048],
            )
        )
        await self._session.execute(stmt)

    async def increment_retry(self, outbox_id: int, error: str) -> int:
        stmt = (
            update(self.model)
            .where(self.model.id == outbox_id)
            .values(
                retry_count=self.model.retry_count + 1,
                last_error=error[:2048],
            )
            .returning(self.model.retry_count)
        )
        return (await self._session.execute(stmt)).scalar_one()
