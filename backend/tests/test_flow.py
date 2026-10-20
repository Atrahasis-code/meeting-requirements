import io
import threading
import zipfile
from app.processing import analyze, transcribe
from app.worker import claim


def process_transcription(client, identity):
    response = client.post(f"/api/meetings/{identity}/transcribe")
    assert response.status_code == 202, response.text
    job = response.json()
    assert claim() == job["id"]
    transcribe(job["id"], threading.Event())
    return job


def process_analysis(client, identity):
    data = client.get(f"/api/meetings/{identity}/analysis-input").json()
    response = client.post(
        f"/api/meetings/{identity}/analyze", json={"input_hash": data["input_hash"], "consent": True}
    )
    assert response.status_code == 202, response.text
    assert claim() == response.json()["id"]
    analyze(response.json()["id"], threading.Event())
    return response.json()


def test_complete_flow_preserves_original_and_exports_edits(client, meeting):
    identity = meeting["id"]
    assert client.get(f"/api/meetings/{identity}").json()["jobs"] == []
    process_transcription(client, identity)
    transcript = client.get(f"/api/meetings/{identity}/transcript").json()
    segment = transcript["segments"][0]
    edited = client.patch(
        f"/api/transcript-segments/{segment['id']}",
        json={
            "revised_text": "El portal debe registrar solicitudes.",
            "reviewed": True,
            "doubtful": True,
            "revision": transcript["revision"],
        },
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["segment"]["original_text"] == segment["original_text"]
    assert (
        client.patch(
            f"/api/transcript-segments/{segment['id']}", json={"revised_text": "Conflicto", "revision": 1}
        ).status_code
        == 409
    )
    process_analysis(client, identity)
    run = client.get(f"/api/meetings/{identity}/analyses").json()[0]
    requirement = run["requirements"][0]
    assert requirement["status"] == "unclear"
    assert requirement["evidence"][0]["quote"] == "El portal debe registrar solicitudes."
    original = requirement["original"]["description"]
    assert (
        client.patch(
            f"/api/requirements/{requirement['id']}",
            json={"description": "Descripción validada por la persona responsable"},
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/api/requirements/{requirement['id']}/validate", json={"status": "validated"}
        ).status_code
        == 200
    )
    detail = client.get(f"/api/requirements/{requirement['id']}").json()
    assert detail["original"]["description"] == original
    assert len(detail["revisions"]) == 2
    artifact = client.post(f"/api/meetings/{identity}/export").json()
    assert len(artifact["files"]) == 12
    download = client.get(f"/api/exports/{artifact['id']}/download")
    with zipfile.ZipFile(io.BytesIO(download.content)) as archive:
        requirements = archive.read("02-requisitos-funcionales.md").decode()
        assert "Descripción validada" in requirements and "validated" in requirements
        assert segment["id"] in archive.read("11-matriz-trazabilidad.md").decode()
        assert archive.read("transcripcion-revisada.txt").decode() == "El portal debe registrar solicitudes."
    assert (
        client.get(
            f"/api/exports/{artifact['id']}/download", params={"file": "../../auth/credentials.json"}
        ).status_code
        == 404
    )
    other = client.post(f"/api/meetings/{identity}/export").json()
    assert other["id"] != artifact["id"]
    process_analysis(client, identity)
    runs = client.get(f"/api/meetings/{identity}/analyses").json()
    assert len(runs) == 2
    assert next(r for r in runs if r["active"])["id"] == run["id"]
    assert client.post(f"/api/analysis-runs/{runs[0]['id']}/activate").status_code == 200
    new_code = runs[0]["requirements"][0]["code"]
    assert new_code != requirement["code"]
    assert runs[0]["code_mapping"]["RF-001"] == new_code
    assert runs[0]["original_result"]["requirements"][0]["code"] == "RF-001"
    later_export = client.post(f"/api/meetings/{identity}/export").json()
    backlog = client.get(f"/api/exports/{later_export['id']}/download?file=10-backlog.md").text
    assert f"Requisitos de origen: {new_code}" in backlog
    matrix = client.get(f"/api/exports/{later_export['id']}/download?file=11-matriz-trazabilidad.md").text
    assert "| Backlog |" in matrix and "BL-001" in matrix and new_code in matrix
    assert client.delete(f"/api/projects/{meeting['project_id']}").status_code == 400
    assert client.delete(f"/api/projects/{meeting['project_id']}?confirm=true").status_code == 204
    assert client.get("/api/projects").json() == []


def test_input_changes_require_new_authorization(client, meeting):
    identity = meeting["id"]
    process_transcription(client, identity)
    old = client.get(f"/api/meetings/{identity}/analysis-input").json()
    client.patch(f"/api/projects/{meeting['project_id']}", json={"context": "Contexto actualizado"})
    assert (
        client.post(
            f"/api/meetings/{identity}/analyze", json={"input_hash": old["input_hash"], "consent": True}
        ).status_code
        == 409
    )


def test_criterion_edits_preserve_generated_result_history_and_old_exports(client, meeting):
    identity = meeting["id"]
    process_transcription(client, identity)
    process_analysis(client, identity)
    run = client.get(f"/api/meetings/{identity}/analyses").json()[0]
    criterion = run["criteria"][0]
    original = run["original_result"]
    first_export = client.post(f"/api/meetings/{identity}/export").json()
    old_document = client.get(
        f"/api/exports/{first_export['id']}/download?file=06-criterios-aceptacion.md"
    ).content
    patch = {
        "revision": criterion["revision"],
        "given": "Una solicitud nueva con los datos acordados",
        "when": "Se confirma su registro y se recarga la vista",
        "then": "La solicitud registrada sigue disponible con sus datos",
        "observations": "Propuesta solicitada; necesita validación explícita",
    }
    edited = client.patch(f"/api/criteria/{criterion['id']}", json=patch)
    assert edited.status_code == 200, edited.text
    revised = edited.json()
    assert revised["status"] == "pending_validation"
    assert revised["revision"] == 1
    assert revised["original"] == criterion["original"]
    assert revised["revisions"][0]["before"]["then"] == criterion["then"]
    assert revised["revisions"][0]["after"]["then"] == patch["then"]
    assert client.patch(f"/api/criteria/{criterion['id']}", json=patch).status_code == 409
    assert (
        client.patch(f"/api/criteria/{criterion['id']}", json={**patch, "status": "validated"}).status_code
        == 422
    )
    latest = client.get(f"/api/meetings/{identity}/analyses").json()[0]
    assert latest["original_result"] == original
    assert latest["criteria"][0]["then"] == patch["then"]
    assert latest["criteria"][0]["requirements"] == criterion["requirements"]
    assert latest["requirements"] == run["requirements"]
    artifact = client.post(f"/api/meetings/{identity}/export").json()
    document = client.get(f"/api/exports/{artifact['id']}/download?file=06-criterios-aceptacion.md").text
    assert patch["then"] in document and criterion["then"] in document
    assert "Texto original generado" in document and "Pendiente de validación" in document
    assert (
        client.get(f"/api/exports/{first_export['id']}/download?file=06-criterios-aceptacion.md").content
        == old_document
    )


def test_explicit_criterion_validation_preserves_text_and_history_and_edit_resets_status(client, meeting):
    identity = meeting["id"]
    process_transcription(client, identity)
    process_analysis(client, identity)
    run = client.get(f"/api/meetings/{identity}/analyses").json()[0]
    criterion = run["criteria"][0]
    patch = {k: criterion[k] for k in ("revision", "given", "when", "then")}
    patch["then"] = "La solicitud persiste después de recargar"
    revised = client.patch(f"/api/criteria/{criterion['id']}", json=patch).json()
    endpoint = f"/api/criteria/{criterion['id']}/validate"
    assert client.post(endpoint, json={"status": "validated"}).status_code == 422
    assert client.post(endpoint, json={"revision": 1, "status": "detected"}).status_code == 422
    assert client.post(endpoint, json={"revision": 0, "status": "validated"}).status_code == 409
    payload = {"revision": 1, "status": "validated", "observations": "Aprobación explícita de la revisión"}
    response = client.post(endpoint, json=payload)
    assert response.status_code == 200, response.text
    validated = response.json()
    assert validated["revision"] == 2 and validated["status"] == "validated"
    assert validated["original"] == criterion["original"]
    assert validated["revisions"][:1] == revised["revisions"]
    assert validated["revisions"][1]["action"] == "validation"
    for key in ("given", "when", "then"):
        assert validated[key] == revised[key]
        assert validated["revisions"][1]["before"][key] == validated["revisions"][1]["after"][key]
    assert client.post(endpoint, json=payload).status_code == 409
    after = client.get(f"/api/meetings/{identity}/analyses").json()[0]
    assert after["original_result"] == run["original_result"]
    assert after["requirements"] == run["requirements"]
    artifact = client.post(f"/api/meetings/{identity}/export").json()
    document = client.get(f"/api/exports/{artifact['id']}/download?file=06-criterios-aceptacion.md").text
    assert "Estado: Validado" in document and "Revisión: 2" in document
    assert "Historial de revisiones" in document and payload["observations"] in document
    assert (
        "Texto original generado" in document and criterion["then"] in document and patch["then"] in document
    )
    edited_again = client.patch(
        f"/api/criteria/{criterion['id']}",
        json={**patch, "revision": 2, "then": "Otra modificación posterior"},
    ).json()
    assert edited_again["status"] == "pending_validation" and edited_again["revision"] == 3
    assert edited_again["revisions"][:2] == validated["revisions"]


def test_exports_keep_analysis_input_after_later_transcript_edit(client, meeting):
    identity = meeting["id"]
    process_transcription(client, identity)
    process_analysis(client, identity)
    transcript = client.get(f"/api/meetings/{identity}/transcript").json()
    client.patch(
        "/api/transcript-segments/" + transcript["segments"][0]["id"],
        json={"revision": transcript["revision"], "revised_text": "Cambio posterior"},
    )
    run = client.get(f"/api/meetings/{identity}/analyses").json()[0]
    assert run["input_snapshot"]["segments"][0]["text"] != "Cambio posterior"
    artifact = client.post(f"/api/meetings/{identity}/export").json()
    assert (
        "Cambio posterior"
        not in client.get(f"/api/exports/{artifact['id']}/download?file=transcripcion-revisada.txt").text
    )


def test_criterion_noop_active_revision_and_rejection_reason(client, meeting):
    process_transcription(client, meeting["id"])
    process_analysis(client, meeting["id"])
    run = client.get(f"/api/meetings/{meeting['id']}/analyses").json()[0]
    c = run["criteria"][0]
    endpoint = f"/api/criteria/{c['id']}"
    assert client.get(endpoint).json()["active"]
    approved = client.post(endpoint + "/validate", json={"revision": 0, "status": "validated"}).json()
    same = client.patch(endpoint, json={"revision": 1, **{k: c[k] for k in ("given", "when", "then")}}).json()
    assert same == approved
    assert client.post(endpoint + "/validate", json={"revision": 1, "status": "rejected"}).status_code == 422
    rejected = client.post(
        endpoint + "/validate",
        json={"revision": 1, "status": "rejected", "observations": "No representa el alcance acordado"},
    ).json()
    assert rejected["status"] == "rejected" and rejected["revisions"][-1]["actor"]["kind"] == "local"
    changed = client.patch(
        endpoint,
        json={
            "revision": 2,
            **{k: c[k] for k in ("given", "when", "then")},
            "then": "Resultado verificable revisado",
        },
    ).json()
    assert changed["status"] == "pending_validation"
    process_analysis(client, meeting["id"])
    newer = client.get(f"/api/meetings/{meeting['id']}/analyses").json()[0]
    client.post(f"/api/analysis-runs/{newer['id']}/activate")
    assert client.post(endpoint + "/validate", json={"revision": 3, "status": "validated"}).status_code == 409
