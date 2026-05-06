#python imports

#third-party imports

#project imports
from memory_service.schemas.search import SearchRequest, SearchResponse


class SearchService:
    async def search(self, _: SearchRequest) -> SearchResponse:
        return SearchResponse(results=[])
