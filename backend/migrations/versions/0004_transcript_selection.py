"""Add reversible exclusion without rebuilding tables or modifying earlier snapshots."""

from alembic import op

revision = "0004"
down_revision = "0003"


def upgrade():
    # Column CHECK works in SQLite and PostgreSQL and preserves tenant triggers/RLS.
    op.execute(
        "ALTER TABLE transcript_segments ADD COLUMN discarded BOOLEAN DEFAULT false NOT NULL "
        "CONSTRAINT ck_transcript_selection CHECK (NOT (reviewed AND discarded))"
    )


def downgrade():
    raise RuntimeError("Restore a verified backup instead of destructive downgrade")
