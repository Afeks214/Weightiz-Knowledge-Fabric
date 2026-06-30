"""live MVP schema compatibility

Revision ID: 0002_live_mvp_schema
Revises: 0001_initial
Create Date: 2026-06-30
"""

from alembic import op
from sqlalchemy import inspect

revision = "0002_live_mvp_schema"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    table_names = set(inspector.get_table_names())
    if "processing_jobs" in table_names and "jobs" not in table_names:
        op.rename_table("processing_jobs", "jobs")
    table_names = set(inspect(bind).get_table_names())
    if "cost_ledger" in table_names and "costs" not in table_names:
        op.rename_table("cost_ledger", "costs")

    columns = {column["name"] for column in inspect(bind).get_columns("embeddings")}
    if "embedding_vector" not in columns:
        op.execute("ALTER TABLE embeddings ADD COLUMN embedding_vector vector")


def downgrade() -> None:
    bind = op.get_bind()
    table_names = set(inspect(bind).get_table_names())

    columns = {column["name"] for column in inspect(bind).get_columns("embeddings")}
    if "embedding_vector" in columns:
        op.execute("ALTER TABLE embeddings DROP COLUMN embedding_vector")
    if "costs" in table_names and "cost_ledger" not in table_names:
        op.rename_table("costs", "cost_ledger")
    table_names = set(inspect(bind).get_table_names())
    if "jobs" in table_names and "processing_jobs" not in table_names:
        op.rename_table("jobs", "processing_jobs")
