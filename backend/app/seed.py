"""Explicit synthetic demo data; never runs automatically or calls an external provider."""

import threading
from datetime import date
from .db import SessionLocal
from . import models as m
from .analysis import snapshot, input_hash, store_result
from .providers import MockAnalysisProvider


def main():
    with SessionLocal.begin() as session:
        project = m.Project(
            name="DEMO · Portal de solicitudes",
            description="Datos sintéticos para explorar el flujo de revisión.",
            context="Ejemplo ficticio: un equipo define un portal interno de solicitudes.",
            glossary={
                "Solicitud": "Petición registrada por una persona usuaria",
                "Responsable": "Rol que revisa una solicitud",
            },
        )
        session.add(project)
        session.flush()
        meeting = m.Meeting(
            project_id=project.id,
            title="DEMO · Descubrimiento inicial",
            date=date.today(),
            status="transcribed",
            transcript_revision=1,
            profile="balanced",
            language="es",
        )
        session.add(meeting)
        session.flush()
        for start, content in (
            (0, "El portal debe permitir registrar solicitudes y consultar su estado."),
            (15, "La persona responsable debe revisar cada solicitud antes de aprobarla."),
            (
                30,
                "Todavía no hemos decidido qué datos serán obligatorios. Debemos aclararlo en la próxima reunión.",
            ),
        ):
            session.add(
                m.TranscriptSegment(
                    meeting_id=meeting.id,
                    start=start,
                    end=start + 12,
                    original_text=content,
                    detection={"synthetic_demo": True},
                )
            )
        session.flush()
        data = snapshot(session, meeting)
        data["provider"] = "mock"
        job = m.ProcessingJob(
            meeting_id=meeting.id,
            kind="analyze",
            status="running",
            params={"snapshot": data, "input_hash": input_hash(data), "demo": True},
        )
        session.add(job)
        session.flush()
        result = MockAnalysisProvider().analyze(data, threading.Event())
        store_result(session, job, result)
    print(
        "Datos DEMO creados. Proveedor predeterminado sin cambios. No se realizó ninguna inferencia externa."
    )


if __name__ == "__main__":
    main()
