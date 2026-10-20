"""Storage interface: local distribution never imports hosted adapters."""

from typing import Protocol
from pathlib import Path
from .media import safe_path


class Storage(Protocol):
    def put_file(self, area: str, key: str, path: Path) -> None: ...
    def fetch_file(self, area: str, key: str, path: Path, max_bytes: int) -> None: ...
    def delete(self, area: str, key: str) -> None: ...


class LocalStorage:
    def put_file(self, area, key, path):
        import shutil

        target = safe_path(area, key)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.resolve() != Path(path).resolve():
            shutil.copyfile(path, target)

    def fetch_file(self, area, key, path, max_bytes):
        import shutil

        source = safe_path(area, key)
        if source.stat().st_size > max_bytes:
            raise ValueError("Archivo demasiado grande")
        if source.resolve() != Path(path).resolve():
            shutil.copyfile(source, path)

    def delete(self, area, key):
        safe_path(area, key).unlink(missing_ok=True)
