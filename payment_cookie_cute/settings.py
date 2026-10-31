from enum import StrEnum
from functools import lru_cache
from typing import (
    TypeVar,
)
from urllib.parse import quote_plus

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)

TSettings = TypeVar("TSettings", bound=BaseSettings)


class ProfileEnum(StrEnum):
    DEVELOPMENT = "development"
    PRODUCTION = "production"


@lru_cache
def get_settings(cls: type[TSettings]) -> TSettings:
    load_dotenv()
    return cls()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="pcc_")

    app_name: str = "Payment Cookie Cute API"
    port: int = 8000
    host: str = "0.0.0.0"
    workers: int = 4
    profile: ProfileEnum = ProfileEnum.DEVELOPMENT
    allow_origin: str = "http://localhost"
    allow_credentials: bool = True
    allow_headers: str = "*"
    api_key: str = Field(..., min_length=8)
    webhook_timeout: int = 10
    webhook_max_retries: int = 3

    @property
    def is_prod(self):
        return self.profile == ProfileEnum.PRODUCTION

    @property
    def allow_origin_list(self) -> list[str]:
        return self.allow_origin.split(",")

    @property
    def cookie_domain(self) -> str | None:
        if self.is_prod:
            return self.auth_domain
        return None


class QueueSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="rabbitmq_")

    host: str = "lynkey_rabbitmq"
    user: str = "test-user"
    password: str = "test-user"
    port: str = "5672"

    event_queue_name: str = "payments.new"
    event_wh_queue_name: str = "payments.new.wh"
    retry_event_queue_name: str = "payments.new.retry"
    retry_wh_event_queue_name: str = "payments.new.wh.retry"
    dlq_event_queue_name: str = "payments.new.dlq"
    retry_ttl: int = 60

    @property
    def rabbitmq_url(self) -> str:
        return f"amqp://{self.user}:{self.password}@{self.host}:{self.port}/"


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="database_")

    driver: str = "postgresql+asyncpg"
    name: str = "postgres"
    username: str = "postgres"
    password: str = "postgres"
    host: str = "127.0.0.1"
    port: str = "5432"
    echo: bool = False

    @property
    def url(self) -> str:
        password = quote_plus(self.password)
        return f"{self.driver}://{self.username}:{password}@{self.host}:{self.port}/{self.name}"
