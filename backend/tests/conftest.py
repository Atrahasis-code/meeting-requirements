import os
import shutil
import tempfile
from pathlib import Path

# Always isolate even when pytest is invoked using the normal backend service.
if os.environ.get("MRA_TEST_DATABASE_CONNECTION"):
    os.environ["MRA_DATABASE_CONNECTION"] = os.environ["MRA_TEST_DATABASE_CONNECTION"]
else:
    os.environ.pop("MRA_DATABASE_CONNECTION", None)
    os.environ.pop("MRA_DATABASE_PASSWORD_FILE", None)

os.environ["MRA_DATA_ROOT"] = tempfile.mkdtemp(prefix="mra-tests-", dir="/tmp")
os.environ["MRA_TEST_MODE"] = "true"
os.environ["MRA_TRANSCRIPTION_PROVIDER"] = "mock"
os.environ["MRA_ANALYSIS_PROVIDER"] = "mock"

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from app.config import settings
from app.db import engine
from app.main import app


@pytest.fixture(autouse=True)
def database():
    engine.dispose()
    root = settings.data_root
    shutil.rmtree(root, ignore_errors=True)
    for name in ("db", "media", "transcripts", "exports", "models", "auth"):
        (root / name).mkdir(parents=True)
    if engine.dialect.name == "postgresql":
        assert engine.url.database == "mra_test", "Refusing to reset a non-test database"
        with engine.begin() as connection:
            connection.exec_driver_sql("DROP SCHEMA public CASCADE")
            connection.exec_driver_sql("CREATE SCHEMA public")
    cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    cfg.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "migrations"))
    command.upgrade(cfg, "head")
    yield
    engine.dispose()


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client


@pytest.fixture
def wav():
    import io
    import wave

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(b"\0\0" * 16000)
    return buffer.getvalue()


@pytest.fixture
def meeting(client, wav):
    project = client.post(
        "/api/projects", json={"name": "Portal", "context": "Gestión de solicitudes"}
    ).json()
    meeting = client.post(
        "/api/meetings", json={"project_id": project["id"], "title": "Descubrimiento", "date": "2026-10-19"}
    ).json()
    response = client.post(
        f"/api/meetings/{meeting['id']}/upload", files={"file": ("prueba.wav", wav, "audio/wav")}
    )
    assert response.status_code == 201, response.text
    return meeting
