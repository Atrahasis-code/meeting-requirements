import secrets
import time
from datetime import datetime
from fastapi import Depends, FastAPI, HTTPException, Query, Request, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session
from . import auth, models as m, schemas as s
from .analysis import input_hash, snapshot
from .config import settings
from .context import current_actor
from .db import session_dependency
from .exports import create_export
from .media import safe_path, save_upload
from .repository import get, rows, serialize, setting, set_setting
from .services import delete_meeting, ensure_idle, queue_job
from .transcripts import render_transcripts, write_transcripts

app = FastAPI(
    title="Meeting Requirements AI", version="0.1.0", docs_url="/api/docs", openapi_url="/api/openapi.json"
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.public_url],
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Content-Type"],
    allow_credentials=True,
)
DB = Depends(session_dependency)


class UploadLimit:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = dict(scope["headers"])
        limit = settings.max_upload_bytes + 1024 * 1024
        if int(headers.get(b"content-length", b"0")) > limit:
            return await JSONResponse({"detail": "Carga demasiado grande"}, 413)(scope, receive, send)
        total = 0

        async def limited_receive():
            nonlocal total
            message = await receive()
            total += len(message.get("body", b""))
            if total > limit:
                raise HTTPException(413, "Carga demasiado grande")
            return message

        await self.app(scope, limited_receive, send)


app.add_middleware(UploadLimit)


@app.middleware("http")
async def local_security(request: Request, call_next):
    host = request.headers.get("host", "").split(":")[0]
    allowed = set(settings.allowed_hosts.split(","))
    if host not in allowed:
        return JSONResponse({"detail": "Host no permitido"}, 400)
    origin = request.headers.get("origin")
    if request.method in {"POST", "PATCH", "DELETE"} and origin and origin != settings.public_url:
        return JSONResponse({"detail": "Origen no permitido"}, 403)
    if (
        request.method in {"POST", "PATCH", "DELETE"}
        and request.headers.get("sec-fetch-site") == "cross-site"
    ):
        return JSONResponse({"detail": "Solicitud externa no permitida"}, 403)
    response = await call_next(request)
    response.headers.update(
        {"X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer", "Cache-Control": "no-store"}
    )
    return response


@app.exception_handler(IntegrityError)
async def conflict(_, error):
    return JSONResponse(
        {"detail": "La operación entra en conflicto con un trabajo o relación existente"}, 409
    )


@app.exception_handler(ValueError)
async def invalid(_, error):
    return JSONResponse({"detail": str(error)[:300]}, 422)


@app.exception_handler(OperationalError)
async def storage_unavailable(_, error):
    return JSONResponse({"detail": "Almacenamiento ocupado o no disponible; reintenta la operación"}, 503)


@app.exception_handler(auth.AuthFailure)
async def auth_error(_, error):
    return JSONResponse({"detail": error.message, "code": error.code}, 409)


@app.get("/api/health")
def health(session: Session = DB):
    session.execute(text("SELECT 1"))
    worker = setting(session, "worker", {})
    return {"status": "ok", "database": "ok", "worker_online": time.time() - worker.get("heartbeat", 0) < 15}


@app.get("/api/providers")
def provider_catalog():
    return [
        {"id": "chatgpt", "available": True, "authentication": "oauth"},
        {"id": "mock", "available": True, "authentication": "none", "explicit_selection": True},
        {"id": "claude", "available": False, "reason": "OAuth para terceros no habilitado"},
        {"id": "grok", "available": False, "reason": "OAuth no disponible para esta aplicación"},
    ]


@app.get("/api/capabilities")
def capabilities():
    from .runtime import runtime

    return runtime.capabilities()


