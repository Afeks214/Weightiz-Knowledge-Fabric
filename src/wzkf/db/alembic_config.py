from __future__ import annotations

from collections.abc import Mapping


def resolve_alembic_database_url(config_url: str | None, environ: Mapping[str, str]) -> str:
    database_url = (environ.get("DATABASE_URL") or "").strip()
    if database_url:
        return database_url
    if config_url:
        return config_url
    raise ValueError("Alembic requires sqlalchemy.url or DATABASE_URL")
