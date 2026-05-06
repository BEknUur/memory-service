#python imports
from asyncio import to_thread
from pathlib import Path

#third-party imports
from alembic import command
from alembic.config import Config

#project imports
from memory_service.config import get_settings


def _build_alembic_config() -> Config:
    project_root = Path(__file__).resolve().parents[3]
    config = Config(str(project_root / "alembic.ini"))
    config.set_main_option("script_location", str(project_root / "migrations"))
    config.set_main_option("sqlalchemy.url", get_settings().database_url)
    return config


async def run_migrations() -> None:
    await to_thread(command.upgrade, _build_alembic_config(), "head")
