import hashlib
import json
import re
from sqlalchemy import func, select
from . import models as m
from .repository import get, setting
from .config import settings
from .schemas import AnalysisResult
from .transcripts import text

SELECTION_POLICY = "reviewed_only_v1"


def require_selection(data):
    if data.get("selection_policy") != SELECTION_POLICY:
        from .providers import ProviderBlocked

        raise ProviderBlocked(
            "review_required",
            "Revisa los bloques y autoriza nuevamente el análisis; cambió la política de selección",
        )


def snapshot(session, meeting):
    project = get(session, m.Project, meeting.project_id)
    segments = session.scalars(
        select(m.TranscriptSegment)
        .where(m.TranscriptSegment.meeting_id == meeting.id)
        .order_by(m.TranscriptSegment.start)
    ).all()
    from .runtime import runtime

    options = runtime.analysis_options(setting(session, "preferences", {}))
    provider_name = options.get("provider", settings.analysis_provider)
    from .auth import status

    return dict(
        selection_policy=SELECTION_POLICY,
        selection_summary=dict(
            total=len(segments),
            reviewed=sum(s.reviewed for s in segments),
            discarded=sum(s.discarded for s in segments),
            pending=sum(not s.reviewed and not s.discarded for s in segments),
            included=sum(s.reviewed and not s.discarded and bool(text(s).strip()) for s in segments),
        ),
        meeting_id=meeting.id,
        revision=meeting.transcript_revision,
        context=project.context,
        glossary=project.glossary,
        provider=provider_name,
        account_id=status()["account_id"] if provider_name == "chatgpt" else None,
        model=options.get("model"),
        segments=[
            dict(id=s.id, start=s.start, end=s.end, text=text(s), doubtful=s.doubtful)
            for s in segments
            if s.reviewed and not s.discarded and text(s).strip()
        ],
    )


