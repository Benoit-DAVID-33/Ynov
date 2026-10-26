from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app import auth, users
from app.db import session_scope
from app.models import AuthSession, Job, Upload, User, utcnow
from tests.conftest import USER_PASSWORD


def _register(client, username="bob", password=USER_PASSWORD):
    return client.post("/api/auth/register", json={"username": username, "password": password})


def _login(client, username="alice", password=USER_PASSWORD):
    return client.post("/api/auth/login", json={"username": username, "password": password})


@pytest.fixture
def anonymous(client):
    """A browser with no account, on the same application."""
    return TestClient(client.app)


# --- registration -----------------------------------------------------------

def test_anyone_can_create_an_account_and_is_logged_in_at_once(anonymous):
    response = _register(anonymous)
    assert response.status_code == 201
    assert response.json() == {"username": "bob", "role": "user"}
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie
    assert anonymous.get("/api/auth/me").json() == {"username": "bob", "role": "user"}


def test_password_is_stored_hashed_and_the_session_token_only_as_a_digest(anonymous):
    token = _register(anonymous, password="plain text secret").cookies["session"]
    with session_scope() as session:
        user = session.query(User).filter_by(username="bob").one()
        assert "plain text secret" not in user.password_hash
        assert user.password_hash.startswith("$argon2")
        assert user.role == "user"
        assert [s.id for s in session.query(AuthSession).filter_by(user_id=user.id)] != [token]


def test_usernames_are_case_insensitive_and_unique(anonymous):
    assert _register(anonymous, "Carol").json()["username"] == "carol"
    taken = _register(TestClient(anonymous.app), "CAROL")
    assert taken.status_code == 409
    assert _register(TestClient(anonymous.app), "alice").status_code == 409


@pytest.mark.parametrize("username", ["ab", "a" * 33, "with space", "-leading", "é-accent", ""])
def test_invalid_usernames_are_refused(anonymous, username):
    assert _register(anonymous, username).status_code == 422


@pytest.mark.parametrize("password", ["short", "x" * 129, ""])
def test_invalid_passwords_are_refused(anonymous, password):
    assert _register(anonymous, password=password).status_code == 422


def test_account_creation_is_rate_limited_per_address(anonymous, settings):
    # alice already used one attempt of this address.
    for i in range(settings.max_registrations_per_hour - 1):
        assert _register(TestClient(anonymous.app), f"user-{i}").status_code == 201
    assert _register(TestClient(anonymous.app), "one-too-many").status_code == 429


# --- login and logout -------------------------------------------------------

def test_login_logout(anonymous):
    assert _login(anonymous, password="wrong password").status_code == 401
    assert _login(anonymous, "nobody").status_code == 401  # same answer for an unknown name
    assert anonymous.get("/api/auth/me").status_code == 401

    assert _login(anonymous, "ALICE ").status_code == 200
    assert anonymous.get("/api/auth/me").json()["username"] == "alice"
    with session_scope() as session:
        assert session.query(User).filter_by(username="alice").one().last_login_at is not None

    assert anonymous.post("/api/auth/logout").status_code == 200
    assert anonymous.get("/api/auth/me").status_code == 401


def test_logout_ends_the_session_on_the_server_not_only_in_the_browser(client):
    token = client.cookies["session"]
    client.post("/api/auth/logout")
    stolen = TestClient(client.app)
    stolen.cookies.set("session", token)
    assert stolen.get("/api/auth/me").status_code == 401


def test_repeated_wrong_passwords_lock_the_login(anonymous):
    for _ in range(5):
        assert _login(anonymous, password="wrong password").status_code == 401
    assert _login(anonymous).status_code == 429


def test_expired_session_is_refused_and_purged(client, settings):
    with session_scope() as session:
        session.query(AuthSession).update({"expires_at": utcnow() - timedelta(seconds=1)})
    assert client.get("/api/auth/me").status_code == 401
    with session_scope() as session:
        assert auth.purge_expired_sessions(session) == 1


def test_disabled_account_cannot_log_in_and_loses_its_session(client, anonymous):
    with session_scope() as session:
        session.query(User).filter_by(username="alice").one().disabled_at = utcnow()
    assert client.get("/api/auth/me").status_code == 401
    assert _login(anonymous).status_code == 401


def test_forged_cookies_are_refused(anonymous):
    for value in ("", "x", "a" * 43, "0" * 64):
        anonymous.cookies.set("session", value)
        assert anonymous.get("/api/auth/me").status_code == 401


# --- what needs an account --------------------------------------------------

def test_everything_but_the_public_pages_requires_an_account(anonymous):
    protected = [
        ("get", "/api/auth/me"), ("get", "/api/uploads/last"), ("post", "/api/uploads"),
        ("post", "/api/uploads/sessions"), ("post", "/api/jobs"), ("get", "/api/jobs/x"),
        ("get", "/api/jobs/x/download"), ("delete", "/api/uploads/x"),
    ]
    for method, path in protected:
        assert getattr(anonymous, method)(path).status_code == 401, path
    for path in ("/api/health", "/api/config", "/api/queue", "/login.html", "/register.html"):
        assert anonymous.get(path).status_code == 200, path


def test_a_new_account_starts_empty_and_work_follows_the_account(client, submit, run_worker):
    job = submit("clip.mp4", "subtitles")
    run_worker()
    other_browser = TestClient(client.app)
    assert _login(other_browser).status_code == 200  # alice again, from another browser
    assert other_browser.get(f"/api/jobs/{job['id']}").status_code == 200
    assert other_browser.get("/api/uploads/last").json()["upload"]["filename"] == "clip.mp4"


def test_uploads_are_recorded_against_the_account(client, submit):
    submit("clip.mp4")
    with session_scope() as session:
        alice = session.query(User).filter_by(username="alice").one()
        assert [u.owner_id for u in session.query(Upload)] == [alice.id]


def test_deleting_an_account_removes_its_rows(client, submit, run_worker):
    submit("clip.mp4")
    run_worker()
    with session_scope() as session:
        session.delete(session.query(User).filter_by(username="alice").one())
    with session_scope() as session:
        assert (session.query(Upload).count(), session.query(Job).count()) == (0, 0)
        assert session.query(AuthSession).count() == 0


# --- command line -----------------------------------------------------------

def test_command_line_creates_lists_and_disables_accounts(settings, monkeypatch, capsys):
    monkeypatch.setattr(users, "_ask_password", lambda: "a good password")
    users.main(["create", "root", "--admin"])
    users.main(["create", "dave"])
    users.main(["disable", "dave"])
    capsys.readouterr()
    users.main(["list"])
    listing = capsys.readouterr().out
    assert "root\tadmin\tactif" in listing and "dave\tuser\tdésactivé" in listing

    with pytest.raises(SystemExit):
        users.main(["create", "dave"])  # already exists
    with session_scope() as session:
        assert auth.authenticate(session, "root", "a good password", role="admin") is not None
        assert auth.authenticate(session, "dave", "a good password") is None  # disabled
    users.main(["enable", "dave"])
    with session_scope() as session:
        assert auth.authenticate(session, "dave", "a good password") is not None


def test_changing_a_password_ends_the_sessions_of_the_account(client, settings, monkeypatch):
    monkeypatch.setattr(users, "_ask_password", lambda: "brand new password")
    users.main(["passwd", "alice"])
    assert client.get("/api/auth/me").status_code == 401
    assert _login(TestClient(client.app), password="brand new password").status_code == 200
