from fastapi import APIRouter

from payment_cookie_cute.router.v1 import api_v1_router

api_router = APIRouter(prefix="/api")
api_router.include_router(api_v1_router)
