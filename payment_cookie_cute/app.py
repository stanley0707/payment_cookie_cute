from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from payment_cookie_cute.router.router import api_router
from payment_cookie_cute.settings import (
    Settings,
    get_settings,
)

app = FastAPI(
    title=get_settings(Settings).app_name,
    redoc_url=None if get_settings(Settings).is_prod else "/redoc",
    docs_url=None if get_settings(Settings).is_prod else "/docs",
    openapi_url=None if get_settings(Settings).is_prod else "/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings(Settings).allow_origin_list,
    allow_credentials=get_settings(Settings).allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/alive")
async def check():
    return "alive"


app.include_router(api_router)

if __name__ == "__main__":
    import uvicorn

    settings = get_settings(Settings)
    uvicorn.run(
        "lynkey_head.app:app",
        host=settings.host,
        port=settings.port,
        workers=settings.workers,
    )
