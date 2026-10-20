import io
import json
import tarfile
import pytest
from app.config import settings
from app.maintenance import backup, restore


def test_backup_restore_validates_data_and_excludes_credentials(client, meeting, tmp_path, monkeypatch):
    from test_flow import process_transcription, process_analysis

    process_transcription(client, meeting["id"])
    process_analysis(client, meeting["id"])
    client.post(f"/api/meetings/{meeting['id']}/export")
    (settings.directory("auth") / "secret").write_text("not-in-backup")
    target = tmp_path / "backup.tar.gz"
    backup(target)
    with tarfile.open(target) as archive:
        assert not any(name.startswith("auth/") for name in archive.getnames())
        assert "db/app.sqlite3" in archive.getnames()
        manifest = json.load(archive.extractfile("manifest.json"))
        assert manifest["credentials_included"] is False
    restored = tmp_path / "restored"
    for area in ("db", "media", "transcripts", "exports", "models", "auth"):
        (restored / area).mkdir(parents=True)
    (restored / "media/.incoming").mkdir()
    monkeypatch.setattr(settings, "data_root", restored)
    restore(target)
    import sqlite3

    with sqlite3.connect(restored / "db/app.sqlite3") as database:
        assert database.execute("SELECT count(*) FROM requirements").fetchone()[0] == 1
    with pytest.raises(SystemExit, match="nuevos"):
        restore(target)


def test_restore_rejects_manifest_traversal(tmp_path, monkeypatch):
    root = tmp_path / "volumes"
    for area in ("db", "media", "transcripts", "exports", "models", "auth"):
        (root / area).mkdir(parents=True)
    monkeypatch.setattr(settings, "data_root", root)
    source = tmp_path / "invalid.tar.gz"
    with tarfile.open(source, "w:gz") as archive:
        data = json.dumps(
            {"version": 1, "credentials_included": False, "files": {"../outside": "fake"}}
        ).encode()
        entry = tarfile.TarInfo("manifest.json")
        entry.size = len(data)
        archive.addfile(entry, io.BytesIO(data))
    with pytest.raises(SystemExit, match="Ruta"):
        restore(source)


def test_restore_rejects_reusing_an_oauth_identity(tmp_path, monkeypatch):
    root = tmp_path / "volumes"
    for area in ("db", "media", "transcripts", "exports", "models", "auth"):
        (root / area).mkdir(parents=True)
    (root / "auth/credentials.json").write_text('{"host_id":"must-not-be-reused"}')
    monkeypatch.setattr(settings, "data_root", root)
    with pytest.raises(SystemExit, match="nuevos"):
        restore(tmp_path / "unused-backup.tar.gz")


def test_optional_models_backup_flattens_safe_links_and_excludes_external_targets(
    client, tmp_path, monkeypatch
):
    cache = settings.directory("models")
    (cache / "blobs").mkdir()
    (cache / "snapshots").mkdir()
    (cache / "blobs/weights.bin").write_bytes(b"synthetic-model-weights")
    (cache / "snapshots/model.bin").symlink_to("../blobs/weights.bin")
    secret = settings.directory("auth") / "private-token"
    secret.write_text("must-not-leave-authentication")
    (cache / "external-secret").symlink_to(secret)
    target = tmp_path / "models.tar.gz"
    backup(target, include_models=True)
    with tarfile.open(target) as archive:
        member = archive.getmember("models/snapshots/model.bin")
        assert member.isfile() and not member.issym()
        assert archive.extractfile(member).read() == b"synthetic-model-weights"
        assert "models/external-secret" not in archive.getnames()
    restored = tmp_path / "restored"
    for area in ("db", "media", "transcripts", "exports", "models", "auth"):
        (restored / area).mkdir(parents=True)
    monkeypatch.setattr(settings, "data_root", restored)
    restore(target)
    model = restored / "models/snapshots/model.bin"
    assert model.read_bytes() == b"synthetic-model-weights" and not model.is_symlink()