@app.get("/api/dashboard")
def dashboard(session: Session = DB):
    projects = session.scalars(select(m.Project).order_by(m.Project.updated_at.desc()).limit(6)).all()
    return dict(
        projects=[serialize(p) for p in projects],
        project_count=session.scalar(select(func.count()).select_from(m.Project)),
        meeting_count=session.scalar(select(func.count()).select_from(m.Meeting)),
        pending_requirements=session.scalar(
            select(func.count())
            .select_from(m.Requirement)
            .join(m.AnalysisRun, m.AnalysisRun.id == m.Requirement.analysis_id)
            .join(m.Meeting, m.Meeting.active_analysis_id == m.AnalysisRun.id)
            .where(m.Requirement.status.notin_(["validated", "rejected"]))
        ),
        jobs=[
            serialize(j)
            for j in session.scalars(
                select(m.ProcessingJob)
                .where(m.ProcessingJob.status.in_(["running", "queued", "blocked"]))
                .order_by(m.ProcessingJob.created_at)
            ).all()
        ],
    )


@app.get("/api/projects")
def projects(session: Session = DB):
    return [serialize(p) for p in session.scalars(select(m.Project).order_by(m.Project.updated_at.desc()))]


@app.post("/api/projects", status_code=201)
def new_project(payload: s.ProjectInput, session: Session = DB):
    project = m.Project(**payload.model_dump())
    session.add(project)
    session.commit()
    return serialize(project)


@app.get("/api/projects/{identity}")
def project_detail(identity: str, session: Session = DB):
    return serialize(get(session, m.Project, identity))


@app.patch("/api/projects/{identity}")
def edit_project(identity: str, payload: s.ProjectPatch, session: Session = DB):
    project = get(session, m.Project, identity)
    for key, value in payload.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(project, key, value)
    session.commit()
    return serialize(project)


@app.delete("/api/projects/{identity}", status_code=204)
def remove_project(identity: str, confirm: bool = False, session: Session = DB):
    if not confirm:
        raise HTTPException(400, "Confirma la eliminación completa del proyecto")
    project = get(session, m.Project, identity)
    meetings = rows(session, m.Meeting, m.Meeting.project_id == identity)
    for meeting in meetings:
        ensure_idle(session, meeting.id)
    for meeting in meetings:
        delete_meeting(session, meeting)
        session.flush()
    session.delete(project)
    session.commit()


@app.get("/api/meetings")
def meetings(project_id: str | None = None, session: Session = DB):
    query = select(m.Meeting).order_by(m.Meeting.created_at.desc())
    if project_id:
        query = query.where(m.Meeting.project_id == project_id)
    return [meeting_response(session, item) for item in session.scalars(query)]


def meeting_response(session, item):
    result = serialize(item)
    media = session.scalar(select(m.MediaFile).where(m.MediaFile.meeting_id == item.id))
    result["media"] = (
        {k: v for k, v in serialize(media).items() if k not in {"path", "sha256"}} if media else None
    )
    result["jobs"] = [
        serialize(j)
        for j in session.scalars(
            select(m.ProcessingJob)
            .where(m.ProcessingJob.meeting_id == item.id)
            .order_by(m.ProcessingJob.created_at.desc())
        )
    ]
    return result


@app.post("/api/meetings", status_code=201)
def new_meeting(payload: s.MeetingInput, session: Session = DB):
    get(session, m.Project, payload.project_id)
    meeting = m.Meeting(**payload.model_dump())
    session.add(meeting)
    session.commit()
    return meeting_response(session, meeting)


@app.get("/api/meetings/{identity}")
def meeting_detail(identity: str, session: Session = DB):
    return meeting_response(session, get(session, m.Meeting, identity))


@app.post("/api/meetings/{identity}/upload", status_code=201)
async def upload(identity: str, file: UploadFile, session: Session = DB):
    meeting = get(session, m.Meeting, identity)
    ensure_idle(session, identity)
    if (
        session.scalar(select(m.MediaFile.id).where(m.MediaFile.meeting_id == identity))
        or meeting.transcript_revision
        or session.scalar(select(m.TranscriptSegment.id).where(m.TranscriptSegment.meeting_id == identity))
    ):
        raise HTTPException(409, "Crea una reunión nueva para otra grabación")
    data = await save_upload(file)
    try:
        session.add(m.MediaFile(meeting_id=identity, **data))
        meeting.status = "uploaded"
        session.commit()
    except BaseException:
        safe_path("media", data["path"]).unlink(missing_ok=True)
        raise
    return meeting_response(session, meeting)


