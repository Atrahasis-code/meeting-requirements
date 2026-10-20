"""Root-only Compose initializer: copy only an explicitly supplied password file."""

import os
from pathlib import Path


def write_private(directory, name, value, uid):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / name
    if target.exists() and target.read_bytes() != value:
        raise ValueError(
            "Credential changed; perform explicit database/key rotation instead of replacing it implicitly"
        )
    os.chown(directory, uid, uid)
    os.chmod(directory, 0o700)
    if not target.exists():
        fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
    os.chown(target, uid, uid)
    os.chmod(target, 0o600)


def main():
    password = Path("/run/secrets/postgres_password").read_bytes()
    if not password.strip() or b"\n" in password.strip():
        raise ValueError("Use one nonempty password line")
    password = password.strip() + b"\n"
    write_private("/server", "password", password, 999)
    write_private("/application", "password", password, 10001)


if __name__ == "__main__":
    main()
