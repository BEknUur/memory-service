#python imports
from functools import lru_cache

#third-party imports
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

#project imports


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    port: int = Field(default=8080, alias="PORT")
    database_url: str = Field(
        default="postgresql+asyncpg://memory:memory@localhost:5432/memory",
        alias="DATABASE_URL",
    )
    memory_auth_token: str | None = Field(default=None, alias="MEMORY_AUTH_TOKEN")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_extract_model: str = Field(default="gpt-5-mini", alias="OPENAI_EXTRACT_MODEL")


@lru_cache
def get_settings() -> Settings:
    return Settings()
