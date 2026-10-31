from typing import Any, Generic, TypeVar

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from payment_cookie_cute.db.base import Base

Model = TypeVar("Model", bound=Base)
DTO = TypeVar("DTO")
READ_DTO = TypeVar("READ_DTO")
LIST_DTO = TypeVar("LIST_DTO")


class BaseRepository(Generic[Model, DTO, READ_DTO, LIST_DTO]):
    model: type[Model]
    dto: type[DTO]
    read_dto: type[READ_DTO]
    list_dto: type[LIST_DTO]

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(
        self,
        pk: Any,
        *,
        for_update: bool = False,
        skip_locked: bool = False,
    ) -> READ_DTO | None:
        model = await self._get_model(
            pk,
            for_update=for_update,
            skip_locked=skip_locked,
        )
        return self.read_dto.model_validate(model) if model else None

    async def get_by(
        self,
        *exprs: ColumnElement[bool],
        for_update: bool = False,
        skip_locked: bool = False,
    ) -> READ_DTO | None:
        model = await self._get_by_model(
            *exprs,
            for_update=for_update,
            skip_locked=skip_locked,
        )
        return self.read_dto.model_validate(model) if model else None

    async def filter_by(
        self,
        *exprs: ColumnElement[bool],
        limit: int | None = None,
        for_update: bool = False,
        skip_locked: bool = False,
    ) -> LIST_DTO:
        models = await self._filter_models(
            *exprs,
            limit=limit,
            for_update=for_update,
            skip_locked=skip_locked,
        )
        return self.list_dto.model_validate(models)

    async def update_by(
        self, *expression: ColumnElement[bool], data: dict[str, Any]
    ) -> READ_DTO | None:
        if len(data):
            res = await self._session.execute(
                update(self.model).where(*expression).values(**data).returning(self.model)
            )
            if res := res.scalar():
                await self._session.flush()
                await self._session.refresh(res)
                return res  # type: ignore[no-any-return]
        return None

    async def create(self, **values: Any) -> READ_DTO:
        model = await self._create_model(**values)
        return self.read_dto.model_validate(model)

    async def update(self, pk: Any, **values: Any) -> READ_DTO | None:
        model = await self._update_model(pk, **values)
        return self.read_dto.model_validate(model) if model else None

    async def delete(self, pk: Any) -> None:
        stmt = delete(self.model).where(self.model.id == pk)  # type: ignore[attr-defined]
        await self._session.execute(stmt)
        await self._session.flush()

    async def _get_model(
        self,
        pk: Any,
        *,
        for_update: bool = False,
        skip_locked: bool = False,
    ) -> Model | None:
        stmt = select(self.model).where(self.model.id == pk)  # type: ignore[attr-defined]
        if for_update:
            stmt = stmt.with_for_update(skip_locked=skip_locked)
        return await self._session.scalar(stmt)

    async def _get_by_model(
        self,
        *exprs: ColumnElement[bool],
        for_update: bool = False,
        skip_locked: bool = False,
    ) -> Model | None:
        stmt = select(self.model).where(*exprs)
        if for_update:
            stmt = stmt.with_for_update(skip_locked=skip_locked)
        return await self._session.scalar(stmt)

    async def _filter_models(
        self,
        *exprs: ColumnElement[bool],
        limit: int | None = None,
        for_update: bool = False,
        skip_locked: bool = False,
    ) -> list[Model]:
        stmt = select(self.model).where(*exprs)
        if for_update:
            stmt = stmt.with_for_update(skip_locked=skip_locked)
        if limit is not None:
            stmt = stmt.limit(limit)
        return list((await self._session.scalars(stmt)).all())

    async def _create_model(self, **values: Any) -> Model:
        model = self.model(**values)
        self._session.add(model)
        await self._session.flush()
        return model

    async def _update_model(self, pk: Any, **values: Any) -> Model | None:
        stmt = (
            update(self.model)
            .where(self.model.id == pk)  # type: ignore[attr-defined]
            .values(**values)
            .returning(self.model)
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        if model is not None:
            await self._session.flush()
        return model
