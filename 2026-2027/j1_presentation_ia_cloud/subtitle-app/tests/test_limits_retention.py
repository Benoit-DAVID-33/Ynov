from datetime import timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from app import media, retention
from app.db import session_scope
from app.models import Job, Upload, utcnow


def _upload(client, name="clip.mp4"):
    return client.post("/api/uploads", files={"file": (name, b"data")})


def _purge(settings):
    with session_scope() as session:
        return retention.purge(session, settings)


def _files(settings, job):
    return Path(settings.results_dir / job["id"]).exists(), _upload_path(job).exists()


def _upload_path(job):
    with session_scope() as session:
        return Path(session.get(Upload, job["upload_id"]).path)


# --- limits -----------------------------------------------------------------

def test_config_exposes_the_limits(client, settings):
    config = client.get("/api/config").json()
    assert (config["max_duration_s"], config["max_upload_mb"]) == (7200.0, 1)


def test_media_longer_than_the_limit_is_rejected_and_not_kept(client, settings, monkeypatch):
    monkeypatch.setattr(media, "probe_duration", lambda path: settings.max_duration_s + 1)
    response = _upload(client)
    assert response.status_code == 413
    assert "120 min" in response.json()["detail"]
    assert list(settings.uploads_dir.iterdir()) == []


def test_media_at_the_limit_is_accepted(client, settings, monkeypatch):
    monkeypatch.setattr(media, "probe_duration", lambda path: settings.max_duration_s)
    assert _upload(client).status_code == 201


def test_unreadable_media_is_rejected_and_not_kept(client, settings, monkeypatch):
    monkeypatch.setattr(media, "probe_duration", lambda path: None)
    assert _upload(client).status_code == 422
    assert list(settings.uploads_dir.iterdir()) == []


# --- retention --------------------------------------------------------------

def test_new_upload_replaces_the_previous_one_but_keeps_its_history(
    client, admin_client, submit, run_worker, settings
):
    old = submit("old.mp4", "subtitles")
    run_worker()
    new = submit("new.mp4", "text")
    run_worker()

    assert _purge(settings) == 1
    assert _files(settings, old) == (False, False)
    assert _files(settings, new) == (True, True)
    assert _purge(settings) == 0  # nothing left to do

    # The files are gone...
    assert client.get(f"/api/jobs/{old['id']}").json()["artifacts"] == []
    assert client.get(f"/api/jobs/{old['id']}/download").status_code == 410
    body = {"upload_id": old["upload_id"], "output_type": "text"}
    assert client.post("/api/jobs", json=body).status_code == 410
    # ...but the answer and the statistics are kept for the administrator.
    admin_client.post("/api/login", json={"password": "secret"})
    assert admin_client.get("/api/overview").json()["stats"]["completed"]["total"] == 2
    texts = {job["filename"]: job["text"] for job in admin_client.get("/api/jobs").json()}
    assert texts["old.mp4"] == "Hello world. This is a fake transcription."


def test_each_visitor_keeps_their_own_latest_file(client, submit, run_worker, settings):
    mine = submit("mine.mp4")
    other_visitor = TestClient(client.app)
    theirs = _upload(other_visitor, "theirs.mp4").json()
    run_worker()

    assert _purge(settings) == 0
    assert _files(settings, mine) == (True, True)
    with session_scope() as session:
        owners = {u.owner_id for u in session.query(Upload)}
        assert len(owners) == 2 and None not in owners
        assert Path(session.get(Upload, theirs["id"]).path).exists()


def test_file_still_being_processed_is_never_purged(client, submit, run_worker, settings):
    queued = submit("first.mp4")  # still in the queue
    _upload(client, "second.mp4")
    assert _purge(settings) == 0
    assert _upload_path(queued).exists()

    run_worker()
    assert _purge(settings) == 1
    assert not _upload_path(queued).exists()


def test_latest_file_expires_after_the_retention_period(client, submit, run_worker, settings):
    job = submit()
    run_worker()
    with session_scope() as session:
        session.get(Upload, job["upload_id"]).created_at = utcnow() - timedelta(days=8)
    assert _purge(settings) == 1
    assert _files(settings, job) == (False, False)
    with session_scope() as session:
        assert session.get(Job, job["id"]).text.startswith("Hello")


def test_last_upload_is_returned_to_its_visitor_only(client, submit, run_worker):
    assert client.get("/api/uploads/last").json() == {"upload": None, "jobs": []}

    submit("first.mp4")
    job = submit("latest.mp4", "subtitles")
    run_worker()
    last = client.get("/api/uploads/last").json()
    assert last["upload"]["filename"] == "latest.mp4"
    assert [(j["id"], j["status"]) for j in last["jobs"]] == [(job["id"], "done")]

    assert TestClient(client.app).get("/api/uploads/last").json()["upload"] is None
