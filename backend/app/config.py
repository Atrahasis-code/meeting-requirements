from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MRA_", extra="ignore")
    data_root: Path = Path("/data")
    database_connection: str | None = None
    database_password_file: Path | None = None
    allowed_hosts: str = "127.0.0.1,localhost,backend,testserver"
    public_url: str = "http://127.0.0.1:8080"
    max_upload_bytes: int = 4 * 1024**3
    analysis_provider: str = "chatgpt"
    transcription_provider: str = "whisper"
    test_mode: bool = False
    model_cache_root: Path | None = None
    cpu_threads: int = 3
    chunk_seconds: int = 300
    analysis_chunk_chars: int = 24000
    provider_timeout_seconds: int = 600
    worker_grace_seconds: int = 45
    nice: int = 10

    @property
    def database_url(self) -> str:
        connection = self.database_connection or f"sqlite:///{self.data_root / 'db/app.sqlite3'}"
        if self.database_password_file and connection.startswith("postgresql"):
            from sqlalchemy.engine import make_url

            return (
                make_url(connection)
                .set(password=self.database_password_file.read_text().strip())
                .render_as_string(hide_password=False)
            )
        return connection

    @property
    def callback_url(self) -> str:
        return self.public_url.rstrip("/") + "/auth/callback"

    def directory(self, name: str) -> Path:
        if name not in {"db", "media", "transcripts", "exports", "models", "auth"}:
            raise ValueError("Directorio no permitido")
        if name == "models" and self.model_cache_root is not None:
            return self.model_cache_root
        return self.data_root / name


settings = Settings()
