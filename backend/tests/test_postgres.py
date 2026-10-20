import pytest
from sqlalchemy import text, select
from app.db import engine, SessionLocal
from app.context import organization
from app.models import Project

pytestmark = pytest.mark.skipif(engine.dialect.name != "postgresql", reason="PostgreSQL opt-in compose suite")


def test_tenant_context_does_not_leak_between_pooled_sessions():
    first = organization.set("org-a")
    try:
        with SessionLocal.begin() as s:
            s.add(Project(name="A"))
            s.flush()
        with SessionLocal() as s:
            assert s.scalar(text("SELECT current_setting('mra.organization_id')")) == "org-a"
    finally:
        organization.reset(first)
    second = organization.set("org-b")
    try:
        with SessionLocal() as s:
            assert s.scalar(text("SELECT current_setting('mra.organization_id')")) == "org-b"
            assert not s.scalars(select(Project)).all()
    finally:
        organization.reset(second)


def test_database_rejects_cross_organization_foreign_key():
    with engine.begin() as c:
        c.execute(
            text(
                "INSERT INTO projects(id,name,description,context,glossary,created_at,updated_at,organization_id) VALUES('foreign-project','A','','','{}',now(),now(),'org-a')"
            )
        )
    with pytest.raises(Exception):
        with engine.begin() as c:
            c.execute(
                text(
                    "INSERT INTO meetings(id,project_id,title,date,status,profile,transcript_revision,created_at,updated_at,organization_id) VALUES('foreign-meeting','foreign-project','B',current_date,'registered','balanced',0,now(),now(),'org-b')"
                )
            )


def test_postgres_worker_lock_excludes_second_worker():
    from app.locking import worker_lock

    with worker_lock():
        with pytest.raises(SystemExit):
            with worker_lock():
                pass


def test_portable_backup_and_sqlite_import_preserve_reviews(client, meeting, tmp_path):
    from test_flow import process_transcription, process_analysis
    from app.maintenance import backup
    from app.migrate_database import migrate
    import tarfile
    import json

    process_transcription(client, meeting["id"])
    process_analysis(client, meeting["id"])
    run = client.get(f"/api/meetings/{meeting['id']}/analyses").json()[0]
    c = run["criteria"][0]
    assert (
        client.post(
            f"/api/criteria/{c['id']}/validate", json={"revision": 0, "status": "validated"}
        ).status_code
        == 200
    )
    archive_path = tmp_path / "backup.tar.gz"
    backup(archive_path)
    with tarfile.open(archive_path) as archive:
        manifest = json.load(archive.extractfile("manifest.json"))
        assert not manifest["credentials_included"]
        snapshot = tmp_path / "snapshot.sqlite3"
        snapshot.write_bytes(archive.extractfile("db/app.sqlite3").read())
    import sqlite3

    with sqlite3.connect(snapshot) as source:
        assert (
            source.execute("SELECT status FROM acceptance_criteria WHERE id=?", (c["id"],)).fetchone()[0]
            == "validated"
        )
    before = snapshot.read_bytes()
    with engine.begin() as target:
        from app.db import Base

        for table in reversed(Base.metadata.sorted_tables):
            target.execute(table.delete())
    report = migrate(snapshot)
    assert report["source_unchanged"] and snapshot.read_bytes() == before
    restored = client.get(f"/api/meetings/{meeting['id']}/analyses").json()[0]
    assert restored["original_result"] == run["original_result"]
    assert restored["criteria"][0]["status"] == "validated"
    assert restored["criteria"][0]["revisions"][-1]["actor"]["kind"] == "local"
    with pytest.raises(ValueError, match="vacío"):
        migrate(snapshot)


def test_import_alpha_schema_preserves_originals_and_approval(client, meeting, tmp_path):
    from test_flow import process_transcription, process_analysis
    from app.db import make_engine, Base
    from app.migrate_database import migrate
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import MetaData, inspect
    from pathlib import Path

    process_transcription(client, meeting["id"])
    process_analysis(client, meeting["id"])
    run = client.get(f"/api/meetings/{meeting['id']}/analyses").json()[0]
    cid = run["criteria"][0]["id"]
    client.post(f"/api/criteria/{cid}/validate", json={"revision": 0, "status": "validated"})
    source = tmp_path / "alpha.sqlite3"
    old = make_engine("sqlite:///" + str(source))
    cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    cfg.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "migrations"))
    with old.connect() as c:
        cfg.attributes["connection"] = c
        command.upgrade(cfg, "0002")
    old_metadata = MetaData()
    old_metadata.reflect(old)
    with engine.begin() as current, old.begin() as target:
        for table in Base.metadata.sorted_tables:
            destination = old_metadata.tables[table.name]
            data = [
                {name: row[name] for name in destination.c.keys()}
                for row in current.execute(table.select()).mappings()
            ]
            if data:
                target.execute(destination.insert(), data)
    with old.connect() as c:
        assert "organization_id" not in [column["name"] for column in inspect(c).get_columns("analysis_runs")]
    old.dispose()
    with engine.begin() as c:
        for table in reversed(Base.metadata.sorted_tables):
            c.execute(table.delete())
    migrate(source)
    restored = client.get(f"/api/meetings/{meeting['id']}/analyses").json()[0]
    assert restored["original_result"] == run["original_result"]
    assert restored["criteria"][0]["status"] == "validated"
    assert restored["criteria"][0]["original"] == run["criteria"][0]["original"]
