"""Offline portable backups. Run with backend and worker stopped."""

import argparse
import hashlib
import io
import json
import sqlite3
import tarfile
import tempfile
from pathlib import Path
from .config import settings

AREAS = ("db", "media", "transcripts", "exports")


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def assert_idle():
    from .db import engine
    from sqlalchemy import text

    with engine.connect() as connection:
        if connection.scalar(text("SELECT count(*) FROM processing_jobs WHERE status='running'")):
            raise SystemExit("Detén backend y worker antes del mantenimiento")


def portable_snapshot(destination):
    from .db import engine, make_engine, Base

    if engine.dialect.name == "sqlite":
        with (
            sqlite3.connect(settings.directory("db") / "app.sqlite3") as source,
            sqlite3.connect(destination) as target,
        ):
            source.backup(target)
        return
    from alembic import command
    from alembic.config import Config

    target_engine = make_engine("sqlite:///" + str(destination))
    cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    cfg.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "migrations"))
    try:
        with target_engine.connect() as connection:
            cfg.attributes["connection"] = connection
            command.upgrade(cfg, "head")
        with (
            engine.connect().execution_options(isolation_level="REPEATABLE READ") as source,
            target_engine.begin() as target,
        ):
            with source.begin():
                for table in Base.metadata.sorted_tables:
                    rows = [dict(row) for row in source.execute(table.select()).mappings()]
                    if rows:
                        target.execute(table.insert(), rows)
    finally:
        target_engine.dispose()


def backup(output, include_models=False):
    from .locking import worker_lock

    with worker_lock():
        assert_idle()
        with tempfile.TemporaryDirectory() as temporary:
            db_copy = Path(temporary) / "app.sqlite3"
            portable_snapshot(db_copy)
            files = [(db_copy, "db/app.sqlite3")]
            for area in (*AREAS[1:], *(("models",) if include_models else ())):
                root = settings.directory(area)
                for path in sorted(root.rglob("*")):
                    if not path.is_file() or ".incoming" in path.parts:
                        continue
                    source_path = path
                    if path.is_symlink():
                        # Hugging Face snapshots link to model blobs. Flatten only
                        # links contained in that volume, never links to secrets.
                        if area != "models" or not path.resolve().is_relative_to(root.resolve()):
                            continue
                        source_path = path.resolve()
                    files.append((source_path, area + "/" + str(path.relative_to(root))))
            manifest = {
                "version": 1,
                "application": "0.1.0",
                "credentials_included": False,
                "files": {name: sha256(path) for path, name in files},
            }
            with tarfile.open(output, "w:gz", dereference=True) as archive:
                encoded = json.dumps(manifest).encode()
                entry = tarfile.TarInfo("manifest.json")
                entry.size = len(encoded)
                archive.addfile(entry, io.BytesIO(encoded))
                for path, name in files:
                    archive.add(path, arcname=name, recursive=False)


def restore(source):
    for area in (*AREAS, "models", "auth"):
        if any(
            not (area == "db" and p.name == "worker.lock" and p.is_file())
            and not (area == "media" and p.name == ".incoming" and p.is_dir() and not any(p.iterdir()))
            for p in settings.directory(area).iterdir()
        ):
            raise SystemExit("Restaura únicamente en volúmenes nuevos/vacíos")
    with tempfile.TemporaryDirectory() as temporary, tarfile.open(source, "r:gz") as archive:
        members = archive.getmembers()
        if len(members) > 200000:
            raise SystemExit("Archivo de backup demasiado grande")
        manifest = json.load(archive.extractfile("manifest.json"))
        if manifest.get("version") != 1 or manifest.get("credentials_included") is not False:
            raise SystemExit("Manifiesto incompatible")
        allowed = {*AREAS, "models"}
        for name in manifest.get("files", {}):
            path = Path(name)
            if path.is_absolute() or ".." in path.parts or not path.parts or path.parts[0] not in allowed:
                raise SystemExit("Ruta no permitida en manifiesto")
        for entry in members:
            path = Path(entry.name)
            if entry.name == "manifest.json":
                continue
            if (
                path.is_absolute()
                or ".." in path.parts
                or path.parts[0] not in allowed
                or not entry.isfile()
                or entry.name not in manifest["files"]
            ):
                raise SystemExit("Ruta o entrada no permitida en backup")
        archive.extractall(temporary, filter="data")
        root = Path(temporary)
        for name, expected in manifest["files"].items():
            path = root / name
            if not path.is_relative_to(root) or not path.is_file() or sha256(path) != expected:
                raise SystemExit("Checksum inválido")
        with sqlite3.connect(root / "db/app.sqlite3") as database:
            if (
                database.execute("PRAGMA integrity_check").fetchone()[0] != "ok"
                or database.execute("PRAGMA foreign_key_check").fetchall()
            ):
                raise SystemExit("La base de datos no pasó la validación de integridad")
        import shutil

        from .db import engine

        if engine.dialect.name == "postgresql":
            from .migrate_database import migrate

            migrate(root / "db/app.sqlite3")
        for name in manifest["files"]:
            if engine.dialect.name == "postgresql" and name == "db/app.sqlite3":
                continue
            target = settings.data_root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(root / name, target)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["backup", "restore"])
    parser.add_argument("path", type=Path)
    parser.add_argument("--include-models", action="store_true")
    args = parser.parse_args()
    backup(args.path, args.include_models) if args.operation == "backup" else restore(args.path)
