import os
import subprocess
import sys
from pathlib import Path
from .config import settings


def main():
    os.umask(0o007)
    for name in ("db", "media", "transcripts", "exports", "models", "auth"):
        path = settings.directory(name)
        path.mkdir(parents=True, exist_ok=True)
        if os.getuid() == 0:
            os.chown(path, 10001, 10001)
            os.chmod(path, 0o700 if name == "auth" else 0o770)
    incoming = settings.directory("media") / ".incoming"
    incoming.mkdir(exist_ok=True)
    if os.getuid() == 0:
        os.chown(incoming, 10001, 10001)
        os.chmod(incoming, 0o770)
    # Detect unsupported filesystems before SQLite gets used. Named Docker volumes are the default.
    mounts = Path("/proc/mounts").read_text().splitlines()
    candidate = str(settings.directory("db").resolve())
    matches = [
        line.split()
        for line in mounts
        if candidate == line.split()[1] or candidate.startswith(line.split()[1].rstrip("/") + "/")
    ]
    if matches and settings.database_url.startswith("sqlite:"):
        mount = max(matches, key=lambda parts: len(parts[1]))
        if mount[2] in {"nfs", "nfs4", "cifs", "smbfs", "9p", "fuse.sshfs", "virtiofs"}:
            raise SystemExit(
                "SQLite requiere un volumen local; no uses carpetas del host o sistemas de archivos de red"
            )
    if os.getuid() == 0:
        os.setgroups([])
        os.setgid(10001)
        os.setuid(10001)
    if "--prepare-only" in sys.argv:
        return
    from .db import engine

    with engine.connect() as connection:
        if engine.dialect.name == "sqlite":
            connection.exec_driver_sql("PRAGMA journal_mode=WAL")
        connection.commit()
    subprocess.run(["alembic", "upgrade", "head"], check=True)


if __name__ == "__main__":
    main()
