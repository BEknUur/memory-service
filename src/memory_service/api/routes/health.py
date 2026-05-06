from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from memory_service.db.session import check_database

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> JSONResponse:
    if await check_database():
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"status": "ok", "database": "ok"},
        )

    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"status": "degraded", "database": "error"},
    )
