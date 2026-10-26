from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app import jobs, media, retention
from app.db import session_scope
from app.models import Upload, UploadSession, utcnow

CHUNK = 1024  # bytes sent per request in these tests


@pytest.fixture
def stranger(client):
    """Another visitor of the same application (its own cookie)."""
    return TestClient(client.app)


def _set_duration(job, seconds):
    with session_scope() as session:
        session.get(Upload, job["upload_id"]).duration_s = seconds


# --- results are private to the visitor who uploaded ------------------------

def test_another_visitor_cannot_read_or_use_someone_elses_work(client, stranger, submit, run_worker):
    job = submit("clip.mp4", "video_subtitles")
    run_worker()
    base = f"/api/jobs/{job['id']}"

    for path in (base, f"{base}/transcript", f"{base}/download", f"{base}/files/video.mp4"):
        assert client.get(path).status_code == 200
        assert stranger.get(path).status_code == 404  # same answer as an unknown identifier
    body = {"upload_id": job["upload_id"], "output_type": "text"}
    assert stranger.post("/api/jobs", json=body).status_code == 404
    assert client.post("/api/jobs", json=body).status_code == 201


def test_visitor_without_cookie_is_a_stranger(client, submit, run_worker):
    job = submit()
    run_worker()
    client.cookies.clear()
    assert client.get(f"/api/jobs/{job['id']}").status_code == 404


def test_uploads_made_before_ownership_existed_stay_readable(client, stranger, submit, run_worker):
    job = submit()
    run_worker()
    with session_scope() as session:
        session.get(Upload, job["upload_id"]).owner_id = None
    assert stranger.get(f"/api/jobs/{job['id']}/download").status_code == 200


# --- queue admission --------------------------------------------------------

def test_queue_refuses_new_work_beyond_the_media_limit(client, stranger, submit, settings, monkeypatch):
    monkeypatch.setattr(settings, "max_pending_media_s", 25.0)  # each test file lasts 10 s
    submit("a.mp4")
    assert client.get("/api/queue").json() == {
        "pending_media_s": 10.0, "max_pending_media_s": 25.0, "accepting": True,
    }
    submit("b.mp4")

    upload = stranger.post("/api/uploads", files={"file": ("c.mp4", b"data")}).json()
    refused = stranger.post("/api/jobs", json={"upload_id": upload["id"], "output_type": "text"})
    assert refused.status_code == 503
    assert refused.headers["retry-after"] == "60"
    assert "saturé" in refused.json()["detail"]


def test_queue_accepts_again_as_running_jobs_progress(client, submit, settings, monkeypatch):
    monkeypatch.setattr(settings, "max_pending_media_s", 15.0)
    first = submit("a.mp4")
    body = {"upload_id": first["upload_id"], "output_type": "subtitles"}
    assert client.post("/api/jobs", json=body).status_code == 503

    with session_scope() as session:
        jobs.claim_next(session)
        jobs.set_progress(session, first["id"], "transcription", 60)
    assert client.get("/api/queue").json()["pending_media_s"] == pytest.approx(4.0)
    assert client.post("/api/jobs", json=body).status_code == 201


def test_empty_queue_accepts_a_file_longer_than_the_limit(client, submit, settings, monkeypatch):
    monkeypatch.setattr(settings, "max_pending_media_s", 5.0)
    assert submit("long.mp4")["status"] == "queued"
    assert client.get("/api/queue").json()["accepting"] is False


def test_one_visitor_cannot_fill_the_queue_alone(client, stranger, submit, settings):
    first = submit()
    body = {"upload_id": first["upload_id"], "output_type": "subtitles"}
    for _ in range(settings.max_pending_jobs_per_visitor - 1):
        assert client.post("/api/jobs", json=body).status_code == 201
    refused = client.post("/api/jobs", json=body)
    assert refused.status_code == 429 and "annulez" in refused.json()["detail"]

    # Others are not affected, and cancelling frees a slot.
    theirs = stranger.post("/api/uploads", files={"file": ("x.mp4", b"data")}).json()
    assert stranger.post("/api/jobs", json={"upload_id": theirs["id"], "output_type": "text"}).status_code == 201
    client.post(f"/api/jobs/{first['id']}/cancel")
    assert client.post("/api/jobs", json=body).status_code == 201


def test_correcting_subtitles_is_not_subject_to_the_queue_limit(
    client, submit, run_worker, settings, monkeypatch
):
    job = submit()
    run_worker()
    monkeypatch.setattr(settings, "max_pending_media_s", 0.0)
    response = client.put(f"/api/jobs/{job['id']}/segments", json={"texts": ["a", "b"]})
    assert response.status_code == 200


