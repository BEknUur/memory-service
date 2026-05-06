#python imports
from collections.abc import AsyncIterator

#third-party imports
import pytest
from httpx import ASGITransport, AsyncClient

#project imports
from memory_service.main import create_app


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client
