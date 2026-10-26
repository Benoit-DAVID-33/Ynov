import os

import pytest
from fastapi.testclient import TestClient

from app import admin, db, media, worker
from app.api import create_app
from app.config import get_settings
from app.transcription.fake import FakeTranscriber

PASSWORD = "secret"


@pytest.fixture
def settings(tmp_path, monkeypatch):
    # TEST_DATABASE_URL runs the same suite against another database, e.g. the
    # PostgreSQL of the Docker stack. Its tables are dropped before each test.
    url = os.environ.get("TEST_DATABASE_URL") or f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    if not url.startswith("sqlite"):
        db.init_db(url)
        db.Base.metadata.drop_all(db._engine)
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    monkeypatch.setenv("ENABLED_MODELS", "fake")
    monkeypatch.setenv("DEFAULT_MODEL", "fake")
    monkeypatch.setenv("ENABLED_TRANSLATORS", "fake-en-fr")
    monkeypatch.setenv("ADMIN_PASSWORD", PASSWORD)
    monkeypatch.setenv("MAX_UPLOAD_MB", "1")
    monkeypatch.setenv("HEARTBEAT_INTERVAL_S", "0.05")
    get_settings.cache_clear()
    FakeTranscriber.calls = 0
    yield get_settings()
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def fake_ffmpeg(monkeypatch):
    """ffmpeg is not required to run the tests: its outputs are stubbed.

    Returns the keyword arguments received by the last burn_subtitles call.
    """
    burn_calls = {}

    def burn(video, srt, dest, **kwargs):
        burn_calls.update(kwargs)
        kwargs["on_progress"](0.5)
        dest.write_bytes(b"burned")

    monkeypatch.setattr(media, "probe_duration", lambda path: 10.0)
    monkeypatch.setattr(media, "extract_audio", lambda source, dest: dest.write_bytes(b"wav"))
    monkeypatch.setattr(media, "burn_subtitles", burn)
    monkeypatch.setattr(
        media, "mux_subtitles", lambda video, srt, dest, language, title: dest.write_bytes(b"muxed")
    )
    return burn_calls


@pytest.fixture
def client(settings):
    return TestClient(create_app())


@pytest.fixture
def admin_client(client, settings, monkeypatch):
    """Admin console, not logged in. Depends on `client` so both share the database."""
    # No user API is listening during the tests: skip the 2 s network probe.
    monkeypatch.setattr(admin, "_api_status", lambda settings: {"up": False, "detail": "stub"})
    admin._sessions.clear()
    admin._failures.clear()
    return TestClient(admin.create_app())


@pytest.fixture
def submit(client):
    """Upload a file and queue a job; returns the job as JSON."""

    def _submit(filename="clip.mp4", output_type="text", **options):
        upload = client.post("/api/uploads", files={"file": (filename, b"data")}).json()
        body = {"upload_id": upload["id"], "output_type": output_type, **options}
        response = client.post("/api/jobs", json=body)
        assert response.status_code == 201, response.text
        return response.json()

    return _submit


@pytest.fixture
def run_worker(settings):
    def _run():
        while worker.process_next(settings):
            pass

    return _run
