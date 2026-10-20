"""Local workspace context and database-side organization consistency."""

from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
TABLES = (
    "projects",
    "meetings",
    "media_files",
    "processing_jobs",
    "transcript_segments",
    "analysis_runs",
    "requirements",
    "requirement_revisions",
    "evidence_references",
    "user_stories",
    "acceptance_criteria",
    "business_rules",
    "open_questions",
    "export_artifacts",
)


def upgrade():
    for name in TABLES:
        op.add_column(name, sa.Column("organization_id", sa.String(), nullable=False, server_default="local"))
        op.create_index("ix_" + name + "_organization_id", name, ["organization_id"])
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    for name in TABLES:
        for fk in inspector.get_foreign_keys(name):
            parent = fk["referred_table"]
            if parent not in TABLES:
                continue
            column = fk["constrained_columns"][0]
            target = fk["referred_columns"][0]
            trigger = "tenant_" + name + "_" + column
            if connection.dialect.name == "postgresql":
                op.execute(f"""CREATE FUNCTION {trigger}() RETURNS trigger LANGUAGE plpgsql AS $$
                BEGIN IF NOT EXISTS(SELECT 1 FROM {parent} WHERE {target}=NEW.{column} AND organization_id=NEW.organization_id) THEN
                RAISE EXCEPTION 'organization relation mismatch'; END IF; RETURN NEW; END $$""")
                op.execute(
                    f"CREATE TRIGGER {trigger} BEFORE INSERT OR UPDATE OF {column}, organization_id ON {name} FOR EACH ROW EXECUTE FUNCTION {trigger}()"
                )
            else:
                for action in ("INSERT", "UPDATE"):
                    op.execute(f"""CREATE TRIGGER {trigger}_{action.lower()} BEFORE {action} ON {name}
                    WHEN NOT EXISTS(SELECT 1 FROM {parent} WHERE {target}=NEW.{column} AND organization_id=NEW.organization_id)
                    BEGIN SELECT RAISE(ABORT,'organization relation mismatch'); END""")


def downgrade():
    raise RuntimeError("Restore a verified backup instead of destructive downgrade")
