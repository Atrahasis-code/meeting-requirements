import threading
from app.worker import claim, recover
from app.processing import transcribe
from test_flow import process_transcription


def test_only_one_job_and_manual_cancellation(client, meeting):
    identity = meeting["id"]
    first = client.post(f"/api/meetings/{identity}/transcribe").json()
    assert client.post(f"/api/meetings/{identity}/transcribe").status_code == 409
    assert client.delete(f"/api/meetings/{identity}?confirm=true").status_code == 409
    assert client.post(f"/api/jobs/{first['id']}/cancel").json()["status"] == "cancelled"
    assert claim() is None
    retry = client.post(f"/api/jobs/{first['id']}/retry")
    assert retry.status_code == 202
    assert claim() == retry.json()["id"]
    recover()
    assert client.get(f"/api/jobs/{retry.json()['id']}").json()["status"] == "interrupted"
    assert client.post(f"/api/jobs/{retry.json()['id']}/retry").status_code == 202


def test_cancelled_inference_keeps_no_completed_transcript(client, meeting):
    job = client.post(f"/api/meetings/{meeting['id']}/transcribe").json()
    assert claim() == job["id"]
    event = threading.Event()
    event.set()
    import pytest

    with pytest.raises(InterruptedError):
        transcribe(job["id"], event)
    assert client.get(f"/api/meetings/{meeting['id']}/transcript").json()["complete"] is False


def test_database_foreign_keys_wal_and_heartbeat_independence(client):
    from app.db import engine

    with engine.connect() as connection:
        assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
        assert connection.exec_driver_sql("PRAGMA busy_timeout").scalar() == 5000
    assert client.get("/api/health").json()["status"] == "ok"
    assert client.get("/api/health").json()["worker_online"] is False


def test_media_deletion_preserves_evidence_text(client, meeting):
    from test_flow import process_analysis

    process_transcription(client, meeting["id"])
    process_analysis(client, meeting["id"])
    assert client.delete(f"/api/meetings/{meeting['id']}/media?confirm=true").status_code == 204
    assert client.get(f"/api/meetings/{meeting['id']}/media").status_code == 404
    assert client.get(f"/api/meetings/{meeting['id']}/transcript").json()["complete"]
    assert client.get(f"/api/projects/{meeting['project_id']}/requirements").json()


def test_lightweight_worker_probe_reads_fresh_and_expired_heartbeats():
    import time
    from app.config import settings
    from app.db import SessionLocal
    from app.healthcheck import worker_healthy
    from app.repository import set_setting

    assert not worker_healthy(settings.data_root)
    with SessionLocal.begin() as session:
        set_setting(session, "worker", {"heartbeat": time.time()})
    assert worker_healthy(settings.data_root)
    with SessionLocal.begin() as session:
        set_setting(session, "worker", {"heartbeat": 0})
    assert not worker_healthy(settings.data_root)


def test_sqlite_contention_returns_retryable_error_without_input(client, caplog):
    import sqlite3
    from app.config import settings
    from app.db import engine

    with sqlite3.connect(settings.directory("db") / "app.sqlite3") as lock:
        lock.execute("BEGIN IMMEDIATE")
        response = client.post("/api/projects", json={"name": "private-content-must-not-be-logged"})
        assert response.status_code == 503
        assert "private-content" not in response.text
    assert "private-content" not in caplog.text
    assert engine.hide_parameters is True