@app.delete("/api/meetings/{identity}", status_code=204)
def remove_meeting(identity: str, confirm: bool = False, session: Session = DB):
    if not confirm:
        raise HTTPException(400, "Confirma la eliminación de reunión, análisis y archivos")
    delete_meeting(session, get(session, m.Meeting, identity))
    session.commit()


@app.delete("/api/meetings/{identity}/media", status_code=204)
def remove_media(identity: str, confirm: bool = False, session: Session = DB):
    get(session, m.Meeting, identity)
    ensure_idle(session, identity)
    if not confirm:
        raise HTTPException(
            400, "Confirma la eliminación de la grabación; se conservarán textos y requisitos"
        )
    media = session.scalar(select(m.MediaFile).where(m.MediaFile.meeting_id == identity))
    if media:
        safe_path("media", media.path).unlink(missing_ok=True)
        session.delete(media)
        session.commit()


@app.get("/api/meetings/{identity}/media")
def media_file(identity: str, session: Session = DB):
    get(session, m.Meeting, identity)
    media = session.scalar(select(m.MediaFile).where(m.MediaFile.meeting_id == identity))
    if not media:
        raise HTTPException(404, "La grabación no está disponible")
    return FileResponse(safe_path("media", media.path), media_type=media.mime_type)


@app.post("/api/meetings/{identity}/transcribe", status_code=202)
def transcribe(identity: str, session: Session = DB):
    meeting = get(session, m.Meeting, identity)
    if meeting.transcript_revision:
        raise HTTPException(
            409, "La transcripción original ya existe; sus correcciones se realizan en el editor"
        )
    if not session.scalar(select(m.MediaFile.id).where(m.MediaFile.meeting_id == identity)):
        raise HTTPException(409, "Carga una grabación primero")
    job = queue_job(
        session, meeting, "transcribe", {"profile": meeting.profile, "language": meeting.language}
    )
    previous = session.scalar(
        select(m.ProcessingJob)
        .where(
            m.ProcessingJob.meeting_id == identity,
            m.ProcessingJob.kind == "transcribe",
            m.ProcessingJob.id != job.id,
        )
        .order_by(m.ProcessingJob.created_at.desc())
    )
    if previous:
        job.checkpoint = previous.checkpoint
    session.commit()
    return serialize(job)


@app.get("/api/meetings/{identity}/analysis-input")
def analysis_input(identity: str, session: Session = DB):
    meeting = get(session, m.Meeting, identity)
    if not meeting.transcript_revision:
        raise HTTPException(409, "Finaliza la transcripción primero")
    data = snapshot(session, meeting)
    return {"snapshot": data, "input_hash": input_hash(data)}


