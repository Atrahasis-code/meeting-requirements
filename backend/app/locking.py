"""Singleton lock appropriate to the configured local database."""

import contextlib
import fcntl
from sqlalchemy import text
from .db import engine
from .config import settings


@contextlib.contextmanager
def worker_lock():
    if engine.dialect.name == "postgresql":
        with engine.connect() as connection:
            acquired = connection.scalar(text("SELECT pg_try_advisory_lock(59278134)"))
            connection.commit()
            if not acquired:
                raise SystemExit("Ya existe un worker activo para esta base de datos")
            try:
                yield
            finally:
                connection.execute(text("SELECT pg_advisory_unlock(59278134)"))
                connection.commit()
    else:
        with (settings.directory("db") / "worker.lock").open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise SystemExit("Ya existe un worker activo para este volumen") from None
            try:
                yield
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)
