import os

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app import admin, auth, media, worker
from app.api import create_app
from app.config import get_settings
from app.transcription.fake import FakeTranscriber

PASSWORD = "admin-secret"
ADMIN_USERNAME = "admin"
USER_PASSWORD = "correct horse"


@pytest.fixture
def settings(tmp_path, monkeypatch):
    # The suite runs on PostgreSQL, the engine of production. Point TEST_DATABASE_URL at a
    # throwaway database (e.g. postgresql+psycopg://postgres@127.0.0.1:5432/subtitle_test):
    # its schema is wiped before each test and rebuilt by the migrations.
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.fail("TEST_DATABASE_URL n'est pas défini (base PostgreSQL jetable pour les tests)")
    engine = create_engine(url, isolation_level="AUTOCOMMIT")
    with engine.connect() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
    engine.dispose()

    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    monkeypatch.setenv("ENABLED_MODELS", "fake")
    monkeypatch.setenv("DEFAULT_MODEL", "fake")
    monkeypatch.setenv("ENABLED_TRANSLATORS", "fake-en-fr")
    monkeypatch.setenv("ADMIN_USERNAME", ADMIN_USERNAME)
    monkeypatch.setenv("ADMIN_PASSWORD", PASSWORD)
    monkeypatch.setenv("MAX_UPLOAD_MB", "1")
    monkeypatch.setenv("MAX_REGISTRATIONS_PER_HOUR", "5")
    monkeypatch.setenv("HEARTBEAT_INTERVAL_S", "0.05")
    # Cheap hashing: the tests create many accounts.
    monkeypatch.setattr(auth, "_hasher", PasswordHasher(time_cost=1, memory_cost=8, parallelism=1))
    auth.reset_limiters()
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
def new_client(settings):
    """Factory of browsers: each call registers a new account on the same application.

    Called without an app, it creates the application; pass `client.app` to share it.
    """
    count = 0

    def _make(app=None, username=None) -> TestClient:
        nonlocal count
        count += 1
        browser = TestClient(app or create_app())
        username = username or f"user{count}"
        response = browser.post(
            "/api/auth/register", json={"username": username, "password": USER_PASSWORD}
        )
        assert response.status_code == 201, response.text
        return browser

    return _make


@pytest.fixture
def client(new_client):
    """The application, with its first user (alice) logged in."""
    return new_client(username="alice")


@pytest.fixture
def stranger(client, new_client):
    """Another registered user of the same application (its own session)."""
    return new_client(client.app)


@pytest.fixture
def admin_client(client, settings, monkeypatch):
    """Admin console, not logged in. Depends on `client` so both share the database."""
    # No user API is listening during the tests: skip the 2 s network probe.
    monkeypatch.setattr(admin, "_api_status", lambda settings: {"up": False, "detail": "stub"})
    admin._known_sessions.clear()
    admin._login_limiter.clear()
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
