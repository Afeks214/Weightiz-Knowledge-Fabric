"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-30
"""

from alembic import op

from wzkf.db.models import metadata

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    metadata.create_all(op.get_bind())


def downgrade() -> None:
    metadata.drop_all(op.get_bind())
