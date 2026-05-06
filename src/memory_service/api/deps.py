#python imports
from typing import Annotated

#third-party imports
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

#project imports
from memory_service.db.session import get_session
from memory_service.services.memories import MemoryService
from memory_service.services.recall import RecallService
from memory_service.services.search import SearchService
from memory_service.services.turns import TurnService


async def get_turn_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TurnService:
    return TurnService(session)


async def get_memory_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> MemoryService:
    return MemoryService(session)


async def get_recall_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> RecallService:
    return RecallService(session)


async def get_search_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SearchService:
    return SearchService(session)
