"""Full HTTP integration through loopback/Nginx in an isolated Compose stack.

The runner shares the frontend network namespace, so localhost is the real
Nginx listener. These tests never need host ports, accounts or model downloads.
"""

import io
import os
import sys
import time
import wave
import zipfile
from urllib.parse import urlsplit

import httpx
import pytest

from app.analysis import validate_evidence
from app.schemas import AnalysisResult

# Independent export contract: changing the exporter must not silently reduce
# the eleven documents promised by the local edition.
DOCUMENTS = {
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
}

pytestmark = pytest.mark.skipif(
    not os.getenv("MRA_TEST_BASE_URL"), reason="Requires Compose integration stack"
)


def checked(client, method, path, expected=200, **kwargs):
    response = client.request(method, path, **kwargs)
    # Do not echo request/response bodies or meeting contents in test logs.
    assert response.status_code == expected, (method, path, response.status_code)
    assert response.headers["access-control-allow-origin"] == client.headers["origin"]
    assert response.headers["access-control-allow-credentials"] == "true"
    return response


def wait_for_job(client, identity):
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        job = checked(client, "GET", "/api/jobs/" + identity).json()
        if job["status"] == "completed":
            return
        assert job["status"] in {"queued", "running"}, job["status"]
        time.sleep(0.25)
    pytest.fail("Isolated worker did not complete the job within 60 seconds")