# --- resumable upload -------------------------------------------------------

def _start(client, name="clip.mp4", size=3000):
    response = client.post("/api/uploads/sessions", json={"filename": name, "size_bytes": size})
    assert response.status_code == 201, response.text
    return response.json()


def _send(client, session_id, offset, data):
    return client.put(
        f"/api/uploads/sessions/{session_id}",
        data={"offset": str(offset)},
        files={"chunk": ("blob", data)},
    )


def test_file_sent_in_chunks_becomes_an_upload(client, settings):
    content = bytes(range(256)) * 12  # 3072 bytes
    started = _start(client, size=len(content))
    assert started["received_bytes"] == 0 and started["chunk_bytes"] == 8 * 1024 * 1024

    for offset in range(0, len(content), CHUNK):
        sent = _send(client, started["id"], offset, content[offset:offset + CHUNK])
        assert sent.status_code == 200
    assert sent.json()["received_bytes"] == len(content)

    done = client.post(f"/api/uploads/sessions/{started['id']}/complete")
    assert done.status_code == 201
    upload = done.json()
    assert (upload["filename"], upload["size_bytes"], upload["kind"]) == ("clip.mp4", len(content), "video")
    with session_scope() as session:
        stored = session.get(Upload, upload["id"])
        assert open(stored.path, "rb").read() == content
        assert session.get(UploadSession, started["id"]) is None
    assert list(settings.partial_dir.iterdir()) == []
    assert client.post("/api/jobs", json={"upload_id": upload["id"], "output_type": "text"}).status_code == 201


def test_interrupted_upload_resumes_where_the_server_stands(client):
    content = b"x" * 2500
    started = _start(client, size=len(content))
    _send(client, started["id"], 0, content[:CHUNK])

    # The answer to the first chunk was lost: the client sends it again...
    again = _send(client, started["id"], 0, content[:CHUNK])
    assert again.status_code == 409 and again.json()["received_bytes"] == CHUNK
    # ...or it skipped ahead after a failed chunk: refused too, nothing is corrupted.
    assert _send(client, started["id"], 2000, content[2000:]).status_code == 409

    # After a page reload the client asks where to resume.
    resume_at = client.get(f"/api/uploads/sessions/{started['id']}").json()["received_bytes"]
    assert resume_at == CHUNK
    assert client.post(f"/api/uploads/sessions/{started['id']}/complete").status_code == 409  # incomplete
    _send(client, started["id"], resume_at, content[resume_at:])
    assert client.post(f"/api/uploads/sessions/{started['id']}/complete").status_code == 201


def test_upload_session_limits(client, stranger, settings):
    too_big = settings.max_upload_mb * 1024 * 1024 + 1
    assert client.post("/api/uploads/sessions", json={"filename": "a.mp4", "size_bytes": too_big}).status_code == 413
    assert client.post("/api/uploads/sessions", json={"filename": "a.pdf", "size_bytes": 10}).status_code == 415
    assert client.post("/api/uploads/sessions", json={"filename": "a.mp4", "size_bytes": 0}).status_code == 422

    started = _start(client, size=100)
    assert _send(client, started["id"], 0, b"x" * 101).status_code == 413  # more than announced
    assert _send(stranger, started["id"], 0, b"x").status_code == 404
    assert stranger.get(f"/api/uploads/sessions/{started['id']}").status_code == 404


def test_completed_file_is_checked_like_any_upload(client, settings, monkeypatch):
    monkeypatch.setattr(media, "probe_duration", lambda path: settings.max_duration_s + 1)
    started = _start(client, size=4)
    _send(client, started["id"], 0, b"data")
    assert client.post(f"/api/uploads/sessions/{started['id']}/complete").status_code == 413
    assert list(settings.uploads_dir.iterdir()) == [] and list(settings.partial_dir.iterdir()) == []


def test_unfinished_uploads_do_not_pile_up(client, settings):
    first = _start(client, size=100)
    _send(client, first["id"], 0, b"x" * 50)
    second = _start(client, "other.mp4", size=100)  # the visitor moved on to another file
    assert client.get(f"/api/uploads/sessions/{first['id']}").status_code == 404
    assert list(settings.partial_dir.iterdir()) == []

    _send(client, second["id"], 0, b"x" * 50)
    with session_scope() as session:
        session.get(UploadSession, second["id"]).created_at = utcnow() - timedelta(hours=25)
        retention.purge(session, settings)
    assert client.get(f"/api/uploads/sessions/{second['id']}").status_code == 404
    assert list(settings.partial_dir.iterdir()) == []
