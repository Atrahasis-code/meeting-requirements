"""Cold-start probes with no ORM, TLS, provider or inference imports."""

import sys


def worker_healthy(root) -> bool:
    import json
    import sqlite3
    import time
    from pathlib import Path

    try:
        import os

        connection = os.environ.get("MRA_DATABASE_CONNECTION", "")
        if connection.startswith("postgresql"):
            import psycopg

            password_file = os.environ.get("MRA_DATABASE_PASSWORD_FILE")
            with psycopg.connect(
                connection.replace("postgresql+psycopg:", "postgresql:"),
                password=Path(password_file).read_text().strip() if password_file else None,
                connect_timeout=3,
            ) as database:
                row = database.execute("SELECT value FROM app_settings WHERE key=%s", ("worker",)).fetchone()
            return bool(row and time.time() - row[0].get("heartbeat", 0) < 20)
        uri = (Path(root) / "db/app.sqlite3").resolve().as_uri() + "?mode=ro"
        with sqlite3.connect(uri, uri=True, timeout=2) as database:
            row = database.execute("SELECT value FROM app_settings WHERE key=?", ("worker",)).fetchone()
        return bool(row and time.time() - json.loads(row[0]).get("heartbeat", 0) < 20)
    except Exception:
        return False


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "worker":
        import os

        raise SystemExit(0 if worker_healthy(os.environ.get("MRA_DATA_ROOT", "/data")) else 1)
    import socket

    try:
        with socket.create_connection(("127.0.0.1", 8000), timeout=3) as connection:
            connection.sendall(b"GET /api/health HTTP/1.1\r\nHost: backend\r\nConnection: close\r\n\r\n")
            with connection.makefile("rb") as stream:
                status = stream.readline(128).split()
        raise SystemExit(0 if len(status) > 1 and status[1] == b"200" else 1)
    except OSError:
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
