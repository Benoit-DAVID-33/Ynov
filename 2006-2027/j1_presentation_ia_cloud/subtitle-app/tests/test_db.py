import sqlite3

from app.db import init_db, session_scope
from app.models import Job


def test_database_from_an_earlier_version_is_upgraded_in_place(tmp_path):
    """A jobs table without the columns added later keeps its rows and gains the columns."""
    path = tmp_path / "old.db"
    old = sqlite3.connect(path)
    old.executescript(
        """
        CREATE TABLE uploads (id VARCHAR(32) PRIMARY KEY, filename VARCHAR(255), kind VARCHAR(16),
            path VARCHAR(1024), size_bytes INTEGER, duration_s FLOAT, created_at DATETIME);
        CREATE TABLE jobs (id VARCHAR(32) PRIMARY KEY, upload_id VARCHAR(32), output_type VARCHAR(32),
            model VARCHAR(64), status VARCHAR(16), attempts INTEGER, error TEXT, created_at DATETIME,
            started_at DATETIME, heartbeat_at DATETIME, finished_at DATETIME, compute_s FLOAT,
            language VARCHAR(8), text TEXT, segments JSON, artifacts JSON);
        INSERT INTO uploads VALUES ('u1', 'a.mp4', 'video', '/x', 1, 10.0, '2026-01-01 00:00:00');
        INSERT INTO jobs (id, upload_id, output_type, model, status, attempts, created_at, text)
            VALUES ('j1', 'u1', 'text', 'fake', 'done', 1, '2026-01-01 00:00:00', 'kept');
        """
    )
    old.close()

    init_db(f"sqlite:///{path}")
    init_db(f"sqlite:///{path}")  # idempotent

    with session_scope() as session:
        job = session.get(Job, "j1")
        assert (job.text, job.progress, job.stage, job.target_language) == ("kept", 0, None, None)
