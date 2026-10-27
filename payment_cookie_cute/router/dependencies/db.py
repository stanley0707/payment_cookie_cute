from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from payment_cookie_cute.db.engine import async_session_factory


async def db_session() -> AsyncGenerator[AsyncSession]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except:
            await session.rollback()
            raise
