from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from app.analysis import validate_evidence
from app.schemas import AnalysisResult
from app.media import safe_path
from app.processing import reconcile_words
from app.providers import MockAnalysisProvider
import threading


def test_validation_rejects_corrupt_spoofed_and_unsafe_paths(client, meeting):
    fresh = client.post(
        "/api/meetings", json={"project_id": meeting["project_id"], "title": "Inválida", "date": "2026-10-19"}
    ).json()
    assert (
        client.post(
            f"/api/meetings/{fresh['id']}/upload", files={"file": ("audio.mp4", b"not media", "video/mp4")}
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"/api/meetings/{fresh['id']}/upload", files={"file": ("script.sh", b"echo", "audio/wav")}
        ).status_code
        == 415
    )
    with pytest.raises(HTTPException):
        safe_path("media", "../auth/credentials.json")
    assert client.post("/api/projects", json={"name": "   "}).status_code == 422
    assert (
        client.post(
            "/api/projects", json={"name": "Portal"}, headers={"origin": "https://attacker.invalid"}
        ).status_code
        == 403
    )
    assert client.get("/api/health", headers={"host": "attacker.invalid"}).status_code == 400


def test_chunk_boundary_words_are_assigned_once():
    left = [
        SimpleNamespace(start=299.1, end=299.8, word="primera"),
        SimpleNamespace(start=299.9, end=300.5, word="segunda"),
    ]
    right = [
        SimpleNamespace(start=1.1, end=1.8, word="primera"),
        SimpleNamespace(start=1.9, end=2.5, word="segunda"),
    ]
    words = reconcile_words(left, 0, 0, 300) + reconcile_words(right, 298, 300, 600)
    assert [w["word"] for w in words] == ["primera", "segunda"]
    assert words[1]["start"] == pytest.approx(299.9)


def test_provider_evidence_and_manual_approval_are_validated():
    data = {"segments": [{"id": "seg1", "text": "Registrar solicitudes"}]}
    result = MockAnalysisProvider().analyze(data, threading.Event())
    assert validate_evidence(result, data)
    raw = result.model_dump()
    raw["requirements"][0]["evidence"][0]["quote"] = "Función inventada"
    with pytest.raises(ValueError):
        validate_evidence(AnalysisResult.model_validate(raw), data)
    raw = result.model_dump()
    raw["requirements"][0]["status"] = "validated"
    with pytest.raises(ValueError):
        AnalysisResult.model_validate(raw)
    raw = result.model_dump()
    raw["stories"][0]["requirements"] = ["RF-999"]
    with pytest.raises(ValueError):
        AnalysisResult.model_validate(raw)


def test_download_subtitle_formats(client, meeting):
    from test_flow import process_transcription

    process_transcription(client, meeting["id"])
    for format in ("txt", "json", "srt", "vtt"):
        result = client.get(f"/api/meetings/{meeting['id']}/transcript/download?format={format}")
        assert result.status_code == 200
        assert "attachment" in result.headers["content-disposition"]
    assert client.get(f"/api/meetings/{meeting['id']}/transcript/download?format=exe").status_code == 422


def test_real_mp4_validation_and_range_streaming(client, meeting, tmp_path):
    import subprocess

    path = tmp_path / "synthetic.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=64x64:r=1:d=1",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=16000:cl=mono",
            "-t",
            "1",
            "-c:v",
            "mpeg4",
            "-c:a",
            "aac",
            "-movflags",
            "+faststart",
            str(path),
        ],
        check=True,
        timeout=30,
    )
    new = client.post(
        "/api/meetings",
        json={"project_id": meeting["project_id"], "title": "Vídeo sintético", "date": "2026-10-19"},
    ).json()
    response = client.post(
        f"/api/meetings/{new['id']}/upload", files={"file": ("test.mp4", path.read_bytes(), "video/mp4")}
    )
    assert response.status_code == 201, response.text
    stream = client.get(f"/api/meetings/{new['id']}/media", headers={"range": "bytes=0-15"})
    assert stream.status_code == 206
    assert len(stream.content) == 16


def test_pinned_codex_runtime_really_disables_tools(tmp_path, monkeypatch):
    from openai_codex import CodexConfig, ApprovalMode
    from app.providers import restricted_overrides, verify_runtime_security

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    verify_runtime_security(CodexConfig(cwd=str(tmp_path), config_overrides=restricted_overrides()))
    assert ApprovalMode.deny_all.value == "deny_all"


