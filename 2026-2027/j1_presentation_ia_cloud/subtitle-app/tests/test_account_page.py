from pathlib import Path

from fastapi.testclient import TestClient

from app import retention
from app.db import session_scope
from app.models import Upload, User
from tests.conftest import USER_PASSWORD


def test_account_shows_profile_and_figures(client, submit, run_worker):
    submit("one.mp4", "text")
    run_worker()
    account = client.get("/api/account").json()
    assert account["username"] == "alice"
    assert account["role"] == "user"
    assert account["has_password"] is True
    assert account["identities"] == []
    stats = account["stats"]
    assert (stats["jobs_total"], stats["jobs_done"], stats["uploads_total"]) == (1, 1, 1)
    assert stats["media_s"] == 10.0
    assert stats["storage_bytes"] > 0


def test_account_requires_login(client):
    assert TestClient(client.app).get("/api/account").status_code == 401


def test_profile_is_edited_field_by_field(client):
    response = client.patch("/api/account", json={"display_name": "  Alice   Martin ", "email": "Alice@Example.org"})
    assert response.status_code == 200
    assert (response.json()["display_name"], response.json()["email"]) == ("Alice Martin", "alice@example.org")
    # Only the fields sent change; an empty value clears.
    client.patch("/api/account", json={"email": ""})
    account = client.get("/api/account").json()
    assert (account["display_name"], account["email"]) == ("Alice Martin", None)


def test_username_and_role_cannot_be_changed_by_the_user(client):
    client.patch("/api/account", json={"username": "root", "role": "admin"})
    assert client.get("/api/auth/me").json() == {"username": "alice", "role": "user"}


def test_invalid_profile_values_are_refused(client):
    assert client.patch("/api/account", json={"email": "not-an-address"}).status_code == 422
    assert client.patch("/api/account", json={"display_name": "x" * 65}).status_code == 422


def test_password_change_needs_the_current_one_and_logs_out_other_browsers(client):
    other = TestClient(client.app)
    other.post("/api/auth/login", json={"username": "alice", "password": USER_PASSWORD})
    assert other.get("/api/auth/me").status_code == 200

    wrong = client.post("/api/account/password", json={"current_password": "nope", "new_password": "new password"})
    assert wrong.status_code == 403
    response = client.post(
        "/api/account/password", json={"current_password": USER_PASSWORD, "new_password": "new password"}
    )
    assert response.status_code == 200
    assert client.get("/api/auth/me").status_code == 200  # this browser stays logged in
    assert other.get("/api/auth/me").status_code == 401
    login = TestClient(client.app).post("/api/auth/login", json={"username": "alice", "password": "new password"})
    assert login.status_code == 200


def test_too_short_new_password_is_refused(client):
    response = client.post("/api/account/password", json={"current_password": USER_PASSWORD, "new_password": "short"})
    assert response.status_code == 422


def test_history_lists_own_jobs_with_timings(client, stranger, submit, run_worker, settings):
    submit("first.mp4", "text")
    run_worker()
    submit("second.mp4", "subtitles", translate_to="fr")
    stranger.post("/api/uploads", files={"file": ("theirs.mp4", b"data")})
    run_worker()
    with session_scope() as session:
        retention.purge(session, settings)

    history = client.get("/api/account/jobs").json()
    assert history["total"] == 2
    latest, oldest = history["jobs"]
    assert (latest["filename"], latest["target_language"], latest["status"]) == ("second.mp4", "fr", "done")
    assert latest["available"] is True
    # The first file was replaced by the second one: its result is gone, its history stays.
    assert (oldest["filename"], oldest["available"]) == ("first.mp4", False)
    for field in ("wait_s", "compute_s", "total_s", "duration_s", "created_at", "finished_at"):
        assert latest[field] is not None, field
    assert client.get("/api/account/jobs?limit=1&offset=1").json()["jobs"][0]["filename"] == "first.mp4"


def test_deleting_the_account_removes_files_and_logs_out(client, submit, run_worker, settings):
    job = submit("mine.mp4", "subtitles")
    run_worker()
    with session_scope() as session:
        upload_path = Path(session.get(Upload, job["upload_id"]).path)
    assert upload_path.exists()

    refused = client.request("DELETE", "/api/account", json={"confirm": "bob", "password": USER_PASSWORD})
    assert refused.status_code == 422
    wrong = client.request("DELETE", "/api/account", json={"confirm": "alice", "password": "nope"})
    assert wrong.status_code == 403

    response = client.request("DELETE", "/api/account", json={"confirm": "alice", "password": USER_PASSWORD})
    assert response.status_code == 204
    assert not upload_path.exists()
    assert not (settings.results_dir / job["id"]).exists()
    assert client.get("/api/auth/me").status_code == 401
    with session_scope() as session:
        assert session.query(User).filter_by(username="alice").count() == 0
        assert session.query(Upload).count() == 0


def test_web_pages_are_revalidated_on_every_load(client):
    for path in ("/", "/app.js", "/account.html", "/shared/style.css"):
        assert client.get(path).headers["cache-control"] == "no-cache", path
    assert "no-cache" not in client.get("/api/config").headers.get("cache-control", "")
