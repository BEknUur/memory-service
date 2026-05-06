#python imports
from typing import Annotated

#third-party imports
from fastapi import APIRouter, Depends

#project imports
from memory_service.api.deps import get_search_service
from memory_service.schemas.search import SearchRequest, SearchResponse
from memory_service.services.search import SearchService
from memory_service.utils.auth import require_auth

router = APIRouter(tags=["search"], dependencies=[Depends(require_auth)])


@router.post("/search", response_model=SearchResponse)
async def search(
    payload: SearchRequest,
    service: Annotated[SearchService, Depends(get_search_service)],
) -> SearchResponse:
    return await service.search(payload)
