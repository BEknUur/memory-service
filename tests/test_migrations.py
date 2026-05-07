#python imports
from pathlib import Path

#third-party imports

#project imports


def test_memory_slots_migration_adds_and_backfills_slot():
    migration = Path("migrations/versions/0004_memory_slots.py").read_text()

    assert 'op.add_column("memories", sa.Column("slot"' in migration
    assert "UPDATE memories SET slot = key" in migration
    assert 'op.alter_column("memories", "slot", nullable=False)' in migration


def test_memory_slots_migration_replaces_unique_indexes_with_slot():
    migration = Path("migrations/versions/0004_memory_slots.py").read_text()

    assert 'op.drop_index("uq_memories_active_user_key"' in migration
    assert 'op.drop_index("uq_memories_active_session_key"' in migration
    assert '["user_id", "slot"]' in migration
    assert '["session_id", "slot"]' in migration


def test_memory_slots_migration_preserves_downgrade_path():
    migration = Path("migrations/versions/0004_memory_slots.py").read_text()

    assert '["user_id", "key"]' in migration
    assert '["session_id", "key"]' in migration
    assert 'op.drop_column("memories", "slot")' in migration
