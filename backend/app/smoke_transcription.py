"""Opt-in real CPU inference on synthetic speech; downloads small only on request."""

import json
import argparse
import platform
import resource
import subprocess
import tempfile
import time
from pathlib import Path
import ctranslate2
import onnxruntime

from faster_whisper import WhisperModel
from .config import settings

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=("tiny", "base", "small"), default="small")
    args = parser.parse_args()
    onnxruntime.disable_telemetry_events()
    with tempfile.TemporaryDirectory() as directory:
        audio = Path(directory) / "synthetic.wav"
        subprocess.run(
            [
                "ffmpeg",
                "-nostdin",
                "-v",
                "error",
                "-f",
                "lavfi",
                "-i",
                "flite=text='The system must register requests and allow users to check their status. A reviewer will validate each requirement.':voice=slt",
                "-ar",
                "16000",
                str(audio),
            ],
            check=True,
        )
        start = time.monotonic()
        model = WhisperModel(
            args.model,
            device="cpu",
            compute_type="int8",
            cpu_threads=3,
            num_workers=1,
            download_root=str(settings.directory("models")),
        )
        segments, info = model.transcribe(
            str(audio), language="en", beam_size=3, vad_filter=True, word_timestamps=True
        )
        transcript = " ".join(s.text for s in segments)
        assert transcript.strip(), "No speech recognized"
        assert "int8" in ctranslate2.get_supported_compute_types("cpu")
        usage = resource.getrusage(resource.RUSAGE_SELF)
        print(
            json.dumps(
                dict(
                    architecture=platform.machine(),
                    model=args.model,
                    device="cpu",
                    compute_type="int8",
                    seconds=round(time.monotonic() - start, 2),
                    cpu_threads=3,
                    cpu_seconds=round(usage.ru_utime + usage.ru_stime, 2),
                    peak_rss_kib=usage.ru_maxrss,
                    transcript=transcript,
                ),
                ensure_ascii=False,
            )
        )
