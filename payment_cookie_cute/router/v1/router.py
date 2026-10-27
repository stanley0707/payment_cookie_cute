from fastapi import APIRouter, Depends

from payment_cookie_cute.router.dependencies import verify_api_key
from payment_cookie_cute.router.v1.payments import payments_router

api_v1_router = APIRouter(
    prefix="/v1",
    dependencies=[Depends(verify_api_key)],
)


api_v1_router.include_router(payments_router)
