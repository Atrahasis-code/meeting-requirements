"""Initial local application schema."""

from alembic import op
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Table,
    Text,
    MetaData,
)

revision = "0001"
down_revision = None


def upgrade():
    # The migration records an immutable schema, independent of future ORM changes.
    metadata = MetaData()

    def table(name, *columns):
        return Table(
            name,
            metadata,
            Column("id", String, primary_key=True),
            Column("created_at", DateTime, nullable=False),
            Column("updated_at", DateTime, nullable=False),
            *columns,
        )

    def field(name, kind=String, nullable=False, **kw):
        return Column(name, kind, nullable=nullable, **kw)

    def ref(name, target, **kw):
        return Column(
            name, String, ForeignKey(target, ondelete=kw.pop("ondelete", "RESTRICT")), nullable=False, **kw
        )

    table(
        "projects", field("name"), field("description", Text), field("context", Text), field("glossary", JSON)
    )
    table(
        "meetings",
        ref("project_id", "projects.id", index=True),
        field("title"),
        field("date", Date),
        field("status"),
        field("profile"),
        field("language", nullable=True),
        field("transcript_revision", Integer),
        field("active_analysis_id", nullable=True),
    )
    table(
        "media_files",
        ref("meeting_id", "meetings.id", unique=True),
        field("path"),
        field("original_name"),
        field("size", Integer),
        field("duration", Float),
        field("mime_type"),
        field("sha256"),
    )
    table(
        "processing_jobs",
        ref("meeting_id", "meetings.id", index=True),
        field("kind"),
        field("status", index=True),
        field("stage"),
        field("progress", Float, nullable=True),
        field("params", JSON),
        field("error", Text, nullable=True),
        field("blocked_reason", nullable=True),
        field("cancel_requested", Boolean),
        field("checkpoint", JSON),
    )
    table(
        "transcript_segments",
        ref("meeting_id", "meetings.id", index=True),
        field("start", Float),
        field("end", Float),
        field("original_text", Text),
        field("revised_text", Text, nullable=True),
        field("reviewed", Boolean),
        field("doubtful", Boolean),
        field("detection", JSON),
        field("chunk_index", Integer),
    )
    table(
        "analysis_runs",
        ref("meeting_id", "meetings.id", index=True),
        ref("job_id", "processing_jobs.id"),
        field("provider"),
        field("input_snapshot", JSON),
        field("original_result", JSON),
    )
    table(
        "requirements",
        ref("project_id", "projects.id", index=True),
        ref("analysis_id", "analysis_runs.id", index=True),
        *[
            field(n, Text if n in ("description", "observations") else String)
            for n in (
                "code",
                "kind",
                "title",
                "description",
                "actor",
                "module",
                "priority",
                "status",
                "interpretation",
                "observations",
            )
        ],
        field("dependencies", JSON),
        field("questions", JSON),
        field("original", JSON),
    )
    table(
        "requirement_revisions",
        ref("requirement_id", "requirements.id", ondelete="CASCADE"),
        field("before", JSON),
        field("after", JSON),
    )
    table(
        "evidence_references",
        ref("requirement_id", "requirements.id", ondelete="CASCADE"),
        ref("segment_id", "transcript_segments.id"),
        field("quote", Text),
        field("start", Float),
        field("end", Float),
    )
    table("user_stories", ref("analysis_id", "analysis_runs.id"), field("code"), field("text", Text))
    table(
        "acceptance_criteria",
        ref("analysis_id", "analysis_runs.id"),
        field("code"),
        field("story_code"),
        field("given", Text),
        field("when", Text),
        field("then", Text),
    )
    for name in ("business_rules", "open_questions"):
        table(name, ref("analysis_id", "analysis_runs.id"), field("text", Text), field("evidence", JSON))
    table(
        "export_artifacts",
        ref("meeting_id", "meetings.id"),
        ref("analysis_id", "analysis_runs.id"),
        field("path"),
        field("files", JSON),
    )
    for name, parent, key in (
        ("story_requirements", "user_stories", "story_id"),
        ("criterion_requirements", "acceptance_criteria", "criterion_id"),
    ):
        Table(
            name,
            metadata,
            ref(key, parent + ".id", primary_key=True, ondelete="CASCADE"),
            ref("requirement_id", "requirements.id", primary_key=True, ondelete="CASCADE"),
        )
    Table("app_settings", metadata, Column("key", String, primary_key=True), field("value", JSON))
    metadata.create_all(op.get_bind())
    op.execute("CREATE UNIQUE INDEX one_running_job ON processing_jobs ((1)) WHERE status = 'running'")
    op.execute(
        "CREATE UNIQUE INDEX one_active_meeting_job ON processing_jobs (meeting_id) WHERE status IN ('running','queued','blocked')"
    )


def downgrade():
    raise RuntimeError("Destructive downgrade is disabled; restore a verified backup instead.")
