"""Preserve explicit acceptance-criterion revisions without changing generated results."""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"


def upgrade():
    op.add_column(
        "acceptance_criteria",
        sa.Column("status", sa.String(), nullable=False, server_default="pending_validation"),
    )
    op.add_column(
        "acceptance_criteria", sa.Column("revision", sa.Integer(), nullable=False, server_default="0")
    )
    op.add_column(
        "acceptance_criteria", sa.Column("revisions", sa.JSON(), nullable=False, server_default="[]")
    )


def downgrade():
    raise RuntimeError("Destructive downgrade is disabled; restore a verified backup instead.")
