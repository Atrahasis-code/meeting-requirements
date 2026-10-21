import math
import os
import time
import subprocess
import uuid
from sqlalchemy import select
from pydantic import ValidationError
from .config import settings
from .db import SessionLocal
from . import models as m
from .repository import get
from .media import safe_path
from .transcripts import write_transcripts
from .analysis import split_input, validate_evidence, merge_results, store_result, require_selection
from .schemas import AnalysisResult
from .providers import provider, ProviderBlocked, analysis_validation_diagnostic

PROFILES = {"economy": ("base", 2), "balanced": ("small", 3), "quality": ("medium", 3)}


def progress(job_id, stage, value=None, meeting_status=None):
    with SessionLocal.begin() as session:
        job = get(session, m.ProcessingJob, job_id)
        job.stage, job.progress = stage, value
        if meeting_status:
            get(session, m.Meeting, job.meeting_id).status = meeting_status


def reconcile_words(words, chunk_start, owner_start, owner_end):
    """Assign each overlap word to one half-open core interval using its global midpoint."""
    return [
        dict(start=chunk_start + w.start, end=chunk_start + w.end, word=w.word)
        for w in words
        if owner_start <= chunk_start + (w.start + w.end) / 2 < owner_end
    ]


def transcribe(job_id, cancelled):
    with SessionLocal() as session:
        job = get(session, m.ProcessingJob, job_id)
        meeting = get(session, m.Meeting, job.meeting_id)
        media = session.scalar(select(m.MediaFile).where(m.MediaFile.meeting_id == meeting.id))
        if not media:
            raise ValueError("La grabación ya no está disponible")
        meeting_id, duration = meeting.id, media.duration
        media_path = safe_path("media", media.path)
        profile, language = job.params["profile"], job.params["language"]
        completed_chunks = job.checkpoint.get("chunks", 0)
    if settings.transcription_provider == "mock":
        if not settings.test_mode:
            raise ValueError("Transcripción simulada permitida únicamente en modo de prueba")
        with SessionLocal.begin() as session:
            if not session.scalar(
                select(m.TranscriptSegment.id).where(m.TranscriptSegment.meeting_id == meeting_id)
            ):
                session.add(
                    m.TranscriptSegment(
                        meeting_id=meeting_id,
                        start=0,
                        end=min(duration, 2),
                        original_text="El sistema debe permitir registrar solicitudes y consultar su estado.",
                        detection={"simulated": True},
                        chunk_index=0,
                    )
                )
    else:
        import onnxruntime

        onnxruntime.disable_telemetry_events()
        from faster_whisper import WhisperModel
        from faster_whisper.utils import download_model

        model_name, threads = PROFILES[profile]
        progress(job_id, "downloading_model", meeting_status="preparing_audio")
        model_path = download_model(model_name, cache_dir=str(settings.directory("models")))
        if cancelled.is_set():
            raise InterruptedError()
        progress(job_id, "loading_model")
        model = WhisperModel(
            model_path,
            device="cpu",
            compute_type="int8",
            cpu_threads=min(threads, settings.cpu_threads),
            num_workers=1,
        )
        chunk_directory = safe_path("transcripts", meeting_id)
        chunk_directory.mkdir(exist_ok=True)
        try:
            chunks = math.ceil(duration / settings.chunk_seconds)
            for index in range(completed_chunks, chunks):
                if cancelled.is_set():
                    raise InterruptedError()
                start, end = (
                    index * settings.chunk_seconds,
                    min(duration, (index + 1) * settings.chunk_seconds),
                )
                decode_start, decode_end = max(0, start - 2), min(duration, end + 2)
                output = chunk_directory / "active-chunk.wav"
                progress(job_id, "preparing_audio", start / duration, "preparing_audio")
                subprocess.run(
                    [
                        "ffmpeg",
                        "-nostdin",
                        "-protocol_whitelist",
                        "file,pipe",
                        "-v",
                        "error",
                        "-threads",
                        "1",
                        "-protocol_whitelist",
                        "file,pipe",
                        "-ss",
                        str(decode_start),
                        "-i",
                        str(media_path),
                        "-t",
                        str(decode_end - decode_start),
                        "-vn",
                        "-ac",
                        "1",
                        "-ar",
                        "16000",
                        "-c:a",
                        "pcm_s16le",
                        "-y",
                        str(output),
                    ],
                    capture_output=True,
                    check=True,
                    timeout=180,
                )
                progress(job_id, "transcribing", start / duration, "transcribing")
                segments, _ = model.transcribe(
                    str(output), language=language, beam_size=3, vad_filter=True, word_timestamps=True
                )
                batch = []
                for segment in segments:
                    if cancelled.is_set():
                        raise InterruptedError()
                    words = reconcile_words(segment.words or [], decode_start, start, end)
                    if not words:
                        continue
                    batch.append(
                        m.TranscriptSegment(
                            id=str(uuid.uuid4()),
                            meeting_id=meeting_id,
                            start=max(0, words[0]["start"]),
                            end=min(duration, words[-1]["end"]),
                            original_text="".join(w["word"] for w in words).strip(),
                            chunk_index=index,
                            detection={
                                "avg_logprob": segment.avg_logprob,
                                "no_speech_prob": segment.no_speech_prob,
                            },
                        )
                    )
                with SessionLocal.begin() as session:
                    session.add_all(batch)
                    job = get(session, m.ProcessingJob, job_id)
                    job.checkpoint = {"chunks": index + 1}
                    job.progress = end / duration
                    from .runtime import runtime

                    runtime.checkpointed(session, job)
                output.unlink(missing_ok=True)
        finally:
            del model
            (chunk_directory / "active-chunk.wav").unlink(missing_ok=True)
    if cancelled.is_set():
        raise InterruptedError()
    with SessionLocal.begin() as session:
        segments = session.scalars(
            select(m.TranscriptSegment)
            .where(m.TranscriptSegment.meeting_id == meeting_id)
            .order_by(m.TranscriptSegment.start)
        ).all()
        write_transcripts(meeting_id, segments)
    from .runtime import runtime

    runtime.artifacts_ready(job_id)
    with SessionLocal.begin() as session:
        meeting = get(session, m.Meeting, meeting_id)
        from .runtime import runtime

        runtime.before_complete(session, get(session, m.ProcessingJob, job_id))
        meeting.status, meeting.transcript_revision = "transcribed", meeting.transcript_revision + 1
        job = get(session, m.ProcessingJob, job_id)
        job.status, job.stage, job.progress = "completed", "completed", 1.0