@pytest.mark.parametrize("hostname", ["localhost", "127.0.0.1"])
def test_loopback_full_flow_with_worker_criteria_and_immutable_exports(hostname):
    configured = urlsplit(os.environ["MRA_TEST_BASE_URL"])
    assert configured.scheme == "http" and configured.hostname in {"localhost", "127.0.0.1"}
    assert configured.port == 8080
    origin = f"http://{hostname}:8080"
    with httpx.Client(
        base_url=origin,
        headers={"Origin": origin, "Sec-Fetch-Site": "same-origin"},
        timeout=30,
        trust_env=False,
    ) as client:
        # Fail before writing anything if this is not an explicit Mock test stack.
        preferences = checked(client, "GET", "/api/settings").json()
        assert preferences["test_mode"] is True and preferences["provider"] == "mock"
        assert checked(client, "GET", "/api/health").json()["worker_online"] is True
        preflight = checked(
            client,
            "OPTIONS",
            "/api/projects",
            headers={
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        assert "POST" in preflight.headers["access-control-allow-methods"]
        project = checked(
            client, "POST", "/api/projects", 201, json={"name": "Loopback integration fixture"}
        ).json()
        try:
            meeting = checked(
                client,
                "POST",
                "/api/meetings",
                201,
                json={
                    "project_id": project["id"],
                    "title": "Synthetic loopback meeting",
                    "date": "2026-10-20",
                },
            ).json()
            meeting_path = "/api/meetings/" + meeting["id"]
            buffer = io.BytesIO()
            with wave.open(buffer, "wb") as audio:
                audio.setnchannels(1)
                audio.setsampwidth(2)
                audio.setframerate(16000)
                audio.writeframes(b"\0\0" * 16000)
            uploaded = checked(
                client,
                "POST",
                meeting_path + "/upload",
                201,
                files={
                    "file": ("synthetic.wav", buffer.getvalue(), "audio/wav"),
                },
            ).json()
            assert uploaded["media"]["original_name"] == "synthetic.wav"
            assert uploaded["jobs"] == []  # Upload never starts processing automatically.
            job = checked(client, "POST", meeting_path + "/transcribe", 202).json()
            wait_for_job(client, job["id"])
            transcript = checked(client, "GET", meeting_path + "/transcript").json()
            assert transcript["complete"] is True
            segment = transcript["segments"][0]
            assert segment["detection"]["simulated"] is True
            reviewed = "El sistema debe registrar solicitudes y mostrar su estado."
            checked(
                client,
                "PATCH",
                "/api/transcript-segments/" + segment["id"],
                json={
                    "revision": transcript["revision"],
                    "revised_text": reviewed,
                    "reviewed": True,
                },
            )
            saved = checked(client, "GET", meeting_path + "/transcript").json()["segments"][0]
            assert saved["original_text"] == segment["original_text"]
            assert saved["revised_text"] == reviewed and saved["reviewed"] is True
            # Reversible exclusion is enforced through the real proxy/API, not just the UI.
            current_revision = checked(client, "GET", meeting_path + "/transcript").json()["revision"]
            discarded = checked(
                client,
                "PATCH",
                "/api/transcript-segments/" + segment["id"],
                json={"revision": current_revision, "discarded": True},
            ).json()
            assert discarded["segment"]["discarded"] and not discarded["segment"]["reviewed"]
            excluded = checked(client, "GET", meeting_path + "/analysis-input").json()
            assert excluded["snapshot"]["segments"] == []
            assert excluded["snapshot"]["selection_summary"]["discarded"] == 1
            checked(
                client,
                "POST",
                meeting_path + "/analyze",
                422,
                json={"input_hash": excluded["input_hash"], "consent": True},
            )
            downloaded = checked(client, "GET", meeting_path + "/transcript/download?format=json").json()
            assert downloaded[0]["discarded"] and downloaded[0]["original_text"] == segment["original_text"]
            checked(
                client,
                "PATCH",
                "/api/transcript-segments/" + segment["id"],
                json={"revision": discarded["revision"], "reviewed": True},
            )
            entry = checked(client, "GET", meeting_path + "/analysis-input").json()
            assert entry["snapshot"]["selection_policy"] == "reviewed_only_v1"
            assert entry["snapshot"]["provider"] == "mock"
            assert entry["snapshot"]["segments"][0]["text"] == reviewed
            job = checked(
                client,
                "POST",
                meeting_path + "/analyze",
                202,
                json={
                    "input_hash": entry["input_hash"],
                    "consent": True,
                },
            ).json()
            wait_for_job(client, job["id"])
            run = checked(client, "GET", meeting_path + "/analyses").json()[0]
            assert run["active"] is True and run["provider"] == "mock"
            assert run["requirements"] and run["criteria"]
            assert run["input_snapshot"] == entry["snapshot"]
            validate_evidence(AnalysisResult.model_validate(run["original_result"]), entry["snapshot"])
            initial_statuses = {r["id"]: r["status"] for r in run["requirements"]}
            first = checked(client, "POST", meeting_path + "/export", 201).json()
            first_zip = checked(client, "GET", "/api/exports/" + first["id"] + "/download").content
            for criterion in run["criteria"]:
                assert criterion["status"] == "pending_validation"
                path = "/api/criteria/" + criterion["id"]
                decision = checked(
                    client,
                    "POST",
                    path + "/validate",
                    json={
                        "revision": criterion["revision"],
                        "status": "validated",
                        "observations": "Explicit approval of isolated synthetic test data",
                    },
                ).json()
                persisted = checked(client, "GET", path).json()
                assert {key: persisted[key] for key in decision} == decision
                assert persisted["active"] is True and persisted["meeting_id"] == meeting["id"]
                assert persisted["status"] == "validated"
                assert persisted["revision"] == criterion["revision"] + 1
                assert persisted["original"] == criterion["original"]
                history = persisted["revisions"][-1]
                assert history["action"] == "validation" and history["created_at"]
                assert history["before"]["status"] == "pending_validation"
                assert history["after"]["status"] == "validated"
                assert history["actor"] == {"id": "local-owner", "label": "Usuario local", "kind": "local"}
            current = checked(client, "GET", meeting_path + "/analyses").json()[0]
            assert current["original_result"] == run["original_result"]
            assert {r["id"]: r["status"] for r in current["requirements"]} == initial_statuses
            assert all(c["status"] == "validated" for c in current["criteria"])
            latest = checked(client, "POST", meeting_path + "/export", 201).json()
            assert latest["id"] != first["id"]
            archive_bytes = checked(client, "GET", "/api/exports/" + latest["id"] + "/download").content
            with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
                assert archive.testzip() is None
                assert set(archive.namelist()) == DOCUMENTS | {"transcripcion-revisada.txt"}
                assert len(archive.namelist()) == 12
                criteria = archive.read("06-criterios-aceptacion.md").decode()
                requirements = archive.read("02-requisitos-funcionales.md").decode()
                trace = archive.read("11-matriz-trazabilidad.md").decode()
                assert archive.read("transcripcion-revisada.txt").decode() == reviewed
                for phrase in (
                    "Estado: Validado",
                    "Texto original generado",
                    "Historial de revisiones",
                    "Usuario local",
                ):
                    assert phrase in criteria
                for criterion in current["criteria"]:
                    assert criterion["code"] in criteria and criterion["code"] in trace
                for requirement in current["requirements"]:
                    assert requirement["code"] in requirements and requirement["code"] in trace
                    assert requirement["evidence"]
                    for evidence in requirement["evidence"]:
                        assert evidence["quote"] in requirements and evidence["quote"] in reviewed
                        assert evidence["segment_id"] in requirements and evidence["segment_id"] in trace
            assert checked(client, "GET", "/api/exports/" + first["id"] + "/download").content == first_zip
            with zipfile.ZipFile(io.BytesIO(first_zip)) as archive:
                assert (
                    "Estado: Pendiente de validación" in archive.read("06-criterios-aceptacion.md").decode()
                )
            assert len(checked(client, "GET", meeting_path + "/exports").json()) == 2
        finally:
            # Delete only the UUID created by a passing case. Preserve failed fixtures.
            if sys.exc_info()[0] is None:
                checked(client, "DELETE", "/api/projects/" + project["id"] + "?confirm=true", 204)


def test_proxy_keeps_external_origins_blocked():
    with httpx.Client(base_url=os.environ["MRA_TEST_BASE_URL"], trust_env=False) as client:
        response = client.post("/api/health", headers={"Origin": "https://attacker.invalid"})
        assert response.status_code == 403
        response = client.options(
            "/api/projects",
            headers={
                "Origin": "https://attacker.invalid",
                "Access-Control-Request-Method": "POST",
            },
        )
        assert response.status_code == 400
        assert "access-control-allow-origin" not in response.headers
