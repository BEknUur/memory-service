#python imports

#third-party imports

#project imports
from memory_service.schemas.recall import RecallRequest, RecallResponse


class RecallService:
    async def recall(self, _: RecallRequest) -> RecallResponse:
        return RecallResponse(context="", citations=[])