def analyze(job_id, cancelled):
    with SessionLocal() as session:
        job = get(session, m.ProcessingJob, job_id)
        require_selection(job.params["snapshot"])
        from .runtime import runtime

        data, cached = runtime.analysis_data(job, job.params["snapshot"]), job.checkpoint.get("blocks", [])
    blocks = split_input(data)
    results = [AnalysisResult.model_validate(r) for r in cached]
    implementation = provider(data["provider"])
    for index in range(len(results), len(blocks)):
        if cancelled.is_set():
            raise InterruptedError()
        progress(job_id, "analyzing", index / len(blocks), "analyzing")
        result = validate_evidence(implementation.analyze(blocks[index], cancelled), blocks[index])
        results.append(result)
        with SessionLocal.begin() as session:
            get(session, m.ProcessingJob, job_id).checkpoint = {"blocks": [r.model_dump() for r in results]}
    if cancelled.is_set():
        raise InterruptedError()
    try:
        merged = merge_results(results)
    except ValidationError as error:
        raise ProviderBlocked(
            "invalid_analysis_merge",
            "No se pudo consolidar el análisis guardado: "
            + analysis_validation_diagnostic(error)
            + ". Se conservaron los fragmentos válidos para revisión y reintento manual.",
        ) from None
    result = validate_evidence(merged, data)
    with SessionLocal.begin() as session:
        store_result(session, get(session, m.ProcessingJob, job_id), result)
    if data["provider"] == "chatgpt":
        from .auth import update_profile

        update_profile(
            account_id=data["account_id"],
            inference_verified=True,
            last_inference_at=time.time(),
            last_inference_model=data["model"],
            error=None,
        )


def execute(job_id, cancelled, result_queue):
    # New process releases all native model memory at exit, including on cancellation.
    if os.getpgrp() != os.getpid():
        os.setsid()
    try:
        os.nice(settings.nice)
    except OSError:
        pass
    try:
        with SessionLocal() as session:
            kind = get(session, m.ProcessingJob, job_id).kind
        (transcribe if kind == "transcribe" else analyze)(job_id, cancelled)
        result_queue.put({"status": "completed"})
    except InterruptedError:
        result_queue.put({"status": "cancelled"})
    except Exception as error:
        from .providers import ProviderBlocked

        if isinstance(error, ProviderBlocked):
            result_queue.put({"status": "blocked", "reason": error.code, "error": error.message})
        else:
            # Input content and raw provider exceptions must not enter logs or API errors.
            result_queue.put(
                {
                    "status": "failed",
                    "error": f"Falló la etapa de procesamiento ({type(error).__name__}). Reintenta o revisa la configuración.",
                }
            )
