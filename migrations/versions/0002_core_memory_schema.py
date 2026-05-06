"""core memory schema

Revision ID: 0002_core_memory_schema
Revises: 0001_enable_pgvector
Create Date: 2026-05-06 00:00:00.000000
"""


#third-party imports
import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision = "0002_core_memory_schema"
down_revision = "0001_enable_pgvector"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "turns",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", sa.String(length=255), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=True),
        sa.Column("messages", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_turns_session_id", "turns", ["session_id"])
    op.create_index("ix_turns_user_id", "turns", ["user_id"])

    op.create_table(
        "memories",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=True),
        sa.Column("session_id", sa.String(length=255), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("confirmation_count", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("supersedes_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("superseded_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("embedding", Vector(dim=1536), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("last_confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["superseded_by_id"], ["memories.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["supersedes_id"], ["memories.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_memories_active", "memories", ["active"])
    op.create_index("ix_memories_created_at", "memories", ["created_at"])
    op.create_index("ix_memories_key", "memories", ["key"])
    op.create_index("ix_memories_session_id", "memories", ["session_id"])
    op.create_index("ix_memories_session_key_active", "memories", ["session_id", "key", "active"])
    op.create_index("ix_memories_user_id", "memories", ["user_id"])
    op.create_index("ix_memories_user_key_active", "memories", ["user_id", "key", "active"])

    op.create_table(
        "memory_evidence",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("memory_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("turn_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quote", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["memory_id"], ["memories.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["turn_id"], ["turns.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_memory_evidence_memory_id", "memory_evidence", ["memory_id"])
    op.create_index("ix_memory_evidence_turn_id", "memory_evidence", ["turn_id"])


def downgrade() -> None:
    op.drop_index("ix_memory_evidence_turn_id", table_name="memory_evidence")
    op.drop_index("ix_memory_evidence_memory_id", table_name="memory_evidence")
    op.drop_table("memory_evidence")

    op.drop_index("ix_memories_user_key_active", table_name="memories")
    op.drop_index("ix_memories_user_id", table_name="memories")
    op.drop_index("ix_memories_session_key_active", table_name="memories")
    op.drop_index("ix_memories_session_id", table_name="memories")
    op.drop_index("ix_memories_key", table_name="memories")
    op.drop_index("ix_memories_created_at", table_name="memories")
    op.drop_index("ix_memories_active", table_name="memories")
    op.drop_table("memories")

    op.drop_index("ix_turns_user_id", table_name="turns")
    op.drop_index("ix_turns_session_id", table_name="turns")
    op.drop_table("turns")
