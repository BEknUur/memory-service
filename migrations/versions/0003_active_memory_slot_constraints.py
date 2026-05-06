"""active memory slot constraints

Revision ID: 0003_active_memory_slot_constraints
Revises: 0002_core_memory_schema
Create Date: 2026-05-06 00:00:00.000000
"""

from alembic import op

revision = "0003_active_memory_slot_constraints"
down_revision = "0002_core_memory_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "uq_memories_active_user_key",
        "memories",
        ["user_id", "key"],
        unique=True,
        postgresql_where="active = true AND user_id IS NOT NULL",
    )
    op.create_index(
        "uq_memories_active_session_key",
        "memories",
        ["session_id", "key"],
        unique=True,
        postgresql_where="active = true AND user_id IS NULL",
    )


def downgrade() -> None:
    op.drop_index("uq_memories_active_session_key", table_name="memories")
    op.drop_index("uq_memories_active_user_key", table_name="memories")
