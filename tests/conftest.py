import os
import uuid
from collections.abc import AsyncGenerator
from urllib.parse import quote_plus

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

import payment_cookie_cute.db.engine as db_engine
from payment_cookie_cute.app import app as fastapi_app
from payment_cookie_cute.repositories import OutboxRepository, PaymentRepository
from payment_cookie_cute.router.dependencies.db import db_session

TEST_API_KEY = "test-api-key"

_driver = os.getenv("DATABASE_DRIVER", "postgresql+asyncpg")
_user = os.getenv("DATABASE_USERNAME", "postgres")
_password = quote_plus(os.getenv("DATABASE_PASSWORD", "postgres"))
_host = os.getenv("DATABASE_HOST", "test_db")
_port = os.getenv("DATABASE_PORT", "5432")
_name = os.getenv("DATABASE_NAME", "postgres_test")
DATABASE_URL = f"{_driver}://{_user}:{_password}@{_host}:{_port}/{_name}"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def engine() -> AsyncGenerator[AsyncEngine, None]:
    e = create_async_engine(DATABASE_URL, poolclass=NullPool)

    # ПАТЧИМ ГЛОБАЛЬНЫЙ ENGINE:
    # Если какой-то код импортирует async_session_factory напрямую (в обход DI),
    # он получит тестовый engine, а не продовый.
    db_engine.engine = e
    db_engine.async_session_factory = async_sessionmaker(e, expire_on_commit=False)

    yield e
    await e.dispose()


@pytest.fixture(autouse=True)
async def clean_db(engine: AsyncEngine) -> AsyncGenerator[None, None]:
    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE TABLE outbox, payments RESTART IDENTITY CASCADE"))
    yield
    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE TABLE outbox, payments RESTART IDENTITY CASCADE"))


@pytest.fixture
async def session(engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
        await s.rollback()


@pytest.fixture
async def second_session(engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
        await s.rollback()


@pytest.fixture
def payment_repo(session: AsyncSession) -> PaymentRepository:
    return PaymentRepository(session)


@pytest.fixture
def outbox_repo(session: AsyncSession) -> OutboxRepository:
    return OutboxRepository(session)


@pytest.fixture
async def app(engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PCC_API_KEY", TEST_API_KEY)
    from payment_cookie_cute.settings import get_settings

    get_settings.cache_clear()

    async def override_db_session():
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as s:
            try:
                yield s
                await s.commit()
            except Exception:
                await s.rollback()
                raise

    fastapi_app.dependency_overrides[db_session] = override_db_session
    yield fastapi_app
    fastapi_app.dependency_overrides.clear()
    get_settings.cache_clear()


@pytest.fixture
async def client(app) -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


@pytest.fixture
def auth_headers() -> dict[str, str]:
    return {"X-API-Key": TEST_API_KEY}


@pytest.fixture
def idempotency_headers(auth_headers: dict[str, str]) -> dict[str, str]:
    return {**auth_headers, "Idempotency-Key": str(uuid.uuid4())}
