import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy_utils import ChoiceType

from alembic import context
from payment_cookie_cute.db import models  # noqa: F401
from payment_cookie_cute.db.base import Base
from payment_cookie_cute.settings import (
    DatabaseSettings,
    get_settings,
)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def render_item(type_, obj, autogen_context):
    if type_ == "type" and isinstance(obj, ChoiceType):
        length = getattr(obj.impl, "length", None) or 255
        autogen_context.imports.add("import sqlalchemy as sa")
        return f"sa.String(length={length})"

    return False


def run_migrations_offline() -> None:
    """SQL Builder db connections less"""
    context.configure(
        url=get_settings(DatabaseSettings).url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_item=render_item,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        render_item=render_item,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = create_async_engine(get_settings(DatabaseSettings).url, poolclass=pool.NullPool)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