@app.post("/api/meetings/{identity}/analyze", status_code=202)
def analyze(identity: str, payload: s.AnalysisRequest, session: Session = DB):
    meeting = get(session, m.Meeting, identity)
    if not meeting.transcript_revision:
        raise HTTPException(409, "Finaliza la transcripción primero")
    data = snapshot(session, meeting)
    if payload.input_hash != input_hash(data):
        raise HTTPException(409, "Cambió la entrada; revisa el texto y autoriza nuevamente")
    if not any(segment["text"].strip() for segment in data["segments"]):
        raise HTTPException(422, "La transcripción está vacía")
    if data["provider"] != "mock":
        if not payload.consent:
            raise HTTPException(403, "Se requiere autorización explícita para enviar el texto")
        from .runtime import runtime

        runtime.analysis_allowed(data)
        if not data.get("model"):
            raise HTTPException(409, "Selecciona un modelo en Configuración")
    job = queue_job(
        session,
        meeting,
        "analyze",
        {
            "snapshot": data,
            "input_hash": payload.input_hash,
            "consent": payload.consent,
            "consented_at": datetime.now().isoformat(),
        },
    )
    previous = session.scalar(
        select(m.ProcessingJob)
        .where(
            m.ProcessingJob.meeting_id == identity,
            m.ProcessingJob.kind == "analyze",
            m.ProcessingJob.id != job.id,
        )
        .order_by(m.ProcessingJob.created_at.desc())
    )
    if (
        previous
        and previous.params.get("input_hash") == payload.input_hash
        and previous.status in {"failed", "interrupted", "cancelled"}
    ):
        job.checkpoint = previous.checkpoint
    session.commit()
    return serialize(job)


@app.get("/api/jobs/{identity}")
def job(identity: str, session: Session = DB):
    return serialize(get(session, m.ProcessingJob, identity))


@app.post("/api/jobs/{identity}/cancel")
def cancel(identity: str, session: Session = DB):
    job = get(session, m.ProcessingJob, identity)
    if job.status == "running":
        job.cancel_requested = True
    elif job.status in {"queued", "blocked"}:
        job.cancel_requested, job.status, job.stage = True, "cancelled", "cancelled"
        get(session, m.Meeting, job.meeting_id).status = "cancelled"
        from .runtime import runtime

        runtime.cancelled(session, job)
    else:
        raise HTTPException(409, "El trabajo ya terminó")
    session.commit()
    return serialize(job)


@app.post("/api/jobs/{identity}/retry", status_code=202)
def retry(identity: str, payload: s.AnalysisRequest | None = None, session: Session = DB):
    previous = get(session, m.ProcessingJob, identity)
    if previous.status not in {"failed", "interrupted", "cancelled", "blocked"}:
        raise HTTPException(409, "El trabajo no admite reintento")
    meeting = get(session, m.Meeting, previous.meeting_id)
    if previous.status == "blocked":
        previous.status = "interrupted"
        session.flush()
    if previous.kind == "transcribe":
        from .runtime import runtime

        runtime.retry_operation(previous)
        try:
            return transcribe(meeting.id, session)
        finally:
            runtime.retry_operation(None)
    if payload is None:
        raise HTTPException(400, "Revisa y autoriza la entrada nuevamente")
    if previous.status == "blocked":
        previous.status = "interrupted"
        session.flush()
    from .runtime import runtime

    runtime.retry_operation(previous)
    try:
        return analyze(meeting.id, payload, session)
    finally:
        runtime.retry_operation(None)


@app.get("/api/meetings/{identity}/transcript")
def transcript(identity: str, session: Session = DB):
    meeting = get(session, m.Meeting, identity)
    segments = session.scalars(
        select(m.TranscriptSegment)
        .where(m.TranscriptSegment.meeting_id == identity)
        .order_by(m.TranscriptSegment.start)
    ).all()
    return {
        "revision": meeting.transcript_revision,
        "complete": meeting.transcript_revision > 0,
        "segments": [serialize(x) for x in segments],
    }


@app.patch("/api/transcript-segments/{identity}")
def edit_segment(identity: str, payload: s.TranscriptPatch, session: Session = DB):
    segment = get(session, m.TranscriptSegment, identity)
    meeting = get(session, m.Meeting, segment.meeting_id)
    if not meeting.transcript_revision:
        raise HTTPException(409, "La transcripción todavía es parcial")
    # Atomic revision comparison prevents lost updates from multiple browser tabs.
    from sqlalchemy import update

    result = session.execute(
        update(m.Meeting)
        .where(m.Meeting.id == meeting.id, m.Meeting.transcript_revision == payload.revision)
        .values(transcript_revision=payload.revision + 1)
    )
    if not result.rowcount:
        raise HTTPException(409, "La transcripción cambió; recarga antes de guardar")
    for key, value in payload.model_dump(exclude_unset=True).items():
        if key != "revision":
            setattr(segment, key, value)
    if meeting.status == "transcribed":
        meeting.status = "in_review"
    session.commit()
    segments = session.scalars(
        select(m.TranscriptSegment)
        .where(m.TranscriptSegment.meeting_id == meeting.id)
        .order_by(m.TranscriptSegment.start)
    ).all()
    write_transcripts(meeting.id, segments)
    return {"segment": serialize(segment), "revision": payload.revision + 1}


