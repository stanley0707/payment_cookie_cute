from fastapi import Security
from fastapi.security import APIKeyHeader

from payment_cookie_cute.services import SecureService

api_key_header = APIKeyHeader(
    name="X-API-Key",
    auto_error=False,
)


async def verify_api_key(
    api_key: str | None = Security(api_key_header),  # твой lru_cache-провайдер
) -> None:
    return SecureService().verify_token(api_key)
