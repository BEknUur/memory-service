"""enable pgvector

Revision ID: 0001_enable_pgvector
Revises:
Create Date: 2026-05-06 00:00:00.000000
"""



#third-party imports
from alembic import op

revision = "0001_enable_pgvector"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS vector")
