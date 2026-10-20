import uuid
import zipfile
from . import models as m
from .media import safe_path
from .repository import get, rows
from .transcripts import timestamp

NAMES = [
    "01-resumen-ejecutivo.md",
    "02-requisitos-funcionales.md",
    "03-requisitos-no-funcionales.md",
    "04-reglas-de-negocio.md",
    "05-historias-de-usuario.md",
    "06-criterios-aceptacion.md",
    "07-procesos.md",
    "08-modelo-conceptual.md",
    "09-preguntas-pendientes.md",
    "10-backlog.md",
    "11-matriz-trazabilidad.md",
]


def cell(value):
    return str(value).replace("|", "\\|").replace("\n", " ")


def criterion_status(value):
    return {"validated": "Validado", "rejected": "Rechazado"}.get(value, "Pendiente de validación")


def create_export(session, meeting):
    if not meeting.active_analysis_id:
        raise ValueError("Activa un análisis antes de exportar")
    run = get(session, m.AnalysisRun, meeting.active_analysis_id)
    project = get(session, m.Project, meeting.project_id)
    identity = str(uuid.uuid4())
    relative = f"{project.id}/{meeting.date.isoformat()}-{meeting.id}/{identity}"
    directory = safe_path("exports", relative)
    directory.mkdir(parents=True)
    requirements = rows(session, m.Requirement, m.Requirement.analysis_id == run.id)
    code_by_id = {r.id: r.code for r in requirements}
    code_by_generated = {r.original.get("code", r.code): r.code for r in requirements}
    stories = rows(session, m.UserStory, m.UserStory.analysis_id == run.id)
    criteria = rows(session, m.AcceptanceCriterion, m.AcceptanceCriterion.analysis_id == run.id)
    raw = run.original_result
    heading = f"Proyecto: {project.name}\nReunión: {meeting.title} ({meeting.date})\nAnálisis: {run.id}\nExportación: {identity}\n\n"
    documents = {}
    summary = "# Resumen ejecutivo\n\n" + heading
    for key, value in raw["summary"].items():
        summary += f"## {key.replace('_', ' ').capitalize()}\n\n"
        summary += ("\n".join("- " + v for v in value) if isinstance(value, list) else value) + "\n\n"
    documents[NAMES[0]] = summary
    for kind, name in (("functional", NAMES[1]), ("nonfunctional", NAMES[2])):
        content = (
            "# Requisitos " + ("funcionales" if kind == "functional" else "no funcionales") + "\n\n" + heading
        )
        for req in requirements:
            if req.kind != kind:
                continue
            content += f"## {req.code}: {req.title}\n\n{req.description}\n\n"
            content += f"- Estado: {req.status}\n- Interpretación: {req.interpretation}\n- Actor: {req.actor}\n- Módulo: {req.module}\n- Prioridad sugerida: {req.priority}\n"
            content += f"- Dependencias: {', '.join(code_by_id.get(code, code) for code in req.dependencies) or 'No indicadas'}\n- Observaciones: {req.observations}\n\n"
            for evidence in req.evidence:
                content += f"> {evidence.quote}\n\nSegmento `{evidence.segment_id}` · {timestamp(evidence.start)}–{timestamp(evidence.end)}\n\n"
            content += "\n".join("- Pregunta: " + question for question in req.questions) + "\n\n"
        documents[name] = content
    documents[NAMES[4]] = (
        "# Historias de usuario\n\n"
        + heading
        + "\n\n".join(
            f"## {story.code}\n\n{story.text}\n\nRequisitos: {', '.join(r.code for r in story.requirements)}"
            for story in stories
        )
    )
    documents[NAMES[5]] = (
        "# Criterios de aceptación\n\n"
        + heading
        + "\n\n".join(
            f"## {criterion.code} · {criterion.story_code}\n\nEstado: {criterion_status(criterion.status)}\nRevisión: {criterion.revision}\n\n- Given: {criterion.given}\n- When: {criterion.when}\n- Then: {criterion.then}\n\nRequisitos: {', '.join(r.code for r in criterion.requirements)}"
            + (
                "\n\n### Texto original generado\n\n"
                + "\n".join(f"- {key.capitalize()}: {original[key]}" for key in ("given", "when", "then"))
                if criterion.revisions
                and (original := next(c for c in raw["criteria"] if c["code"] == criterion.code))
                else ""
            )
            + (
                "\n\n### Historial de revisiones\n\n"
                + "\n\n".join(
                    f"#### Revisión {index + 1} · {entry['created_at']}\n\n"
                    f"Estado anterior: {criterion_status(entry['before']['status'])}\n"
                    f"Estado posterior: {criterion_status(entry['after']['status'])}\n\n"
                    f"Autor: {entry.get('actor', {}).get('label', 'Registro anterior sin identidad verificada')}\n\n"
                    f"Observaciones: {entry['observations']}\n\n"
                    + "\n".join(
                        f"- {key.capitalize()} anterior: {entry['before'][key]}\n"
                        f"- {key.capitalize()} posterior: {entry['after'][key]}"
                        for key in ("given", "when", "then")
                    )
                    for index, entry in enumerate(criterion.revisions)
                )
                if criterion.revisions
                else ""
            )
            for criterion in criteria
        )
    )
    for key, name, title in (
        ("business_rules", NAMES[3], "Reglas de negocio"),
        ("processes", NAMES[6], "Procesos AS-IS y TO-BE"),
        ("conceptual_model", NAMES[7], "Modelo conceptual"),
        ("questions", NAMES[8], "Preguntas pendientes y contradicciones"),
    ):
        content = f"# {title}\n\n" + heading
        for item in raw[key]:
            content += (
                item["text"]
                + "\n\n"
                + "\n".join(f"> {e['quote']} (segmento {e['segment_id']})" for e in item["evidence"])
                + "\n\n"
            )
        documents[name] = content or "Sin evidencia suficiente."
    documents[NAMES[9]] = (
        "# Backlog propuesto\n\n"
        + heading
        + "\n\n".join(
            f"## {item['code']} · {item['module']}\n\nHistoria: {item['story_code']}\n\nPrioridad sugerida: {item['priority']}\n\nEstado: {item['status']}\n\nRequisitos de origen: {', '.join(code_by_generated.get(code, code) for code in item['requirements'])}\n\nDependencias: {', '.join(item['dependencies']) or 'No indicadas'}"
            for item in raw["backlog"]
        )
    )
    matrix = (
        "# Matriz de trazabilidad\n\n"
        + heading
        + "| Requisito | Historia | Criterio | Backlog | Segmento | Tiempo | Estado |\n|---|---|---|---|---|---|---|\n"
    )
    for req in requirements:
        linked_stories = [s for s in stories if any(r.id == req.id for r in s.requirements)]
        for story in linked_stories or [None]:
            linked_criteria = [
                c
                for c in criteria
                if any(r.id == req.id for r in c.requirements)
                and (story is None or c.story_code == story.code)
            ]
            for criterion in linked_criteria or [None]:
                for evidence in req.evidence:
                    values = (
                        req.code,
                        story.code if story else "—",
                        criterion.code if criterion else "—",
                        ", ".join(
                            item["code"]
                            for item in raw["backlog"]
                            if req.original.get("code") in item["requirements"]
                            and (story is None or item["story_code"] == story.code)
                        )
                        or "—",
                        evidence.segment_id,
                        timestamp(evidence.start),
                        req.status,
                    )
                    matrix += "| " + " | ".join(cell(v) for v in values) + " |\n"
    documents[NAMES[10]] = matrix
    # Export the exact reviewed input associated with this analysis, not a later incompatible revision.
    documents["transcripcion-revisada.txt"] = "\n".join(s["text"] for s in run.input_snapshot["segments"])
    for name, content in documents.items():
        (directory / name).write_text(content, encoding="utf-8")
    with zipfile.ZipFile(directory / "documentos.zip", "x", zipfile.ZIP_DEFLATED) as archive:
        for name, content in documents.items():
            archive.writestr(name, content)
    artifact = m.ExportArtifact(
        id=identity, meeting_id=meeting.id, analysis_id=run.id, path=relative, files=list(documents)
    )
    session.add(artifact)
    return artifact
