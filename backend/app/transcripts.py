import json
from .media import safe_path


def text(segment):
    return segment.revised_text if segment.revised_text is not None else segment.original_text


def timestamp(seconds, separator="."):
    millis = max(0, round(seconds * 1000))
    hours, rest = divmod(millis, 3600000)
    minutes, rest = divmod(rest, 60000)
    seconds, millis = divmod(rest, 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02}{separator}{millis:03}"


def render_transcripts(segments):
    data = [
        dict(
            id=s.id,
            start=s.start,
            end=s.end,
            original_text=s.original_text,
            revised_text=s.revised_text,
            reviewed=s.reviewed,
            doubtful=s.doubtful,
            detection=s.detection,
        )
        for s in segments
    ]
    srt, vtt = [], ["WEBVTT\n"]
    for index, segment in enumerate(segments, 1):
        srt.append(
            f"{index}\n{timestamp(segment.start, ',')} --> {timestamp(segment.end, ',')}\n{text(segment)}\n"
        )
        vtt.append(f"{timestamp(segment.start)} --> {timestamp(segment.end)}\n{text(segment)}\n")
    return {
        "json": json.dumps(data, ensure_ascii=False, indent=2),
        "txt": "\n".join(text(s) for s in segments),
        "srt": "\n".join(srt),
        "vtt": "\n".join(vtt),
    }


def write_transcripts(meeting_id, segments):
    directory = safe_path("transcripts", meeting_id)
    directory.mkdir(exist_ok=True)
    for extension, content in render_transcripts(segments).items():
        temporary = directory / f"transcript.{extension}.tmp"
        temporary.write_text(content, encoding="utf-8")
        temporary.replace(directory / f"transcript.{extension}")
