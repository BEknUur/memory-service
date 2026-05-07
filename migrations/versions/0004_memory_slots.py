"""canonical memory slots

Revision ID: 0004_memory_slots
Revises: 0003_active_slots
Create Date: 2026-05-07 00:00:00.000000
"""


#third-party imports
import sqlalchemy as sa
from alembic import op

revision = "0004_memory_slots"
down_revision = "0003_active_slots"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("memories", sa.Column("slot", sa.String(length=255), nullable=True))
    op.execute("UPDATE memories SET slot = key")
    op.alter_column("memories", "slot", nullable=False)

    op.drop_index("uq_memories_active_user_key", table_name="memories")
    op.drop_index("uq_memories_active_session_key", table_name="memories")
    op.drop_index("ix_memories_user_key_active", table_name="memories")
    op.drop_index("ix_memories_session_key_active", table_name="memories")

    op.create_index(
        "uq_memories_active_user_key",
        "memories",
        ["user_id", "slot"],
        unique=True,
        postgresql_where=sa.text("active = true AND user_id IS NOT NULL"),
    )
    op.create_index(
        "uq_memories_active_session_key",
        "memories",
        ["session_id", "slot"],
        unique=True,
        postgresql_where=sa.text("active = true AND user_id IS NULL"),
    )
    op.create_index(
        "ix_memories_user_slot_active",
        "memories",
        ["user_id", "slot", "active"],
    )
    op.create_index(
        "ix_memories_session_slot_active",
        "memories",
        ["session_id", "slot", "active"],
    )


def downgrade() -> None:
    op.drop_index("ix_memories_session_slot_active", table_name="memories")
    op.drop_index("ix_memories_user_slot_active", table_name="memories")
    op.drop_index("uq_memories_active_session_key", table_name="memories")
    op.drop_index("uq_memories_active_user_key", table_name="memories")

    op.create_index(
        "uq_memories_active_user_key",
        "memories",
        ["user_id", "key"],
        unique=True,
        postgresql_where=sa.text("active = true AND user_id IS NOT NULL"),
    )
    op.create_index(
        "uq_memories_active_session_key",
        "memories",
        ["session_id", "key"],
        unique=True,
        postgresql_where=sa.text("active = true AND user_id IS NULL"),
    )
    op.create_index(
        "ix_memories_user_key_active",
        "memories",
        ["user_id", "key", "active"],
    )
    op.create_index(
        "ix_memories_session_key_active",
        "memories",
        ["session_id", "key", "active"],
    )
    op.drop_column("memories", "slot")
