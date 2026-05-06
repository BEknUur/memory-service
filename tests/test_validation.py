from memory_service.config import Settings
from memory_service.db.session import get_session


def test_settings_read_environment(monkeypatch):
    monkeypatch.setenv("PORT", "9090")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost:5432/test")
    monkeypatch.setenv("MEMORY_AUTH_TOKEN", "secret")

    settings = Settings(_env_file=None)

    assert settings.port == 9090
    assert settings.database_url == "postgresql+asyncpg://u:p@localhost:5432/test"
    assert settings.memory_auth_token == "secret"


def test_db_session_dependency_is_importable():
    assert callable(get_session)
