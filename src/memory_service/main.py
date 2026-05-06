from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from memory_service.api.routes.health import router as health_router
from memory_service.db.session import engine


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # Engine construction is intentionally eager so DB config errors surface on boot.
    _ = engine
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Memory Service", lifespan=lifespan)
    app.include_router(health_router)
    return app


app = create_app()