def test_analysis_output_contract_and_backlog_merging():
    from app.providers import analysis_output_schema
    from app.analysis import merge_results

    schema = analysis_output_schema()
    for node in [schema, *schema["$defs"].values()]:
        if node.get("type") == "object":
            assert set(node["required"]) == set(node["properties"])
            assert node["additionalProperties"] is False
    data = {"segments": [{"id": "segment", "text": "Registrar solicitudes"}]}
    result = MockAnalysisProvider().analyze(data, threading.Event())
    raw = result.model_dump()
    second = {**raw["backlog"][0], "code": "BL-002", "dependencies": ["BL-001"]}
    raw["backlog"].append(second)
    result = AnalysisResult.model_validate(raw)
    merged = merge_results([result, result])
    assert merged.backlog[3].dependencies == ["BL-003"]
    raw["backlog"][0]["status"] = "validated"
    with pytest.raises(ValueError):
        AnalysisResult.model_validate(raw)


def test_provider_diagnostics_never_echo_request_or_credentials():
    from app.providers import safe_failure_diagnostic

    error = RuntimeError("HTTP 400 invalid_json_schema: private meeting text token=secret-value")
    diagnostic = safe_failure_diagnostic(error)
    assert "http_400" in diagnostic
    assert "invalid_json_schema" in diagnostic
    assert "private" not in diagnostic
    assert "secret-value" not in diagnostic


def test_codex_completed_enum_accepts_valid_output_and_rejects_other_states():
    from openai_codex.generated.v2_all import TurnStatus
    from app.providers import parse_codex_result

    data = {"segments": [{"id": "seg1", "text": "Registrar solicitudes"}]}
    expected = MockAnalysisProvider().analyze(data, threading.Event())
    result = SimpleNamespace(
        status=TurnStatus.completed, final_response=expected.model_dump_json(), error=None
    )
    assert parse_codex_result(result) == expected
    for status in (TurnStatus.failed, TurnStatus.interrupted):
        result.status = status
        with pytest.raises(RuntimeError):
            parse_codex_result(result)
    result.status = TurnStatus.completed
    result.final_response = None
    with pytest.raises(RuntimeError):
        parse_codex_result(result)


def test_file_protocols_and_disabled_providers_are_explicit(client):
    providers = client.get("/api/providers").json()
    assert {p["id"] for p in providers if p["available"]} == {"chatgpt", "mock"}
    assert all(not p["available"] for p in providers if p["id"] in {"claude", "grok"})


def test_secret_initializer_preserves_private_modes_and_rejects_implicit_rotation(tmp_path):
    import os
    from app.prepare_database_secret import write_private

    root = tmp_path / "credentials"
    write_private(root, "password", b"synthetic-test-password\n", os.getuid())
    assert root.stat().st_mode & 0o777 == 0o700
    assert (root / "password").stat().st_mode & 0o777 == 0o600
    write_private(root, "password", b"synthetic-test-password\n", os.getuid())
    with pytest.raises(ValueError, match="rotation"):
        write_private(root, "password", b"changed\n", os.getuid())


@pytest.mark.parametrize(
    ("failure", "expected"),
    [
        ("json", "JSON válido"),
        ("missing", "campos obligatorios"),
        ("extra", "campos que no admite"),
        ("requirement_reference", "requisito inexistente"),
        ("story_reference", "historia inexistente"),
        ("backlog_dependency", "tarea inexistente"),
        ("duplicate", "requisitos duplicados"),
    ],
)
def test_invalid_analysis_has_actionable_safe_diagnostic(failure, expected):
    import json
    from app.providers import parse_codex_result, ProviderBlocked
    from openai_codex.generated.v2_all import TurnStatus

    raw = (
        MockAnalysisProvider()
        .analyze({"segments": [{"id": "segment", "text": "Requisito sintético"}]}, threading.Event())
        .model_dump()
    )
    if failure == "missing":
        del raw["requirements"][0]["title"]
    elif failure == "extra":
        raw["secret-field-name"] = "private-token-not-for-output"
    elif failure == "requirement_reference":
        raw["criteria"][0]["requirements"] = ["private-token-not-for-output"]
    elif failure == "story_reference":
        raw["criteria"][0]["story_code"] = "private-token-not-for-output"
    elif failure == "backlog_dependency":
        raw["backlog"][0]["dependencies"] = ["private-token-not-for-output"]
    elif failure == "duplicate":
        raw["requirements"].append(raw["requirements"][0])
    response = "private-token-not-for-output" if failure == "json" else json.dumps(raw)
    result = SimpleNamespace(status=TurnStatus.completed, final_response=response, error=None)
    with pytest.raises(ProviderBlocked) as caught:
        parse_codex_result(result)
    assert caught.value.code == "invalid_analysis_result"
    assert expected in caught.value.message
    assert "resultados anteriores" in caught.value.message
    assert "private-token" not in caught.value.message
    assert "secret-field-name" not in caught.value.message


