import secrets

from fastapi import (
    HTTPException,
    status,
)

from payment_cookie_cute.settings import (
    Settings,
    get_settings,
)


class SecureService:
    @staticmethod
    def verify_token(api_key: str) -> None | HTTPException:
        if not api_key or not secrets.compare_digest(api_key, get_settings(Settings).api_key):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing X-API-Key header",
                headers={"WWW-Authenticate": "ApiKey"},
            )
