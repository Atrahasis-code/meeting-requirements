import shutil
from fastapi import HTTPException
from sqlalchemy import delete, select
from . import models as m
from .repository import rows
from .media import safe_path

ACTIVE = ("running", "queued", "blocked")


def ensure_idle(session, meeting_id):
    if session.scalar(
        select(m.ProcessingJob.id).where(
            m.ProcessingJob.meeting_id == meeting_id, m.ProcessingJob.status.in_(ACTIVE)
        )
    ):
        raise HTTPException(409, "Cancela o termina el trabajo pendiente antes de continuar")


def queue_job(session, meeting, kind, params):
    ensure_idle(session, meeting.id)
    job = m.ProcessingJob(meeting_id=meeting.id, kind=kind, params=params)
    session.add(job)
    meeting.status = "queued"
    session.flush()
    from .runtime import runtime

    runtime.queued(session, job, meeting)
    return job


def delete_meeting(session, meeting):
    ensure_idle(session, meeting.id)
    # Delete explicitly in dependency order; no implicit project/meeting cascade.
    artifacts = rows(session, m.ExportArtifact, m.ExportArtifact.meeting_id == meeting.id)
    media = rows(session, m.MediaFile, m.MediaFile.meeting_id == meeting.id)
    runs = rows(session, m.AnalysisRun, m.AnalysisRun.meeting_id == meeting.id)
    for artifact in artifacts:
        shutil.rmtree(safe_path("exports", artifact.path), ignore_errors=True)
        session.delete(artifact)
    session.flush()
    for run in runs:
        for model in (m.AcceptanceCriterion, m.UserStory):
            for entity in rows(session, model, model.analysis_id == run.id):
                session.delete(entity)
        session.flush()
        for requirement in rows(session, m.Requirement, m.Requirement.analysis_id == run.id):
            session.delete(requirement)
        for model in (m.BusinessRule, m.OpenQuestion):
            session.execute(delete(model).where(model.analysis_id == run.id))
        session.flush()
        session.delete(run)
    session.flush()
    for model in (m.TranscriptSegment, m.ProcessingJob):
        session.execute(delete(model).where(model.meeting_id == meeting.id))
    for item in media:
        safe_path("media", item.path).unlink(missing_ok=True)
        session.delete(item)
    shutil.rmtree(safe_path("transcripts", meeting.id), ignore_errors=True)
    session.flush()
    session.delete(meeting)
