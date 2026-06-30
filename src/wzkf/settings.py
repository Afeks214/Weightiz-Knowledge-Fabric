from pathlib import Path

from pydantic import BaseModel


class Settings(BaseModel):
    storage_root: Path = Path("data")
    obsidian_export_root: Path = Path("data/obsidian_export")
    database_url: str = "postgresql+psycopg://wzkf:wzkf@localhost:5432/wzkf"
    redis_url: str = "redis://localhost:6379/0"
    embedding_provider: str = "mock"
