import multiprocessing as mp
import os
import queue
import signal
import time
from sqlalchemy import select, text
from .config import settings
from .db import SessionLocal
from . import models as m
from .repository import get, set_setting
from .processing import execute


def claim():
    with SessionLocal() as session:
        if session.bind.dialect.name == "sqlite":
            session.execute(text("BEGIN IMMEDIATE"))
        job = session.scalar(
            select(m.ProcessingJob)
            .where(m.ProcessingJob.status == "queued")
            .order_by(m.ProcessingJob.created_at)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        if not job:
            session.rollback()
            return None
        job.status, job.stage = "running", "starting"
        identity = job.id
        session.commit()
        return identity


def recover():
    # Called only after acquiring the OS worker lock; no previous worker can still own jobs.
    with SessionLocal.begin() as session:
        for job in session.scalars(select(m.ProcessingJob).where(m.ProcessingJob.status == "running")):
            job.status, job.stage, job.error = (
                "interrupted",
                "interrupted",
                "Worker interrumpido; reintento manual disponible",
            )
            get(session, m.Meeting, job.meeting_id).status = "failed"


def heartbeat():
    with SessionLocal.begin() as session:
        set_setting(session, "worker", {"heartbeat": time.time(), "pid": os.getpid()})


def run():
    stop = False

    def shutdown(*_):
        nonlocal stop
        stop = True

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    recover()
    context = mp.get_context("spawn")
    last_heartbeat = 0
    while not stop:
        if time.monotonic() - last_heartbeat >= 3:
            heartbeat()
            last_heartbeat = time.monotonic()
        identity = claim()
        if identity is None:
            time.sleep(0.5)
            continue
        cancelled, messages = context.Event(), context.Queue()
        process = context.Process(target=execute, args=(identity, cancelled, messages))
        process.start()
        started, cancellation_start = time.monotonic(), None
        while process.is_alive():
            if time.monotonic() - last_heartbeat >= 3:
                heartbeat()
                last_heartbeat = time.monotonic()
            with SessionLocal() as session:
                job = get(session, m.ProcessingJob, identity)
                cancel = job.cancel_requested
                timeout = (
                    job.kind == "analyze" and time.monotonic() - started > settings.provider_timeout_seconds
                )
            if stop or cancel or timeout:
                cancelled.set()
                if cancellation_start is None:
                    cancellation_start = time.monotonic()
                if time.monotonic() - cancellation_start > settings.worker_grace_seconds:
                    try:
                        os.killpg(process.pid, signal.SIGTERM)
                    except ProcessLookupError:
                        pass
                    process.join(3)
                    if process.is_alive():
                        os.killpg(process.pid, signal.SIGKILL)
                    break
            process.join(0.5)
        process.join()
        try:
            result = messages.get(timeout=1)
        except queue.Empty:
            result = {
                "status": "cancelled" if cancelled.is_set() and not stop else "interrupted",
                "error": "El proceso se interrumpió; se conservan los checkpoints",
            }
        with SessionLocal.begin() as session:
            job = get(session, m.ProcessingJob, identity)
            if job.status != "completed":
                job.status = "interrupted" if stop else result["status"]
                job.stage, job.error = job.status, result.get("error")
                job.blocked_reason = result.get("reason")
                meeting = get(session, m.Meeting, job.meeting_id)
                meeting.status = (
                    "queued"
                    if job.status == "blocked"
                    else "cancelled"
                    if job.status == "cancelled"
                    else "failed"
                )
        messages.close()
    with SessionLocal.begin() as session:
        set_setting(session, "worker", {"heartbeat": 0, "stopped": True})


def main():
    from .locking import worker_lock

    with worker_lock():
        run()


if __name__ == "__main__":
    main()
