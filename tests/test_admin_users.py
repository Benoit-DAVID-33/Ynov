import pytest
from fastapi.testclient import TestClient

from app.db import session_scope
from app.models import Upload, User
from tests.conftest import ADMIN_USERNAME, PASSWORD, USER_PASSWORD


@pytest.fixture
def admin(admin_client):
    assert admin_client.post(
        "/api/login", json={"username": ADMIN_USERNAME, "password": PASSWORD}
    ).status_code == 200
    return admin_client


def _users(admin, q=""):
    return {u["username"]: u for u in admin.get(f"/api/users?q={q}").json()}


def _id(admin, username):
    return _users(admin)[username]["id"]


def test_account_pages_require_an_admin_session(admin_client):
    for method, path in [("GET", "/api/users"), ("POST", "/api/users"), ("GET", "/api/metrics"),
                         ("PATCH", "/api/users/x"), ("DELETE", "/api/users/x")]:
        assert admin_client.request(method, path, json={}).status_code == 401, path


def test_user_session_does_not_open_the_console(client, admin_client):
    # Same cookie name on another port would not be sent anyway; a user token is refused too.
    token = client.cookies["session"]
    admin_client.cookies.set("admin_session", token)
    assert admin_client.get("/api/users").status_code == 401


def test_users_are_listed_with_their_activity(admin, client, submit, run_worker):
    submit("a.mp4", "text")
    run_worker()
    users = _users(admin)
    assert set(users) == {"alice", "admin"}
    assert users["alice"]["jobs"] == 1 and users["alice"]["role"] == "user"
    assert users["alice"]["has_password"] is True
    client.patch("/api/account", json={"email": "alice@example.org"})
    assert set(_users(admin, "example")) == {"alice"}


def test_user_detail_has_history_and_figures(admin, submit, run_worker):
    submit("a.mp4", "text")
    run_worker()
    detail = admin.get(f"/api/users/{_id(admin, 'alice')}").json()
    assert detail["stats"]["jobs_done"] == 1
    assert detail["history"]["jobs"][0]["filename"] == "a.mp4"
    assert admin.get("/api/users/unknown").status_code == 404


def test_admin_creates_an_account(admin, client):
    response = admin.post("/api/users", json={"username": "Bob", "password": USER_PASSWORD,
                                              "email": "bob@example.org"})
    assert response.status_code == 201
    assert (response.json()["username"], response.json()["email"]) == ("bob", "bob@example.org")
    assert admin.post("/api/users", json={"username": "bob", "password": USER_PASSWORD}).status_code == 409
    assert admin.post("/api/users", json={"username": "x", "password": USER_PASSWORD}).status_code == 422
    assert admin.post("/api/users", json={"username": "carl", "password": USER_PASSWORD,
                                          "role": "root"}).status_code == 422
    login = TestClient(client.app).post("/api/auth/login", json={"username": "bob", "password": USER_PASSWORD})
    assert login.status_code == 200


def test_disabling_an_account_logs_it_out(admin, client):
    alice = _id(admin, "alice")
    assert admin.patch(f"/api/users/{alice}", json={"disabled": True}).json()["disabled"] is True
    assert client.get("/api/auth/me").status_code == 401
    admin.patch(f"/api/users/{alice}", json={"disabled": False})
    relogin = client.post("/api/auth/login", json={"username": "alice", "password": USER_PASSWORD})
    assert relogin.status_code == 200


def test_promoted_user_can_open_the_console(admin, client, admin_client):
    alice = _id(admin, "alice")
    assert admin.patch(f"/api/users/{alice}", json={"role": "admin"}).json()["role"] == "admin"
    console = TestClient(admin_client.app)
    response = console.post("/api/login", json={"username": "alice", "password": USER_PASSWORD})
    assert response.status_code == 200


def test_admin_cannot_lock_themselves_out(admin):
    me = _id(admin, "admin")
    assert admin.patch(f"/api/users/{me}", json={"role": "user"}).status_code == 409
    assert admin.patch(f"/api/users/{me}", json={"disabled": True}).status_code == 409
    assert admin.delete(f"/api/users/{me}").status_code == 409
    assert admin.get("/api/me").json()["username"] == "admin"


def test_last_active_admin_is_kept(admin, admin_client):
    alice = _id(admin, "alice")
    admin.patch(f"/api/users/{alice}", json={"role": "admin"})
    # alice, now admin, demotes the original admin: allowed, alice remains.
    other = TestClient(admin_client.app)
    other.post("/api/login", json={"username": "alice", "password": USER_PASSWORD})
    assert other.patch(f"/api/users/{_id(admin, 'admin')}", json={"role": "user"}).status_code == 200
    # Now alice is the last administrator: nobody can remove her rights.
    with session_scope() as session:
        assert session.query(User).filter_by(role="admin").count() == 1


def test_password_reset_ends_sessions(admin, client):
    alice = _id(admin, "alice")
    assert admin.post(f"/api/users/{alice}/password", json={"new_password": "short"}).status_code == 422
    assert admin.post(f"/api/users/{alice}/password", json={"new_password": "brand new pw"}).status_code == 200
    assert client.get("/api/auth/me").status_code == 401
    assert client.post("/api/auth/login", json={"username": "alice", "password": "brand new pw"}).status_code == 200


def test_deleting_an_account_removes_its_files(admin, submit, run_worker, settings):
    job = submit("a.mp4", "subtitles")
    run_worker()
    assert admin.delete(f"/api/users/{_id(admin, 'alice')}").status_code == 204
    assert "alice" not in _users(admin)
    assert not (settings.results_dir / job["id"]).exists()
    with session_scope() as session:
        assert session.query(Upload).count() == 0


def test_jobs_show_their_owner_and_filter_by_user(admin, client, stranger, submit):
    submit("mine.mp4")
    stranger.post("/api/jobs", json={
        "upload_id": stranger.post("/api/uploads", files={"file": ("theirs.mp4", b"data")}).json()["id"],
        "output_type": "text",
    })
    jobs = admin.get("/api/jobs").json()
    assert {j["username"] for j in jobs} == {"alice", "user2"}
    only_alice = admin.get(f"/api/jobs?user_id={_id(admin, 'alice')}").json()
    assert [j["filename"] for j in only_alice] == ["mine.mp4"]


def test_metrics_cover_activity_users_and_models(admin, client, submit, run_worker):
    submit("a.mp4", "text")
    submit("b.mp4", "subtitles", translate_to="fr")
    run_worker()
    submit("c.mp4", "text")  # still queued
    metrics = admin.get("/api/metrics?days=7").json()

    assert metrics["days"] == 7 and len(metrics["series"]) == 7
    today = metrics["series"][-1]
    assert (today["jobs"], today["done"], today["failed"]) == (3, 2, 0)
    assert today["media_s"] == 20.0 and today["active_users"] == 1
    assert sum(day["new_users"] for day in metrics["series"]) == 2  # admin + alice
    assert metrics["users"]["total"] == 2 and metrics["users"]["active_7d"] == 1
    assert metrics["jobs"]["by_status"] == {"done": 2, "queued": 1}
    assert metrics["jobs"]["success_rate"] == 1.0
    assert metrics["jobs"]["compute_s"]["avg"] is not None
    assert [m["model"] for m in metrics["by_model"]] == ["fake"]
    assert {(row["language"], row["jobs"]) for row in metrics["by_language"]} == {(None, 2), ("fr", 1)}
    assert metrics["storage"]["uploads"] >= 1
