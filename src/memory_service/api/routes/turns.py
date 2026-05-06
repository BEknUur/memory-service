#python imports
from typing import Annotated

#third-party imports
from fastapi import APIRouter, Depends, status

#project imports
from memory_service.api.deps import get_turn_service
from memory_service.schemas.turns import TurnCreate, TurnCreated
from memory_service.services.turns import TurnService
from memory_service.utils.auth import require_auth

router = APIRouter(tags=["turns"], dependencies=[Depends(require_auth)])


@router.post("/turns", response_model=TurnCreated, status_code=status.HTTP_201_CREATED)
async def create_turn(
    payload: TurnCreate,
    service: Annotated[TurnService, Depends(get_turn_service)],
) -> TurnCreated:
    turn_id = await service.create_turn(payload)
    return TurnCreated(id=str(turn_id))
