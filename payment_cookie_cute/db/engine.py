from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from payment_cookie_cute.settings import (
    DatabaseSettings,
    get_settings,
)

engine = create_async_engine(
    get_settings(DatabaseSettings).url,
    pool_size=20,
    max_overflow=30,
    pool_timeout=50,
    pool_recycle=1800,
    pool_pre_ping=True,
    pool_use_lifo=False,
    echo=get_settings(DatabaseSettings).echo,
)


async_session_factory = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession,
    autoflush=False,
    autocommit=False,
)
