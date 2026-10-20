"""Host-controlled Compose recovery probe; never used by the normal application."""

import json
import sys
import time
from pathlib import Path
from datetime import date
import httpx
from app import models as m
from app.config import settings
from app.db import SessionLocal
from app.repository import get, set_setting

STATE = Path("/tmp/mra-worker-probe.json")


def prepare():
    assert settings.test_mode, "Recovery probes require the isolated test configuration"
    with SessionLocal.begin() as session:
        set_setting(session, "preferences", {"provider": "mock", "model": None})
        project = m.Project(name="Worker recovery synthetic test", context="", glossary={})
        session.add(project)
        session.flush()
        meeting = m.Meeting(
            project_id=project.id,
            title="Synthetic recovery",
            date=date.today(),
            status="transcribed",
            transcript_revision=1,
            profile="balanced",
            language="es",
        )
        session.add(meeting)
        session.flush()
        identity = meeting.id
        for index in range(1000):
            content = (
                f"Necesidad sintética {index}. "
                + "El sistema debe registrar solicitudes pendientes de revisión. " * 160
            )[:9000]
            session.add(
                m.TranscriptSegment(
                    meeting_id=identity, start=index * 10, end=index * 10 + 8, original_text=content
                )
            )
    with httpx.Client(base_url="http://127.0.0.1:8000", timeout=60) as client:
        entry = client.get(f"/api/meetings/{identity}/analysis-input")
        entry.raise_for_status()
        response = client.post(
            f"/api/meetings/{identity}/analyze",
            json={"input_hash": entry.json()["input_hash"], "consent": True},
        )
        response.raise_for_status()
    STATE.write_text(json.dumps({"job_id": response.json()["id"]}))
    print("Synthetic Mock analysis queued")


def checkpoint():
    state = json.loads(STATE.read_text())
    identity = state["job_id"]
    minimum = state.get("blocks", 0) + 3
    for _ in range(600):
        with SessionLocal() as session:
            job = get(session, m.ProcessingJob, identity)
            count = len(job.checkpoint.get("blocks", []))
            if job.status == "running" and count >= minimum:
                STATE.write_text(json.dumps({"job_id": identity, "blocks": count}))
                print(f"Active processing confirmed with {count} saved checkpoints")
                return
            assert job.status not in {"completed", "failed", "blocked", "cancelled"}, job.status
        time.sleep(0.1)
    raise AssertionError("No active processing/checkpoint observed")


def recovered():
    state = json.loads(STATE.read_text())
    with SessionLocal() as session:
        job = get(session, m.ProcessingJob, state["job_id"])
        assert job.status == "interrupted", job.status
        assert len(job.checkpoint.get("blocks", [])) >= state["blocks"]
    time.sleep(1)
    with SessionLocal() as session:
        assert get(session, m.ProcessingJob, state["job_id"]).status == "interrupted"
    print("Interrupted job and checkpoints preserved; no automatic inference: PASS")


def resume():
    state = json.loads(STATE.read_text())
    with SessionLocal() as session:
        job = get(session, m.ProcessingJob, state["job_id"])
        meeting_id = job.meeting_id
        blocks = len(job.checkpoint.get("blocks", []))
    with httpx.Client(base_url="http://127.0.0.1:8000", timeout=60) as client:
        entry = client.get(f"/api/meetings/{meeting_id}/analysis-input")
        entry.raise_for_status()
        response = client.post(
            f"/api/jobs/{state['job_id']}/retry",
            json={"input_hash": entry.json()["input_hash"], "consent": True},
        )
        response.raise_for_status()
    STATE.write_text(json.dumps({"job_id": response.json()["id"], "blocks": blocks}))
    print("Manual retry authorized for synthetic Mock data")


def cancel():
    state = json.loads(STATE.read_text())
    with httpx.Client(base_url="http://127.0.0.1:8000", timeout=60) as client:
        response = client.post(f"/api/jobs/{state['job_id']}/cancel")
        response.raise_for_status()
    for _ in range(120):
        with SessionLocal() as session:
            job = get(session, m.ProcessingJob, state["job_id"])
            if job.status == "cancelled":
                assert len(job.checkpoint.get("blocks", [])) >= state["blocks"]
                print("Manual cancellation preserves checkpoints: PASS")
                return
            assert job.status in {"queued", "running"}, job.status
        time.sleep(0.5)
    raise AssertionError("Cancellation did not complete")


if __name__ == "__main__":
    {
        "prepare": prepare,
        "checkpoint": checkpoint,
        "recovered": recovered,
        "resume": resume,
        "cancel": cancel,
    }[sys.argv[1]]()
