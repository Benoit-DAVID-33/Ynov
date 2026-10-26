from fastapi.testclient import TestClient

from app import jobs, media
from app.config import get_settings
from app.db import session_scope
from app.models import User, utcnow
from tests.conftest import ADMIN_USERNAME, PASSWORD, USER_PASSWORD


def _login(admin_client, password=PASSWORD, username=ADMIN_USERNAME):
    return admin_client.post("/api/login", json={"username": username, "password": password})


def test_everything_but_the_login_page_requires_a_session(admin_client):
    assert "Connexion" in admin_client.get("/").text
    for path in ("/api/overview", "/api/jobs", "/api/logs", "/api/logs/api.log"):
        assert admin_client.get(path).status_code == 401
    assert admin_client.post("/api/logout").status_code == 401


def test_login_and_logout(admin_client):
    assert _login(admin_client, "wrong").status_code == 401
    assert admin_client.get("/api/overview").status_code == 401

    response = _login(admin_client)
    assert response.status_code == 200
    assert "httponly" in response.headers["set-cookie"].lower()
    assert admin_client.get("/api/overview").status_code == 200

    assert admin_client.post("/api/logout").status_code == 200
    assert admin_client.get("/api/overview").status_code == 401


def test_repeated_wrong_passwords_lock_the_login(admin_client):
    for _ in range(5):
        assert _login(admin_client, "wrong").status_code == 401
    assert _login(admin_client).status_code == 429


def test_overview_reports_services_and_usage(admin_client, submit, run_worker, monkeypatch):
    submit("a.mp4", "text")
    submit("b.wav", "text")
    submit("c.mp4", "video_embedded")
    run_worker()

    def broken(source, dest):
        raise media.MediaError("boom")

    monkeypatch.setattr(media, "extract_audio", broken)
    submit("d.wav", "subtitles")
    run_worker()
    submit("e.mp4", "subtitles")  # left in the queue
    with session_scope() as session:
        jobs.worker_heartbeat(session, "host:1")

    _login(admin_client)
    overview = admin_client.get("/api/overview").json()

    assert overview["database"]["up"] is True
    assert overview["api"] == {"up": False, "detail": "stub"}
    assert [(w["id"], w["up"]) for w in overview["workers"]] == [("host:1", True)]
    assert overview["disk"]["free_gb"] > 0

    stats = overview["stats"]
    assert stats["completed"] == {
        "total": 3,
        "by_output_type": {"text": 2, "video_embedded": 1},
        "by_input_kind": {"video": 2, "audio": 1},
    }
    assert stats["failed"] == {
        "total": 1, "by_output_type": {"subtitles": 1}, "by_input_kind": {"audio": 1}
    }
    assert stats["unfinished"] == {
        "total": 1, "by_output_type": {"subtitles": 1}, "by_input_kind": {"video": 1}
    }
    assert stats["avg_compute_s"] > 0
    assert stats["avg_realtime_factor"] < 1

    listed = admin_client.get("/api/jobs").json()
    assert len(listed) == 5
    done = admin_client.get("/api/jobs?status=done").json()
    assert {j["text"] for j in done} == {"Hello world. This is a fake transcription."}


def test_console_stays_usable_when_the_database_is_down(admin_client, settings, monkeypatch):
    (settings.logs_dir / "worker-host.log").write_text("worker crashed\n", encoding="utf-8")
    _login(admin_client)

    def unreachable(url):
        raise OSError("connection refused")

    monkeypatch.setattr("app.admin.init_db", unreachable)
    monkeypatch.setattr("app.admin._db_ready", False)

    # Already logged in: the session is still honoured, the database parts report the outage.
    overview = admin_client.get("/api/overview").json()
    assert overview["database"]["up"] is False
    assert overview["stats"] is None
    assert admin_client.get("/api/jobs").status_code == 503
    assert admin_client.get("/api/logs/worker-host.log").json()["lines"] == ["worker crashed"]

    # A new login needs the database: it says so instead of failing as a bad password.
    other = TestClient(admin_client.app)
    assert _login(other).status_code == 503
    assert other.get("/api/overview").status_code == 401


def test_only_administrators_can_log_in(admin_client, client):
    assert _login(admin_client, USER_PASSWORD, username="alice").status_code == 401
    assert admin_client.get("/api/overview").status_code == 401


def test_a_user_session_does_not_open_the_console(admin_client, client):
    token = client.cookies["session"]
    admin_client.cookies.set("admin_session", token)
    assert admin_client.get("/api/overview").status_code == 401


def test_first_administrator_is_created_from_the_settings_once(admin_client, settings, monkeypatch):
    assert _login(admin_client).status_code == 200
    with session_scope() as session:
        admins = session.query(User).filter_by(role="admin").all()
        assert [a.username for a in admins] == ["admin"]
        assert admins[0].password_hash != PASSWORD and admins[0].password_hash.startswith("$argon2")
        assert admins[0].last_login_at is not None

    # An administrator exists: other values of the settings create nothing more.
    monkeypatch.setenv("ADMIN_USERNAME", "second")
    get_settings.cache_clear()
    admin_client.post("/api/logout")
    monkeypatch.setattr("app.admin._db_ready", False)
    assert _login(admin_client).status_code == 200
    with session_scope() as session:
        assert session.query(User).filter_by(role="admin").count() == 1


def test_missing_admin_password_generates_one_printed_once(client, settings, capsys):
    from app import auth

    no_password = settings.model_copy(update={"admin_password": ""})
    with session_scope() as session:
        auth.ensure_admin(session, no_password)
    printed = capsys.readouterr().err
    password = printed.split("le mot de passe ")[1].split()[0]
    with session_scope() as session:
        assert auth.authenticate(session, "admin", password, role="admin") is not None
        auth.ensure_admin(session, no_password)  # an administrator exists: nothing more
    assert "mot de passe" not in capsys.readouterr().err


def test_disabling_the_administrator_ends_their_session(admin_client):
    _login(admin_client)
    assert admin_client.get("/api/overview").status_code == 200
    with session_scope() as session:
        session.query(User).filter_by(role="admin").one().disabled_at = utcnow()
    assert admin_client.get("/api/overview").status_code == 401
    assert _login(admin_client).status_code == 401


def test_logs_are_listed_and_tailed(admin_client, settings):
    _login(admin_client)
    lines = "".join(f"line {i}\n" for i in range(500))
    (settings.logs_dir / "worker-host.log").write_text(lines, encoding="utf-8")

    names = [f["name"] for f in admin_client.get("/api/logs").json()]
    assert "worker-host.log" in names and "admin.log" in names

    tail = admin_client.get("/api/logs/worker-host.log?lines=3").json()["lines"]
    assert tail == ["line 497", "line 498", "line 499"]
    assert admin_client.get("/api/logs/..%2Ftest.db").status_code == 404
    assert admin_client.get("/api/logs/missing.log").status_code == 404
