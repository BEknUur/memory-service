from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from memory_service.api.deps import get_memory_service, get_turn_service
from memory_service.schemas.memories import UserMemoriesResponse
from memory_service.services.memories import MemoryService
from memory_service.services.turns import TurnService
from memory_service.utils.auth import require_auth

router = APIRouter(tags=["users"], dependencies=[Depends(require_auth)])


@router.get("/users/{user_id}/memories", response_model=UserMemoriesResponse)
async def list_user_memories(
    user_id: str,
    service: Annotated[MemoryService, Depends(get_memory_service)],
) -> UserMemoriesResponse:
    memories = await service.list_user_memories(user_id)
    return UserMemoriesResponse(memories=memories)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: str,
    service: Annotated[TurnService, Depends(get_turn_service)],
) -> Response:
    await service.delete_user(user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
