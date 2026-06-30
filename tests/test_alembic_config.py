from wzkf.db.alembic_config import resolve_alembic_database_url


def test_resolve_alembic_database_url_prefers_environment_database_url():
    assert (
        resolve_alembic_database_url(
            "postgresql+psycopg://wzkf:wzkf@localhost:5432/wzkf",
            {"DATABASE_URL": "postgresql+psycopg://wzkf:wzkf@localhost:5432/wzkf_live_smoke"},
        )
        == "postgresql+psycopg://wzkf:wzkf@localhost:5432/wzkf_live_smoke"
    )


def test_resolve_alembic_database_url_falls_back_to_ini_value():
    assert (
        resolve_alembic_database_url(
            "postgresql+psycopg://wzkf:wzkf@localhost:5432/wzkf",
            {},
        )
        == "postgresql+psycopg://wzkf:wzkf@localhost:5432/wzkf"
    )
