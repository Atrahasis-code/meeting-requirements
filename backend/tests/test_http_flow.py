"""Cross-container integration. Run only with the isolated Compose test stack."""

import io
import os
import time
import wave
import httpx
import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("MRA_TEST_BASE_URL"), reason="Requires Compose integration stack"
)


def test_http_pipeline_with_real_worker_and_ffprobe():
    with httpx.Client(base_url=os.environ["MRA_TEST_BASE_URL"], timeout=30) as client:
        project = client.post("/api/projects", json={"name": "Integración Docker"}).json()
        meeting = client.post(
            "/api/meetings",
            json={"project_id": project["id"], "title": "Prueba sintética", "date": "2026-10-19"},
        ).json()
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(16000)
            audio.writeframes(b"\0\0" * 16000)
        result = client.post(
            f"/api/meetings/{meeting['id']}/upload",
            files={"file": ("sample.wav", buffer.getvalue(), "audio/wav")},
        )
        assert result.status_code == 201, result.text
        assert result.json()["jobs"] == []

        def wait(identity):
            for _ in range(120):
                job = client.get("/api/jobs/" + identity).json()
                if job["status"] == "completed":
                    return
                assert job["status"] not in {"failed", "interrupted", "blocked"}, job
                time.sleep(0.5)
            pytest.fail("Worker timeout")

        job = client.post(f"/api/meetings/{meeting['id']}/transcribe").json()
        wait(job["id"])
        transcript = client.get(f"/api/meetings/{meeting['id']}/transcript").json()
        assert transcript["complete"]
        segment = transcript["segments"][0]
        assert (
            client.patch(
                "/api/transcript-segments/" + segment["id"],
                json={
                    "revision": transcript["revision"],
                    "revised_text": "Se requiere registrar solicitudes.",
                    "reviewed": True,
                },
            ).status_code
            == 200
        )
        entry = client.get(f"/api/meetings/{meeting['id']}/analysis-input").json()
        job = client.post(
            f"/api/meetings/{meeting['id']}/analyze",
            json={"input_hash": entry["input_hash"], "consent": True},
        ).json()
        wait(job["id"])
        runs = client.get(f"/api/meetings/{meeting['id']}/analyses").json()
        requirement = runs[0]["requirements"][0]
        assert (
            client.post(
                "/api/requirements/" + requirement["id"] + "/validate", json={"status": "validated"}
            ).status_code
            == 200
        )
        artifact = client.post(f"/api/meetings/{meeting['id']}/export").json()
        assert client.get("/api/exports/" + artifact["id"] + "/download").content.startswith(b"PK")
        assert client.delete("/api/projects/" + project["id"] + "?confirm=true").status_code == 204
