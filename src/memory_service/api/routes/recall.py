#python imports
from typing import Annotated

#third-party imports
from fastapi import APIRouter, Depends

#project imports
from memory_service.api.deps import get_recall_service
from memory_service.schemas.recall import RecallRequest, RecallResponse
from memory_service.services.recall import RecallService
from memory_service.utils.auth import require_auth

router = APIRouter(tags=["recall"], dependencies=[Depends(require_auth)])


@router.post("/recall", response_model=RecallResponse)
async def recall(
    payload: RecallRequest,
    service: Annotated[RecallService, Depends(get_recall_service)],
) -> RecallResponse:
    return await service.recall(payload)
