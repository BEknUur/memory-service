from fastapi import status
from fastapi.testclient import TestClient

from memory_service.main import create_app


def test_health_returns_ok_when_database_is_reachable(monkeypatch):
    async def fake_check_database() -> bool:
        return True

    monkeypatch.setattr("memory_service.api.routes.health.check_database", fake_check_database)

    with TestClient(create_app()) as client:
        response = client.get("/health")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "ok", "database": "ok"}


def test_health_returns_degraded_when_database_is_unreachable(monkeypatch):
    async def fake_check_database() -> bool:
        return False

    monkeypatch.setattr("memory_service.api.routes.health.check_database", fake_check_database)

    with TestClient(create_app()) as client:
        response = client.get("/health")

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.json() == {"status": "degraded", "database": "error"}