@pytest.mark.parametrize("runtime_failure", [False, True, "json"])
def test_codex_validation_does_not_retry_or_claim_auth_failure(monkeypatch, runtime_failure):
    import os
    import openai_codex
    from pydantic import ValidationError
    from openai_codex.generated.v2_all import TurnStatus
    from app import providers

    monkeypatch.setattr(os, "environ", dict(os.environ))
    monkeypatch.setattr(providers.auth, "token", lambda **_: "synthetic-oauth-token")
    monkeypatch.setattr(providers, "verify_runtime_security", lambda _: None)
    calls = []

    class FakeCodex:
        def __init__(self, _):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def thread_start(self, **_):
            return self

        def run(self, *_, **options):
            calls.append(options)
            if runtime_failure == "json":
                raise ValueError("private-token-not-for-output")
            if runtime_failure:
                raise ValidationError.from_exception_data(
                    "SDK",
                    [
                        {
                            "type": "missing",
                            "loc": ("secret-field-name",),
                            "input": {"token": "private-token-not-for-output"},
                        }
                    ],
                )
            return SimpleNamespace(status=TurnStatus.completed, final_response="invalid-json", error=None)

    monkeypatch.setattr(openai_codex, "Codex", FakeCodex)
    with pytest.raises(providers.ProviderBlocked) as caught:
        providers.CodexAnalysisProvider().analyze(
            {
                "model": "synthetic-model",
                "account_id": "fixture-account",
                "segments": [{"id": "authorized-segment", "text": "Texto sintético"}],
            },
            threading.Event(),
        )
    assert len(calls) == 1
    assert caught.value.code == (
        "invalid_provider_response" if runtime_failure else "invalid_analysis_result"
    )
    assert "autenticación" not in caught.value.message
    assert "private-token" not in caught.value.message and "secret-field-name" not in caught.value.message
    assert calls[0]["output_schema"]["$defs"]["Evidence"]["properties"]["segment_id"]["enum"] == [
        "authorized-segment"
    ]


@pytest.mark.parametrize("count", [500, 1100])
def test_large_input_does_not_generate_an_unsupported_enum_schema(count):
    from uuid import UUID
    from app.providers import analysis_output_schema

    data = {"segments": [{"id": str(UUID(int=i))} for i in range(count)]}
    schema = analysis_output_schema(data)
    assert "enum" not in schema["$defs"]["Evidence"]["properties"]["segment_id"]


@pytest.mark.parametrize("hostname", ["127.0.0.1", "localhost"])
def test_loopback_browser_can_write_with_credentialed_cors(client, hostname):
    origin = f"http://{hostname}:8080"
    headers = {"origin": origin, "host": f"{hostname}:8080", "sec-fetch-site": "same-origin"}
    preflight = client.options(
        "/api/projects",
        headers={
            **headers,
            "access-control-request-method": "POST",
            "access-control-request-headers": "content-type",
        },
    )
    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == origin
    assert preflight.headers["access-control-allow-credentials"] == "true"
    response = client.post("/api/projects", json={"name": "Loopback fixture"}, headers=headers)
    assert response.status_code == 201
    assert response.headers["access-control-allow-origin"] == origin
    identity = response.json()["id"]
    assert (
        client.patch(
            f"/api/projects/{identity}", json={"name": "Edited fixture"}, headers=headers
        ).status_code
        == 200
    )
    assert client.delete(f"/api/projects/{identity}?confirm=true", headers=headers).status_code == 204


@pytest.mark.parametrize(
    "origin",
    [
        "https://attacker.invalid",
        "http://localhost:8081",
        "https://localhost:8080",
        "http://localhost.attacker.invalid:8080",
        "http://127.0.0.2:8080",
        "null",
    ],
)
def test_loopback_alias_does_not_allow_external_origins_or_other_ports(client, origin):
    response = client.post("/api/projects", json={"name": "Forbidden fixture"}, headers={"origin": origin})
    assert response.status_code == 403
    preflight = client.options(
        "/api/projects", headers={"origin": origin, "access-control-request-method": "POST"}
    )
    assert preflight.status_code == 400
    assert "access-control-allow-origin" not in preflight.headers


def test_loopback_alias_keeps_cross_site_protection(client):
    assert (
        client.post(
            "/api/projects",
            json={"name": "Forbidden fixture"},
            headers={
                "origin": "http://localhost:8080",
                "sec-fetch-site": "cross-site",
            },
        ).status_code
        == 403
    )


def test_configured_port_and_hosted_origins_remain_explicit():
    from app.config import Settings

    assert Settings(public_url="http://127.0.0.1:18080").browser_origins == [
        "http://127.0.0.1:18080",
        "http://localhost:18080",
    ]
    assert Settings(public_url="http://localhost:18080/").browser_origins == [
        "http://localhost:18080",
        "http://127.0.0.1:18080",
    ]
    assert Settings(public_url="https://preview.example.invalid").browser_origins == [
        "https://preview.example.invalid",
    ]
