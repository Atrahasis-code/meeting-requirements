"""Renumber references without retaining block-local dependency identifiers."""

import copy
import threading

from app.analysis import merge_results, validate_evidence
from app.providers import MockAnalysisProvider
from app.schemas import AnalysisResult


def block(codes=("RF-101", "RN-201", "RF-701"), suffix=""):
    result = (
        MockAnalysisProvider()
        .analyze(
            {"segments": [{"id": "selected-segment", "text": "Registrar solicitudes."}]}, threading.Event()
        )
        .model_dump()
    )
    template = result["requirements"][0]
    result["requirements"] = []
    for index, code in enumerate(codes):
        req = copy.deepcopy(template)
        req.update(
            code=code,
            kind="nonfunctional" if code.startswith("RN") else "functional",
            description=f"Necesidad sintética {index}{suffix}",
            dependencies=[codes[1]] if index != 1 else [],
        )
        result["requirements"].append(req)
    result["stories"][0]["requirements"] = list(codes)
    result["criteria"][0]["requirements"] = list(codes)
    result["backlog"][0]["requirements"] = list(codes)
    return AnalysisResult.model_validate(result)


def test_merge_translates_forward_and_mixed_requirement_dependencies_without_mutation():
    source = block()
    original = source.model_dump()
    merged = merge_results([source])
    assert [r.code for r in merged.requirements] == ["RF-001", "RN-002", "RF-003"]
    assert [r.dependencies for r in merged.requirements] == [["RN-002"], [], ["RN-002"]]
    assert merged.stories[0].requirements == ["RF-001", "RN-002", "RF-003"]
    assert merged.criteria[0].requirements == merged.stories[0].requirements
    assert merged.backlog[0].requirements == merged.stories[0].requirements
    validate_evidence(merged, {"segments": [{"id": "selected-segment", "text": "Registrar solicitudes."}]})
    assert source.model_dump() == original


def test_merge_repeated_local_codes_and_deduplication_keep_only_canonical_dependencies():
    first = block()
    second = block(suffix=" en otro bloque")
    # Repeated concept across blocks must merge without disturbing prior canonical references.
    second.requirements[1].description = first.requirements[1].description
    originals = [first.model_dump(), second.model_dump()]
    merged = merge_results([first, second])
    assert len(merged.requirements) == 5
    assert [r.dependencies for r in merged.requirements] == [
        ["RN-002"],
        [],
        ["RN-002"],
        ["RN-002"],
        ["RN-002"],
    ]
    assert set(merged.stories[1].requirements) == {"RF-004", "RN-002", "RF-005"}
    assert [first.model_dump(), second.model_dump()] == originals
    assert merge_results([first, second]).model_dump() == merged.model_dump()


def test_consolidation_failure_preserves_checkpoint_and_exposes_only_safe_diagnostics(
    client, meeting, monkeypatch
):
    import pytest
    from sqlalchemy import select
    from app import models as m
    from app.db import SessionLocal
    from app.processing import analyze
    from app.providers import ProviderBlocked
    from app.worker import claim
    from test_flow import process_transcription

    mid = meeting["id"]
    process_transcription(client, mid)
    transcript = client.get(f"/api/meetings/{mid}/transcript").json()
    client.patch(
        "/api/transcript-segments/" + transcript["segments"][0]["id"],
        json={"revision": transcript["revision"], "reviewed": True},
    )
    entry = client.get(f"/api/meetings/{mid}/analysis-input").json()
    queued = client.post(
        f"/api/meetings/{mid}/analyze", json={"input_hash": entry["input_hash"], "consent": True}
    ).json()
    assert claim() == queued["id"]
    saved = MockAnalysisProvider().analyze(entry["snapshot"], threading.Event()).model_dump()
    with SessionLocal.begin() as s:
        s.get(m.ProcessingJob, queued["id"]).checkpoint = {"blocks": [saved]}

    def invalid_merge(results):
        invalid = copy.deepcopy(saved)
        invalid["requirements"][0]["dependencies"] = ["private-value-must-not-be-logged"]
        return AnalysisResult.model_validate(invalid)

    class NoInference:
        def analyze(self, *args):
            pytest.fail("A compatible checkpoint must not cause another inference")

    monkeypatch.setattr("app.processing.merge_results", invalid_merge)
    monkeypatch.setattr("app.processing.provider", lambda _: NoInference())
    with pytest.raises(ProviderBlocked) as caught:
        analyze(queued["id"], threading.Event())
    assert caught.value.code == "invalid_analysis_merge"
    assert "private-value" not in str(caught.value)
    assert "un requisito depende de otro requisito inexistente" in str(caught.value)
    with SessionLocal() as s:
        assert s.get(m.ProcessingJob, queued["id"]).checkpoint == {"blocks": [saved]}
        assert not s.scalar(select(m.AnalysisRun).where(m.AnalysisRun.meeting_id == mid))