def input_hash(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def normalize(value):
    return re.sub(r"\s+", " ", value).strip()


def validate_evidence(result: AnalysisResult, data):
    segments = {s["id"]: s for s in data["segments"]}
    seen = set()
    for item in [
        *result.requirements,
        *result.business_rules,
        *result.questions,
        *result.processes,
        *result.conceptual_model,
    ]:
        if not item.evidence:
            raise ValueError("Cada hallazgo debe citar evidencia")
        for evidence in item.evidence:
            if evidence.segment_id not in segments or normalize(evidence.quote) not in normalize(
                segments[evidence.segment_id]["text"]
            ):
                raise ValueError("Evidencia inexistente o cita ajena a la entrada autorizada")
    for req in result.requirements:
        key = (req.kind, normalize(req.description).casefold())
        if key in seen:
            raise ValueError("Requisito duplicado")
        seen.add(key)
        if req.code.startswith("RF") != (req.kind == "functional"):
            raise ValueError("Código incompatible con el tipo de requisito")
    return result


def store_result(session, job, result):
    from .runtime import runtime

    runtime.before_complete(session, job)
    meeting = get(session, m.Meeting, job.meeting_id)
    data = job.params["snapshot"]
    validate_evidence(result, data)
    run = m.AnalysisRun(
        meeting_id=meeting.id,
        job_id=job.id,
        provider=data["provider"],
        input_snapshot=data,
        original_result=result.model_dump(),
    )
    session.add(run)
    session.flush()
    if session.bind.dialect.name == "postgresql":
        session.execute(
            select(m.Project).where(m.Project.id == meeting.project_id).with_for_update()
        ).scalar_one()
    mapping = {}
    segments = {s["id"]: s for s in data["segments"]}
    count = session.scalar(
        select(func.count()).select_from(m.Requirement).where(m.Requirement.project_id == meeting.project_id)
    )
    for index, generated in enumerate(result.requirements, count + 1):
        raw = generated.model_dump()
        fields = {
            k: raw[k]
            for k in (
                "kind",
                "title",
                "description",
                "actor",
                "module",
                "priority",
                "status",
                "interpretation",
                "questions",
            )
        }
        requirement = m.Requirement(
            project_id=meeting.project_id,
            analysis_id=run.id,
            code=f"{'RF' if generated.kind == 'functional' else 'RN'}-{index:03}",
            original=raw,
            **fields,
        )
        session.add(requirement)
        session.flush()
        mapping[generated.code] = requirement
        for e in generated.evidence:
            segment = segments[e.segment_id]
            requirement.evidence.append(
                m.EvidenceReference(
                    segment_id=e.segment_id, quote=e.quote, start=segment["start"], end=segment["end"]
                )
            )
    for generated in result.requirements:
        mapping[generated.code].dependencies = [mapping[c].id for c in generated.dependencies]
    for story in result.stories:
        session.add(
            m.UserStory(
                analysis_id=run.id,
                code=story.code,
                text=story.text,
                requirements=[mapping[c] for c in story.requirements],
            )
        )
    for criterion in result.criteria:
        session.add(
            m.AcceptanceCriterion(
                analysis_id=run.id,
                code=criterion.code,
                story_code=criterion.story_code,
                given=criterion.given,
                when=criterion.when,
                then=criterion.then,
                requirements=[mapping[c] for c in criterion.requirements],
            )
        )
    for items, model in ((result.business_rules, m.BusinessRule), (result.questions, m.OpenQuestion)):
        for item in items:
            session.add(
                model(analysis_id=run.id, text=item.text, evidence=[e.model_dump() for e in item.evidence])
            )
    if meeting.active_analysis_id is None:
        meeting.active_analysis_id = run.id
    meeting.status = "completed"
    job.status, job.stage, job.progress = "completed", "completed", 1.0
    return run


def split_input(data):
    blocks, current, length = [], [], 0
    for segment in data["segments"]:
        if current and length + len(segment["text"]) > settings.analysis_chunk_chars:
            blocks.append({**data, "segments": current})
            current, length = [], 0
        current.append(segment)
        length += len(segment["text"])
    if current:
        blocks.append({**data, "segments": current})
    return blocks


def merge_results(results):
    # Re-number block-local identifiers and merge exact duplicates with combined evidence.
    combined = AnalysisResult(summary={})
    canonical = {}
    for result in results:
        mapping = {}
        for req in result.requirements:
            key = (req.kind, normalize(req.description).casefold())
            if key in canonical:
                existing = canonical[key]
                existing.evidence = list(
                    {(e.segment_id, e.quote): e for e in [*existing.evidence, *req.evidence]}.values()
                )
                mapping[req.code] = existing.code
            else:
                new_code = f"{'RF' if req.kind == 'functional' else 'RN'}-{len(combined.requirements) + 1:03}"
                mapping[req.code] = new_code
                copy = req.model_copy(deep=True)
                copy.code = new_code
                # Dependencies still use block-local codes here. Start clean and
                # translate them once the complete block mapping is available.
                copy.dependencies = []
                canonical[key] = copy
                combined.requirements.append(copy)
        for req in result.requirements:
            target = next(r for r in combined.requirements if r.code == mapping[req.code])
            target.dependencies = list(
                dict.fromkeys([*target.dependencies, *(mapping[c] for c in req.dependencies)])
            )
        story_map = {}
        for story in result.stories:
            copy = story.model_copy(deep=True)
            copy.code = f"HU-{len(combined.stories) + 1:03}"
            story_map[story.code] = copy.code
            copy.requirements = list(dict.fromkeys(mapping[c] for c in story.requirements))
            combined.stories.append(copy)
        for criterion in result.criteria:
            copy = criterion.model_copy(deep=True)
            copy.code = f"CA-{len(combined.criteria) + 1:03}"
            copy.story_code = story_map[criterion.story_code]
            copy.requirements = list(dict.fromkeys(mapping[c] for c in criterion.requirements))
            combined.criteria.append(copy)
        backlog_map = {
            item.code: f"BL-{len(combined.backlog) + index:03}"
            for index, item in enumerate(result.backlog, 1)
        }
        for item in result.backlog:
            copy = item.model_copy(deep=True)
            copy.code = backlog_map[item.code]
            copy.dependencies = [backlog_map[code] for code in item.dependencies]
            copy.story_code = story_map[item.story_code]
            copy.requirements = list(dict.fromkeys(mapping[c] for c in item.requirements))
            combined.backlog.append(copy)
        for name in ("business_rules", "questions", "processes", "conceptual_model"):
            getattr(combined, name).extend(getattr(result, name))
        for name, value in result.summary.model_dump().items():
            existing = getattr(combined.summary, name)
            setattr(
                combined.summary,
                name,
                (existing + "\n" + value).strip()
                if isinstance(value, str)
                else list(dict.fromkeys(existing + value)),
            )
    return AnalysisResult.model_validate(combined.model_dump())
