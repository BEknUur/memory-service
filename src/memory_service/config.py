from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    port: int = Field(default=8080, alias="PORT")
    database_url: str = Field(
        default="postgresql+asyncpg://memory:memory@localhost:5432/memory",
        alias="DATABASE_URL",
    )
    memory_auth_token: str | None = Field(default=None, alias="MEMORY_AUTH_TOKEN")


@lru_cache
def get_settings() -> Settings:
    return Settings()
