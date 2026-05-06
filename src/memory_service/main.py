#python imports
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

#third-party imports
from fastapi import FastAPI

#project imports
from memory_service.api.routes.health import router as health_router
from memory_service.api.routes.recall import router as recall_router
from memory_service.api.routes.search import router as search_router
from memory_service.api.routes.sessions import router as sessions_router
from memory_service.api.routes.turns import router as turns_router
from memory_service.api.routes.users import router as users_router
from memory_service.db.migrations import run_migrations
from memory_service.db.session import engine


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # Engine construction is intentionally eager so DB config errors surface on boot.
    _ = engine
    await run_migrations()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Memory Service", lifespan=lifespan)
    app.include_router(health_router)
    app.include_router(turns_router)
    app.include_router(recall_router)
    app.include_router(search_router)
    app.include_router(users_router)
    app.include_router(sessions_router)
    return app


app = create_app()
