from datetime import timedelta

from app import jobs
from app.db import session_scope
from app.domain import JobStatus
from app.models import Job, utcnow


def test_jobs_are_claimed_once_in_submission_order(client, submit):
    first, second = submit(), submit()
    with session_scope() as session:
        assert jobs.claim_next(session) == first["id"]
        assert jobs.claim_next(session) == second["id"]
        assert jobs.claim_next(session) is None
        assert session.get(Job, first["id"]).attempts == 1


def _interrupt(job_id: str, attempts: int) -> None:
    """Simulate a worker that died a while ago in the middle of a job."""
    with session_scope() as session:
        job = session.get(Job, job_id)
        job.status = JobStatus.PROCESSING.value
        job.attempts = attempts
        job.heartbeat_at = utcnow() - timedelta(minutes=10)


def test_interrupted_job_is_requeued_then_completes(client, submit, run_worker, settings):
    job = submit()
    _interrupt(job["id"], attempts=1)
    with session_scope() as session:
        assert jobs.requeue_stale(session, settings.stale_after_s, settings.max_attempts) == 1
    run_worker()
    assert client.get(f"/api/jobs/{job['id']}").json()["status"] == "done"


def test_job_interrupted_too_many_times_fails(client, submit, settings):
    job = submit()
    _interrupt(job["id"], attempts=settings.max_attempts)
    with session_scope() as session:
        jobs.requeue_stale(session, settings.stale_after_s, settings.max_attempts)
    failed = client.get(f"/api/jobs/{job['id']}").json()
    assert failed["status"] == "failed"
    assert "abandonné" in failed["error"]


def test_running_job_with_recent_heartbeat_is_left_alone(client, submit, settings):
    submit()
    with session_scope() as session:
        jobs.claim_next(session)
        assert jobs.requeue_stale(session, settings.stale_after_s, settings.max_attempts) == 0
