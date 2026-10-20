import hashlib
import json
import math
import subprocess
import uuid
from pathlib import Path
from fastapi import HTTPException
from .config import settings

FORMATS = {
    ".mp4": {"mov", "mp4", "m4a", "3gp", "3g2", "mj2"},
    ".m4a": {"mov", "mp4", "m4a"},
    ".mp3": {"mp3"},
    ".wav": {"wav"},
}
MIMES = {".mp4": "video/mp4", ".m4a": "audio/mp4", ".mp3": "audio/mpeg", ".wav": "audio/wav"}


def safe_path(area: str, relative: str) -> Path:
    from .context import organization

    root = settings.directory(area).resolve()
    if organization.get() != "local" and area in {"media", "transcripts", "exports"}:
        import re

        if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", organization.get()):
            raise HTTPException(400, "Identificador de organización inválido")
        root = root / organization.get()
        root.mkdir(parents=True, exist_ok=True)
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or path == root:
        raise HTTPException(400, "Ruta no permitida")
    return path


def probe(path: Path, extension: str) -> float:
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-protocol_whitelist",
                "file,pipe",
                "-show_entries",
                "format=duration,format_name:stream=codec_type",
                "-of",
                "json",
                str(path),
            ],
            capture_output=True,
            timeout=30,
            check=True,
        )
        data = json.loads(result.stdout)
        duration = float(data["format"]["duration"])
        if not set(data["format"]["format_name"].split(",")) & FORMATS[extension]:
            raise ValueError("El contenido no coincide con la extensión")
        if (
            not math.isfinite(duration)
            or duration <= 0
            or not any(s["codec_type"] == "audio" for s in data["streams"])
        ):
            raise ValueError("No contiene audio válido")
        return duration
    except (ValueError, KeyError, subprocess.SubprocessError) as error:
        raise HTTPException(422, "Grabación corrupta, vacía, sin audio o formato incorrecto") from error


async def save_upload(upload):
    original = Path((upload.filename or "").replace("\\", "/")).name
    extension = Path(original).suffix.lower()
    if extension not in FORMATS:
        raise HTTPException(415, "Formato permitido: MP4, M4A, MP3 o WAV")
    name = str(uuid.uuid4()) + extension
    path = safe_path("media", name)
    digest = hashlib.sha256()
    size = 0
    try:
        with path.open("xb") as stream:
            while block := await upload.read(1024 * 1024):
                size += len(block)
                if size > settings.max_upload_bytes:
                    raise HTTPException(413, "La grabación excede el límite configurado")
                digest.update(block)
                stream.write(block)
        import asyncio

        duration = await asyncio.to_thread(probe, path, extension)
        return dict(
            path=name,
            original_name=original[:250],
            size=size,
            duration=duration,
            mime_type=MIMES[extension],
            sha256=digest.hexdigest(),
        )
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()
