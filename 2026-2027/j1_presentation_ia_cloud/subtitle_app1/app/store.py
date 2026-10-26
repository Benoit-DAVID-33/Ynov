import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

QUEUED, PROCESSING, DONE, FAILED, UPLOADED = "queued", "processing", "done", "failed", "uploaded"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    input_kind TEXT NOT NULL,
    input_path TEXT NOT NULL,
    output_format TEXT,
    status TEXT NOT NULL,
    error TEXT,
    result_path TEXT,
    result_text TEXT,
    media_seconds REAL,
    processing_seconds REAL,
    created_at TEXT NOT NULL,
    finished_at TEXT
)
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class JobStore:
    """SQLite-backed job repository (one short-lived connection per call: thread safe)."""

    def __init__(self, db_path: Path):
        self._db_path = db_path
        with self._connect() as conn:
            conn.execute(_SCHEMA)

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            with conn:  # commit / rollback
                yield conn
        finally:
            conn.close()

    def create(self, job_id: str, filename: str, input_kind: str, input_path: Path) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO jobs (id, filename, input_kind, input_path, status, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (job_id, filename, input_kind, str(input_path), UPLOADED, _now()),
            )

    def get(self, job_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return dict(row) if row else None

    def queue(self, job_id: str, output_format: str) -> None:
        self._update(job_id, status=QUEUED, output_format=output_format, error=None)

    def mark_processing(self, job_id: str) -> None:
        self._update(job_id, status=PROCESSING)

    def mark_done(self, job_id: str, result_path: Path, result_text: str,
                  media_seconds: float, processing_seconds: float) -> None:
        self._update(job_id, status=DONE, result_path=str(result_path), result_text=result_text,
                     media_seconds=media_seconds, processing_seconds=processing_seconds,
                     finished_at=_now())

    def mark_failed(self, job_id: str, error: str) -> None:
        self._update(job_id, status=FAILED, error=error, finished_at=_now())

    def list_unfinished(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM jobs WHERE status IN (?, ?) ORDER BY created_at", (QUEUED, PROCESSING)
            ).fetchall()
        return [dict(r) for r in rows]

    def list_responses(self, limit: int = 50) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, filename, output_format, finished_at, result_text FROM jobs"
                " WHERE status = ? ORDER BY finished_at DESC LIMIT ?", (DONE, limit)
            ).fetchall()
        return [dict(r) for r in rows]

    def stats(self) -> dict:
        with self._connect() as conn:
            def by_format(statuses: tuple[str, ...]) -> dict[str, int]:
                marks = ",".join("?" * len(statuses))
                rows = conn.execute(
                    f"SELECT output_format, COUNT(*) AS n FROM jobs WHERE status IN ({marks})"
                    " GROUP BY output_format", statuses
                ).fetchall()
                return {r["output_format"]: r["n"] for r in rows}

            done = conn.execute(
                "SELECT COUNT(*) AS n, AVG(processing_seconds) AS avg_s,"
                " SUM(processing_seconds) / NULLIF(SUM(media_seconds), 0) AS rtf"
                " FROM jobs WHERE status = ?", (DONE,)
            ).fetchone()
            done_by_type = by_format((DONE,))
            unfinished_by_type = by_format((QUEUED, PROCESSING))
            failed_by_type = by_format((FAILED,))
        return {
            "inferences_done": done["n"],
            "inferences_done_by_type": done_by_type,
            "avg_processing_seconds": done["avg_s"],
            # processing time / media duration; the requirement is < 1
            "avg_realtime_factor": done["rtf"],
            "unfinished": sum(unfinished_by_type.values()),
            "unfinished_by_type": unfinished_by_type,
            "failed": sum(failed_by_type.values()),
            "failed_by_type": failed_by_type,
        }

    def _update(self, job_id: str, **fields) -> None:
        cols = ", ".join(f"{k} = ?" for k in fields)
        with self._connect() as conn:
            conn.execute(f"UPDATE jobs SET {cols} WHERE id = ?", (*fields.values(), job_id))
