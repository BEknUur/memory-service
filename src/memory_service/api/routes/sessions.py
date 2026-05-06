#python imports
from typing import Annotated

#third-party imports
from fastapi import APIRouter, Depends, Response, status

#project imports
from memory_service.api.deps import get_turn_service
from memory_service.services.turns import TurnService
from memory_service.utils.auth import require_auth

router = APIRouter(tags=["sessions"], dependencies=[Depends(require_auth)])


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: str,
    service: Annotated[TurnService, Depends(get_turn_service)],
) -> Response:
    await service.delete_session(session_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