@app.get("/api/meetings/{identity}/transcript/download")
def download_transcript(
    identity: str, format: str = Query("txt", pattern="^(txt|json|srt|vtt)$"), session: Session = DB
):
    meeting = get(session, m.Meeting, identity)
    if not meeting.transcript_revision:
        raise HTTPException(409, "La transcripción no está completa")
    segments = session.scalars(
        select(m.TranscriptSegment)
        .where(m.TranscriptSegment.meeting_id == identity)
        .order_by(m.TranscriptSegment.start)
    ).all()
    return Response(
        render_transcripts(segments)[format],
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="transcript.{format}"'},
    )


@app.get("/api/meetings/{identity}/analyses")
def analyses(identity: str, session: Session = DB):
    meeting = get(session, m.Meeting, identity)
    result = []
    for run in session.scalars(
        select(m.AnalysisRun)
        .where(m.AnalysisRun.meeting_id == identity)
        .order_by(m.AnalysisRun.created_at.desc())
    ):
        item = serialize(run)
        item["active"] = meeting.active_analysis_id == run.id
        requirements = rows(session, m.Requirement, m.Requirement.analysis_id == run.id)
        item["requirements"] = [requirement_response(r) for r in requirements]
        item["code_mapping"] = {r.original.get("code", r.code): r.code for r in requirements}
        item["criteria"] = [
            criterion_response(c, run)
            for c in rows(session, m.AcceptanceCriterion, m.AcceptanceCriterion.analysis_id == run.id)
        ]
        item["stories"] = [
            dict(**serialize(story), requirements=[r.id for r in story.requirements])
            for story in rows(session, m.UserStory, m.UserStory.analysis_id == run.id)
        ]
        result.append(item)
    return result


def criterion_response(criterion, run):
    original = next(c for c in run.original_result["criteria"] if c["code"] == criterion.code)
    return {
        **serialize(criterion),
        "original": original,
        "requirements": [r.original["code"] for r in criterion.requirements],
    }


@app.get("/api/criteria/{identity}")
def criterion_detail(identity: str, session: Session = DB):
    criterion = get(session, m.AcceptanceCriterion, identity)
    run = get(session, m.AnalysisRun, criterion.analysis_id)
    return {
        **criterion_response(criterion, run),
        "meeting_id": run.meeting_id,
        "active": get(session, m.Meeting, run.meeting_id).active_analysis_id == run.id,
    }


def editable_criterion(session, criterion, expected_revision):
    run = get(session, m.AnalysisRun, criterion.analysis_id)
    if get(session, m.Meeting, run.meeting_id).active_analysis_id != run.id:
        raise HTTPException(409, "Activa esta versión antes de editar sus criterios")
    if criterion.revision != expected_revision:
        raise HTTPException(409, "El criterio cambió; revisa la última versión antes de editar")


@app.patch("/api/criteria/{identity}")
def edit_criterion(identity: str, payload: s.CriterionPatch, session: Session = DB):
    criterion = get(session, m.AcceptanceCriterion, identity)
    editable_criterion(session, criterion, payload.revision)
    fields = payload.model_dump(include={"given", "when", "then"})
    if all(getattr(criterion, key) == value for key, value in fields.items()):
        return criterion_response(criterion, get(session, m.AnalysisRun, criterion.analysis_id))
    after = {**fields, "status": "pending_validation"}
    return save_criterion_revision(session, criterion, payload.revision, after, payload.observations, "edit")


