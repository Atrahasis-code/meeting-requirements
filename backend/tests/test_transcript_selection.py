"""Human selection is enforced before providers, independently of result approvals."""

import io
import json
import threading
import zipfile
from datetime import date

import pytest
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError

from app import models as m
from app.analysis import SELECTION_POLICY
from app.db import SessionLocal
from app.processing import analyze
from app.providers import MockAnalysisProvider, ProviderBlocked
from app.worker import claim
from test_flow import process_transcription


@pytest.fixture
def blocks(client, meeting):
    process_transcription(client, meeting["id"])
    with SessionLocal.begin() as s:
        s.add_all(
            [
                m.TranscriptSegment(
                    meeting_id=meeting["id"],
                    start=30,
                    end=40,
                    original_text="Ruido descartado sobre el almuerzo.",
                ),
                m.TranscriptSegment(
                    meeting_id=meeting["id"],
                    start=50,
                    end=60,
                    original_text="Conversación pendiente sin revisar.",
                ),
            ]
        )
    return client.get(f"/api/meetings/{meeting['id']}/transcript").json()


def change(client, mid, sid, **values):
    current = client.get(f"/api/meetings/{mid}/transcript").json()
    return client.patch(f"/api/transcript-segments/{sid}", json={"revision": current["revision"], **values})


def queue(client, mid, entry=None):
    entry = entry or client.get(f"/api/meetings/{mid}/analysis-input").json()
    return client.post(
        f"/api/meetings/{mid}/analyze", json={"input_hash": entry["input_hash"], "consent": True}
    )


def test_pending_empty_selection_and_explicit_exclusive_transitions(client, meeting, blocks):
    mid = meeting["id"]
    sid = blocks["segments"][0]["id"]
    entry = client.get(f"/api/meetings/{mid}/analysis-input").json()
    assert entry["snapshot"]["segments"] == [] and entry["snapshot"]["selection_summary"]["pending"] == 3
    assert queue(client, mid).status_code == 422
    assert change(client, mid, sid, reviewed=True, discarded=True).status_code == 422
    assert change(client, mid, sid, reviewed=None).status_code == 422
    reviewed = change(client, mid, sid, reviewed=True).json()["segment"]
    assert reviewed["reviewed"] and not reviewed["discarded"]
    discarded = change(client, mid, sid, discarded=True).json()["segment"]
    assert discarded["discarded"] and not discarded["reviewed"]
    assert discarded["original_text"] == reviewed["original_text"]
    restored = change(client, mid, sid, reviewed=True).json()["segment"]
    assert restored["reviewed"] and not restored["discarded"]
    pending = change(client, mid, sid, reviewed=False).json()["segment"]
    assert not pending["reviewed"] and not pending["discarded"]


def test_text_edits_reset_decision_noops_do_not_and_revision_conflicts(client, meeting, blocks):
    mid = meeting["id"]
    sid = blocks["segments"][0]["id"]
    first = change(client, mid, sid, reviewed=True).json()
    same = change(client, mid, sid, revised_text=first["segment"]["original_text"], reviewed=True).json()
    assert same["revision"] == first["revision"]
    assert {k: v for k, v in same["segment"].items() if k not in {"created_at", "updated_at"}} == {
        k: v for k, v in first["segment"].items() if k not in {"created_at", "updated_at"}
    }
    stale = client.patch(
        f"/api/transcript-segments/{sid}", json={"revision": blocks["revision"], "discarded": True}
    )
    assert stale.status_code == 409
    edited = change(client, mid, sid, revised_text="Texto corregido.").json()["segment"]
    assert not edited["reviewed"] and not edited["discarded"]
    change(client, mid, sid, discarded=True)
    edited = change(client, mid, sid, revised_text="Otra corrección.").json()["segment"]
    assert not edited["reviewed"] and not edited["discarded"]
    confirmed = change(
        client, mid, sid, revised_text="Corrección confirmada.", reviewed=True, doubtful=True
    ).json()["segment"]
    assert confirmed["reviewed"] and confirmed["doubtful"]
    change(client, mid, sid, revised_text=" ", reviewed=True)
    assert queue(client, mid).status_code == 422


def test_only_reviewed_text_reaches_provider_and_new_exports_keep_history(
    client, meeting, blocks, monkeypatch
):
    mid = meeting["id"]
    sid, noise, pending = [s["id"] for s in blocks["segments"]]
    change(client, mid, noise, discarded=True)
    change(client, mid, sid, reviewed=True, doubtful=True)
    entry = client.get(f"/api/meetings/{mid}/analysis-input").json()
    data = entry["snapshot"]
    assert data["selection_policy"] == SELECTION_POLICY
    assert data["selection_summary"] == dict(total=3, reviewed=1, discarded=1, pending=1, included=1)
    assert [s["id"] for s in data["segments"]] == [sid] and data["segments"][0]["doubtful"]
    assert "almuerzo" not in json.dumps(data) and "Conversación pendiente" not in json.dumps(data)
    received = []

    class CapturingMock(MockAnalysisProvider):
        def analyze(self, data, cancelled):
            received.append(data)
            return super().analyze(data, cancelled)

    monkeypatch.setattr("app.processing.provider", lambda _: CapturingMock())
    queued = queue(client, mid, entry).json()
    assert claim() == queued["id"]
    # A job retains exactly the input already authorized; changes apply to future jobs.
    change(client, mid, sid, discarded=True)
    analyze(queued["id"], threading.Event())
    assert received[0]["segments"] == data["segments"]
    run = client.get(f"/api/meetings/{mid}/analyses").json()[0]
    assert all(e["segment_id"] == sid for r in run["requirements"] for e in r["evidence"])
    exported = client.post(f"/api/meetings/{mid}/export").json()
    first_zip = client.get(f"/api/exports/{exported['id']}/download").content
    with zipfile.ZipFile(io.BytesIO(first_zip)) as z:
        assert z.read("transcripcion-revisada.txt").decode() == data["segments"][0]["text"]
    change(client, mid, pending, reviewed=True)
    queued = queue(client, mid).json()
    assert claim() == queued["id"]
    analyze(queued["id"], threading.Event())
    assert received[-1]["segments"][0]["id"] == pending
    assert client.get(f"/api/exports/{exported['id']}/download").content == first_zip
    old = next(r for r in client.get(f"/api/meetings/{mid}/analyses").json() if r["id"] == run["id"])
    assert old["input_snapshot"] == data and old["original_result"] == run["original_result"]
    full = client.get(f"/api/meetings/{mid}/transcript/download?format=json").json()
    assert len(full) == 3 and next(s for s in full if s["id"] == noise)["discarded"]


