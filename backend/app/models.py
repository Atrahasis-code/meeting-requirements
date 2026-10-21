from datetime import date
from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    false,
    Column,
    Date,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base, Record


story_requirements = Table(
    "story_requirements",
    Base.metadata,
    Column("story_id", ForeignKey("user_stories.id", ondelete="CASCADE"), primary_key=True),
    Column("requirement_id", ForeignKey("requirements.id", ondelete="CASCADE"), primary_key=True),
)
criterion_requirements = Table(
    "criterion_requirements",
    Base.metadata,
    Column("criterion_id", ForeignKey("acceptance_criteria.id", ondelete="CASCADE"), primary_key=True),
    Column("requirement_id", ForeignKey("requirements.id", ondelete="CASCADE"), primary_key=True),
)


class Project(Record, Base):
    __tablename__ = "projects"
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    context: Mapped[str] = mapped_column(Text, default="")
    glossary: Mapped[dict] = mapped_column(JSON, default=dict)


class Meeting(Record, Base):
    __tablename__ = "meetings"
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="RESTRICT"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(default="registered")
    profile: Mapped[str] = mapped_column(default="balanced")
    language: Mapped[str | None] = mapped_column(default="es")
    transcript_revision: Mapped[int] = mapped_column(default=0)
    active_analysis_id: Mapped[str | None] = mapped_column(default=None)


class MediaFile(Record, Base):
    __tablename__ = "media_files"
    meeting_id: Mapped[str] = mapped_column(ForeignKey("meetings.id", ondelete="RESTRICT"), unique=True)
    path: Mapped[str]
    original_name: Mapped[str]
    size: Mapped[int] = mapped_column(Integer)
    duration: Mapped[float] = mapped_column(Float)
    mime_type: Mapped[str]
    sha256: Mapped[str]


class ProcessingJob(Record, Base):
    __tablename__ = "processing_jobs"
    meeting_id: Mapped[str] = mapped_column(ForeignKey("meetings.id", ondelete="RESTRICT"), index=True)
    kind: Mapped[str]
    status: Mapped[str] = mapped_column(default="queued", index=True)
    stage: Mapped[str] = mapped_column(default="queued")
    progress: Mapped[float | None] = mapped_column(Float, default=None)
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text, default=None)
    blocked_reason: Mapped[str | None] = mapped_column(default=None)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    checkpoint: Mapped[dict] = mapped_column(JSON, default=dict)


class TranscriptSegment(Record, Base):
    __tablename__ = "transcript_segments"
    __table_args__ = (CheckConstraint("NOT (reviewed AND discarded)", name="ck_transcript_selection"),)
    meeting_id: Mapped[str] = mapped_column(ForeignKey("meetings.id", ondelete="RESTRICT"), index=True)
    start: Mapped[float] = mapped_column(Float)
    end: Mapped[float] = mapped_column(Float)
    original_text: Mapped[str] = mapped_column(Text)
    revised_text: Mapped[str | None] = mapped_column(Text, default=None)
    reviewed: Mapped[bool] = mapped_column(Boolean, default=False)
    discarded: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    doubtful: Mapped[bool] = mapped_column(Boolean, default=False)
    detection: Mapped[dict] = mapped_column(JSON, default=dict)
    chunk_index: Mapped[int] = mapped_column(default=0)


class AnalysisRun(Record, Base):
    __tablename__ = "analysis_runs"
    meeting_id: Mapped[str] = mapped_column(ForeignKey("meetings.id", ondelete="RESTRICT"), index=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("processing_jobs.id", ondelete="RESTRICT"))
    provider: Mapped[str]
    input_snapshot: Mapped[dict] = mapped_column(JSON)
    original_result: Mapped[dict] = mapped_column(JSON)