@app.post("/api/criteria/{identity}/validate")
def validate_criterion(identity: str, payload: s.CriterionValidation, session: Session = DB):
    criterion = get(session, m.AcceptanceCriterion, identity)
    editable_criterion(session, criterion, payload.revision)
    after = {key: getattr(criterion, key) for key in ("given", "when", "then")}
    after["status"] = payload.status
    return save_criterion_revision(
        session, criterion, payload.revision, after, payload.observations, "validation"
    )


def save_criterion_revision(session, criterion, expected_revision, after, observations, action):
    before = {key: getattr(criterion, key) for key in ("given", "when", "then", "status")}
    revision = {
        "before": before,
        "after": after,
        "action": action,
        "actor": current_actor(),
        "observations": observations,
        "created_at": datetime.now().isoformat(),
    }
    changed = session.execute(
        update(m.AcceptanceCriterion)
        .where(m.AcceptanceCriterion.id == criterion.id, m.AcceptanceCriterion.revision == expected_revision)
        .values(**after, revision=expected_revision + 1, revisions=[*criterion.revisions, revision])
    )
    if changed.rowcount != 1:
        raise HTTPException(409, "El criterio cambió; revisa la última versión antes de editar")
    session.commit()
    session.refresh(criterion)
    return criterion_response(criterion, get(session, m.AnalysisRun, criterion.analysis_id))


@app.post("/api/analysis-runs/{identity}/activate")
def activate(identity: str, session: Session = DB):
    run = get(session, m.AnalysisRun, identity)
    get(session, m.Meeting, run.meeting_id).active_analysis_id = run.id
    session.commit()
    return {"active_analysis_id": run.id}


def requirement_response(requirement):
    return {**serialize(requirement), "evidence": [serialize(e) for e in requirement.evidence]}


@app.get("/api/projects/{identity}/requirements")
def project_requirements(
    identity: str,
    status: str | None = None,
    module: str | None = None,
    priority: str | None = None,
    include_history: bool = False,
    session: Session = DB,
):
    get(session, m.Project, identity)
    query = select(m.Requirement).where(m.Requirement.project_id == identity)
    if not include_history:
        query = query.join(m.AnalysisRun, m.AnalysisRun.id == m.Requirement.analysis_id).join(
            m.Meeting, m.Meeting.active_analysis_id == m.AnalysisRun.id
        )
    for key, value in (("status", status), ("module", module), ("priority", priority)):
        if value:
            query = query.where(getattr(m.Requirement, key) == value)
    return [requirement_response(r) for r in session.scalars(query.order_by(m.Requirement.created_at))]


@app.get("/api/requirements/{identity}")
def requirement(identity: str, session: Session = DB):
    req = get(session, m.Requirement, identity)
    return {
        **requirement_response(req),
        "meeting_id": get(session, m.AnalysisRun, req.analysis_id).meeting_id,
        "revisions": [
            serialize(r)
            for r in rows(session, m.RequirementRevision, m.RequirementRevision.requirement_id == identity)
        ],
    }


@app.patch("/api/requirements/{identity}")
def edit_requirement(identity: str, payload: s.RequirementPatch, session: Session = DB):
    req = get(session, m.Requirement, identity)
    before = jsonable_encoder(serialize(req))
    for key, value in payload.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(req, key, value)
    session.add(
        m.RequirementRevision(
            requirement_id=identity,
            before=before,
            after={**jsonable_encoder(serialize(req)), "_actor": current_actor()},
        )
    )
    session.commit()
    return requirement_response(req)


@app.post("/api/requirements/{identity}/validate")
def validate_requirement(identity: str, payload: s.RequirementPatch, session: Session = DB):
    if payload.status not in {s.ValidationStatus.validated, s.ValidationStatus.rejected}:
        raise HTTPException(422, "Elige Validado o Rechazado explícitamente")
    return edit_requirement(identity, payload, session)


