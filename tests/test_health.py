from fastapi import status


async def test_health_returns_ok_when_database_is_reachable(client, monkeypatch):
    async def fake_check_database() -> bool:
        return True

    monkeypatch.setattr("memory_service.api.routes.health.check_database", fake_check_database)

    response = await client.get("/health")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "ok", "database": "ok"}


async def test_health_returns_degraded_when_database_is_unreachable(client, monkeypatch):
    async def fake_check_database() -> bool:
        return False

    monkeypatch.setattr("memory_service.api.routes.health.check_database", fake_check_database)

    response = await client.get("/health")

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.json() == {"status": "degraded", "database": "error"}