def test_selection_changes_invalidate_consent_and_checkpoints(client, meeting, blocks):
    mid = meeting["id"]
    sid = blocks["segments"][0]["id"]
    change(client, mid, sid, reviewed=True)
    entry = client.get(f"/api/meetings/{mid}/analysis-input").json()
    change(client, mid, blocks["segments"][1]["id"], discarded=True)
    assert queue(client, mid, entry).status_code == 409
    queued = queue(client, mid).json()
    client.post(f"/api/jobs/{queued['id']}/cancel")
    with SessionLocal.begin() as s:
        s.get(m.ProcessingJob, queued["id"]).checkpoint = {"blocks": [{"old": "must not be reused"}]}
    change(client, mid, sid, revised_text="Entrada nueva.", reviewed=True)
    data = client.get(f"/api/meetings/{mid}/analysis-input").json()
    retried = client.post(
        f"/api/jobs/{queued['id']}/retry", json={"input_hash": data["input_hash"], "consent": True}
    )
    assert retried.status_code == 202 and retried.json()["checkpoint"] == {}


def test_legacy_jobs_block_before_any_provider_or_runtime_access(client, meeting, blocks, monkeypatch):
    mid = meeting["id"]
    change(client, mid, blocks["segments"][0]["id"], reviewed=True)
    queued = queue(client, mid).json()
    with SessionLocal.begin() as s:
        job = s.get(m.ProcessingJob, queued["id"])
        old = dict(job.params["snapshot"])
        old.pop("selection_policy")
        job.params = {**job.params, "snapshot": old}
    monkeypatch.setattr("app.processing.provider", lambda _: pytest.fail("Provider must not be reached"))
    assert claim() == queued["id"]
    with pytest.raises(ProviderBlocked) as caught:
        analyze(queued["id"], threading.Event())
    assert caught.value.code == "review_required"


def test_database_enforces_mutual_exclusion(client, meeting, blocks):
    with pytest.raises(IntegrityError), SessionLocal.begin() as s:
        s.execute(
            update(m.TranscriptSegment)
            .where(m.TranscriptSegment.id == blocks["segments"][0]["id"])
            .values(reviewed=True, discarded=True)
        )


def test_selection_migration_preserves_legacy_rows_and_tenant_triggers(tmp_path):
    from alembic import command
    from alembic.config import Config
    from app.db import make_engine
    from sqlalchemy import MetaData
    from pathlib import Path

    engine = make_engine("sqlite:///" + str(tmp_path / "legacy.sqlite3"))
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "migrations"))
    with engine.begin() as c:
        config.attributes["connection"] = c
        command.upgrade(config, "0003")
        tables = MetaData()
        tables.reflect(c)
        record = dict(
            created_at=__import__("datetime").datetime.now(),
            updated_at=__import__("datetime").datetime.now(),
            organization_id="local",
        )
        c.execute(
            tables.tables["projects"]
            .insert()
            .values(**record, id="p", name="Legacy", description="", context="", glossary={})
        )
        c.execute(
            tables.tables["meetings"]
            .insert()
            .values(
                **record,
                id="m",
                project_id="p",
                title="Legacy",
                date=date.today(),
                profile="balanced",
                language="es",
                status="transcribed",
                transcript_revision=2,
            )
        )
        for i, reviewed in enumerate((True, False)):
            c.execute(
                tables.tables["transcript_segments"]
                .insert()
                .values(
                    **record,
                    id=str(i),
                    meeting_id="m",
                    start=i * 10,
                    end=i * 10 + 5,
                    original_text="Original",
                    revised_text="Revisión",
                    reviewed=reviewed,
                    doubtful=False,
                    detection={},
                    chunk_index=0,
                )
            )
        before = c.exec_driver_sql("SELECT * FROM transcript_segments ORDER BY id").mappings().all()
        triggers = c.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='trigger'").fetchall()
        command.upgrade(config, "head")
        after = c.exec_driver_sql("SELECT * FROM transcript_segments ORDER BY id").mappings().all()
        assert [dict(r) for r in before] == [{k: v for k, v in r.items() if k != "discarded"} for r in after]
        assert all(not r["discarded"] for r in after)
        assert c.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='trigger'").fetchall() == triggers
        assert not c.exec_driver_sql("PRAGMA foreign_key_check").fetchall()
    engine.dispose()