@app.post("/api/meetings/{identity}/export", status_code=201)
def export(identity: str, session: Session = DB):
    artifact = create_export(session, get(session, m.Meeting, identity))
    session.commit()
    return serialize(artifact)


@app.get("/api/meetings/{identity}/exports")
def exports(identity: str, session: Session = DB):
    get(session, m.Meeting, identity)
    return [serialize(e) for e in rows(session, m.ExportArtifact, m.ExportArtifact.meeting_id == identity)]


@app.get("/api/exports/{identity}/download")
def download_export(identity: str, file: str | None = None, session: Session = DB):
    artifact = get(session, m.ExportArtifact, identity)
    name = file or "documentos.zip"
    if name not in [*artifact.files, "documentos.zip"]:
        raise HTTPException(404, "Documento no encontrado")
    return FileResponse(safe_path("exports", artifact.path + "/" + name), filename=name)


@app.get("/api/settings")
def preferences(session: Session = DB):
    return {
        **dict(profile="balanced", provider=settings.analysis_provider, model=None, language="es"),
        **setting(session, "preferences", {}),
        "max_upload_bytes": settings.max_upload_bytes,
        "storage": {
            name: str(settings.directory(name))
            for name in ("db", "media", "transcripts", "exports", "models")
        },
        "cpu_threads": settings.cpu_threads,
        "test_mode": settings.test_mode,
    }


@app.patch("/api/settings")
def save_preferences(payload: s.SettingsPatch, session: Session = DB):
    set_setting(session, "preferences", payload.model_dump())
    session.commit()
    return preferences(session)


@app.get("/api/auth/chatgpt/status")
def connection_status(request: Request):
    response = JSONResponse(auth.status())
    if not request.cookies.get("mra_browser"):
        response.set_cookie(
            "mra_browser", secrets.token_urlsafe(40), httponly=True, samesite="lax", max_age=86400
        )
    return response


@app.post("/api/auth/chatgpt/start")
def connect(request: Request):
    return connect_response(request)


def connect_response(request: Request, *, new_account=False):
    browser = request.cookies.get("mra_browser") or secrets.token_urlsafe(40)
    response = JSONResponse({"redirect": auth.begin(browser, new_account=new_account)})
    response.set_cookie("mra_browser", browser, httponly=True, samesite="lax", max_age=86400)
    return response


@app.get("/api/auth/chatgpt/authorize/{state}")
def authorize(state: str, request: Request):
    return RedirectResponse(
        auth.authorize_url(state, request.cookies.get("mra_browser", "")), status_code=303
    )


@app.get("/auth/callback")
def oauth_callback(request: Request):
    try:
        auth.callback(dict(request.query_params), request.cookies.get("mra_browser", ""))
        result = "connected"
    except Exception:
        # No raw errors or callback values in redirects/logs.
        result = "failed"
    return RedirectResponse("/settings?connection=" + result, status_code=303)


@app.post("/api/auth/chatgpt/disconnect")
def disconnect():
    return auth.disconnect()


@app.post("/api/auth/chatgpt/select")
def select_account(payload: s.AccountChoice):
    with auth.credentials() as data:
        if payload.account_id not in data["profiles"]:
            raise HTTPException(404, "Cuenta no encontrada")
        data["active"] = payload.account_id
    return auth.status()


@app.post("/api/auth/chatgpt/add-account")
def add_account(request: Request):
    return connect_response(request, new_account=True)


@app.post("/api/auth/chatgpt/usage-policy")
def usage_policy(payload: s.CreditPolicy):
    auth.update_profile(credits_zero_confirmed=payload.confirmed_zero_credits, quota_blocked=False)
    return auth.status()


@app.get("/api/providers/chatgpt/models")
def available_models():
    return auth.models()
