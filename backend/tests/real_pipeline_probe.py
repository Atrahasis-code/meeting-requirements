"""Opt-in real Whisper + Mock analysis, isolated data, reusable model cache only."""

import json
import os
import platform
import resource
import subprocess
import tempfile
import threading
import time
from pathlib import Path


def main():
    start = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="mra-real-pipeline-", dir="/tmp") as directory:
        root = Path(directory)
        for area in ("db", "media", "transcripts", "exports", "auth"):
            (root / area).mkdir()
        (root / "models").symlink_to("/data/models", target_is_directory=True)
        os.environ.update(
            MRA_DATA_ROOT=directory,
            MRA_ANALYSIS_PROVIDER="mock",
            MRA_TRANSCRIPTION_PROVIDER="whisper",
            MRA_TEST_MODE="false",
        )
        from app.initialize import main as initialize

        initialize()
        from fastapi.testclient import TestClient
        from app.main import app
        from app.worker import claim
        from app.processing import transcribe, analyze

        audio = root / "synthetic.wav"
        subprocess.run(
            [
                "ffmpeg",
                "-nostdin",
                "-v",
                "error",
                "-f",
                "lavfi",
                "-i",
                "flite=text='The system must register requests and allow users to check their status. A reviewer validates requirements.':voice=slt",
                "-ar",
                "16000",
                str(audio),
            ],
            check=True,
        )
        with TestClient(app) as client:
            preferences = client.patch(
                "/api/settings",
                json={"provider": "mock", "profile": "balanced", "language": "en", "model": None},
            )
            assert preferences.status_code == 200
            project = client.post("/api/projects", json={"name": "Real CPU synthetic probe"}).json()
            meeting = client.post(
                "/api/meetings",
                json={
                    "project_id": project["id"],
                    "title": "Synthetic real Whisper",
                    "date": "2026-10-19",
                    "profile": "balanced",
                    "language": "en",
                },
            ).json()
            response = client.post(
                f"/api/meetings/{meeting['id']}/upload",
                files={"file": ("synthetic.wav", audio.read_bytes(), "audio/wav")},
            )
            assert response.status_code == 201, response.text
            job = client.post(f"/api/meetings/{meeting['id']}/transcribe").json()
            assert claim() == job["id"]
            transcribe(job["id"], threading.Event())
            transcript = client.get(f"/api/meetings/{meeting['id']}/transcript").json()
            assert transcript["complete"] and transcript["segments"]
            for format in ("txt", "json", "srt", "vtt"):
                assert (
                    client.get(
                        f"/api/meetings/{meeting['id']}/transcript/download?format={format}"
                    ).status_code
                    == 200
                )
            entry = client.get(f"/api/meetings/{meeting['id']}/analysis-input").json()
            job = client.post(
                f"/api/meetings/{meeting['id']}/analyze",
                json={"input_hash": entry["input_hash"], "consent": True},
            ).json()
            assert claim() == job["id"]
            analyze(job["id"], threading.Event())
            runs = client.get(f"/api/meetings/{meeting['id']}/analyses").json()
            assert runs[0]["provider"] == "mock" and runs[0]["requirements"]
            artifact = client.post(f"/api/meetings/{meeting['id']}/export").json()
            assert client.get(f"/api/exports/{artifact['id']}/download").content.startswith(b"PK")
        print(
            json.dumps(
                {
                    "architecture": platform.machine(),
                    "real_whisper": True,
                    "analysis_provider": "mock",
                    "segments": len(transcript["segments"]),
                    "requirements": len(runs[0]["requirements"]),
                    "export": "zip",
                    "seconds": round(time.monotonic() - start, 2),
                    "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                }
            )
        )


if __name__ == "__main__":
    main()