class Requirement(Record, Base):
    __tablename__ = "requirements"
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="RESTRICT"), index=True)
    analysis_id: Mapped[str] = mapped_column(ForeignKey("analysis_runs.id", ondelete="RESTRICT"), index=True)
    code: Mapped[str]
    kind: Mapped[str]
    title: Mapped[str]
    description: Mapped[str] = mapped_column(Text)
    actor: Mapped[str]
    module: Mapped[str]
    priority: Mapped[str]
    status: Mapped[str] = mapped_column(default="detected")
    interpretation: Mapped[str] = mapped_column(default="proposal")
    dependencies: Mapped[list] = mapped_column(JSON, default=list)
    questions: Mapped[list] = mapped_column(JSON, default=list)
    observations: Mapped[str] = mapped_column(Text, default="")
    original: Mapped[dict] = mapped_column(JSON)
    evidence: Mapped[list["EvidenceReference"]] = relationship(cascade="all, delete-orphan")


class RequirementRevision(Record, Base):
    __tablename__ = "requirement_revisions"
    requirement_id: Mapped[str] = mapped_column(ForeignKey("requirements.id", ondelete="CASCADE"))
    before: Mapped[dict] = mapped_column(JSON)
    after: Mapped[dict] = mapped_column(JSON)


class EvidenceReference(Record, Base):
    __tablename__ = "evidence_references"
    requirement_id: Mapped[str] = mapped_column(ForeignKey("requirements.id", ondelete="CASCADE"))
    segment_id: Mapped[str] = mapped_column(ForeignKey("transcript_segments.id", ondelete="RESTRICT"))
    quote: Mapped[str] = mapped_column(Text)
    start: Mapped[float] = mapped_column(Float)
    end: Mapped[float] = mapped_column(Float)


class UserStory(Record, Base):
    __tablename__ = "user_stories"
    analysis_id: Mapped[str] = mapped_column(ForeignKey("analysis_runs.id", ondelete="RESTRICT"))
    code: Mapped[str]
    text: Mapped[str] = mapped_column(Text)
    requirements: Mapped[list[Requirement]] = relationship(secondary=story_requirements)


class AcceptanceCriterion(Record, Base):
    __tablename__ = "acceptance_criteria"
    analysis_id: Mapped[str] = mapped_column(ForeignKey("analysis_runs.id", ondelete="RESTRICT"))
    code: Mapped[str]
    story_code: Mapped[str]
    given: Mapped[str] = mapped_column(Text)
    when: Mapped[str] = mapped_column(Text)
    then: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(default="pending_validation", server_default="pending_validation")
    revision: Mapped[int] = mapped_column(default=0, server_default="0")
    revisions: Mapped[list] = mapped_column(JSON, default=list, server_default="[]")
    requirements: Mapped[list[Requirement]] = relationship(secondary=criterion_requirements)


class BusinessRule(Record, Base):
    __tablename__ = "business_rules"
    analysis_id: Mapped[str] = mapped_column(ForeignKey("analysis_runs.id", ondelete="RESTRICT"))
    text: Mapped[str] = mapped_column(Text)
    evidence: Mapped[list] = mapped_column(JSON)


class OpenQuestion(Record, Base):
    __tablename__ = "open_questions"
    analysis_id: Mapped[str] = mapped_column(ForeignKey("analysis_runs.id", ondelete="RESTRICT"))
    text: Mapped[str] = mapped_column(Text)
    evidence: Mapped[list] = mapped_column(JSON)


class ExportArtifact(Record, Base):
    __tablename__ = "export_artifacts"
    meeting_id: Mapped[str] = mapped_column(ForeignKey("meetings.id", ondelete="RESTRICT"))
    analysis_id: Mapped[str] = mapped_column(ForeignKey("analysis_runs.id", ondelete="RESTRICT"))
    path: Mapped[str]
    files: Mapped[list] = mapped_column(JSON)


class AppSetting(Base):
    __tablename__ = "app_settings"
    key: Mapped[str] = mapped_column(primary_key=True)
    value: Mapped[dict] = mapped_column(JSON)
