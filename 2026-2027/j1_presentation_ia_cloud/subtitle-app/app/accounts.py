"""Accounts seen from their owner and from the administrators: figures, history, changes.

Shared by the user API (app/account_api.py) and the admin console (app/admin.py).
"""

from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app import jobs, retention
from app.auth import ROLE_ADMIN, ROLE_USER
from app.config import Settings
from app.domain import JobStatus
from app.models import AuthSession, Job, Upload, UploadSession, User, UserIdentity, utcnow


class AccountConflict(Exception):
    """A change refused to keep the service usable (last administrator, own account...)."""


def _seconds(start: datetime | None, end: datetime | None) -> float | None:
    return (end - start).total_seconds() if start and end else None


def _results_bytes(settings: Settings, job_ids: list[str]) -> int:
    total = 0
    for job_id in job_ids:
        folder = settings.results_dir / job_id
        if folder.is_dir():
            total += sum(f.stat().st_size for f in folder.iterdir() if f.is_file())
    return total


def user_stats(session: Session, user_id: str, settings: Settings) -> dict:
    """What an account has done with the service, and what it currently keeps on disk."""
    by_status = dict(
        session.execute(
            select(Job.status, func.count())
            .join(Upload, Job.upload_id == Upload.id)
            .where(Upload.owner_id == user_id)
            .group_by(Job.status)
        ).all()
    )
    media_s, compute_s = session.execute(
        select(func.sum(Upload.duration_s), func.sum(Job.compute_s))
        .join(Upload, Job.upload_id == Upload.id)
        .where(Upload.owner_id == user_id, Job.status == JobStatus.DONE.value)
    ).one()
    uploads_total = session.scalar(select(func.count()).where(Upload.owner_id == user_id))
    kept = session.execute(
        select(Upload.id, Upload.size_bytes).where(Upload.owner_id == user_id, Upload.purged_at.is_(None))
    ).all()
    kept_jobs = list(session.scalars(select(Job.id).where(Job.upload_id.in_([u.id for u in kept]))))
    last_job_at = session.scalar(
        select(func.max(Job.created_at))
        .join(Upload, Job.upload_id == Upload.id)
        .where(Upload.owner_id == user_id)
    )
    return {
        "jobs_total": sum(by_status.values()),
        "jobs_done": by_status.get(JobStatus.DONE.value, 0),
        "jobs_failed": by_status.get(JobStatus.FAILED.value, 0),
        "jobs_cancelled": by_status.get(JobStatus.CANCELLED.value, 0),
        "jobs_active": sum(by_status.get(s, 0) for s in jobs.ACTIVE),
        "uploads_total": uploads_total,
        "media_s": media_s or 0.0,
        "compute_s": compute_s or 0.0,
        # Below 1 means faster than real time.
        "realtime_factor": compute_s / media_s if compute_s and media_s else None,
        "storage_bytes": sum(u.size_bytes for u in kept) + _results_bytes(settings, kept_jobs),
        "last_job_at": last_job_at,
    }


def history(session: Session, user_id: str, limit: int = 50, offset: int = 0) -> dict:
    """The jobs of an account, newest first, with their timings."""
    base = select(Job).join(Upload, Job.upload_id == Upload.id).where(Upload.owner_id == user_id)
    total = session.scalar(select(func.count()).select_from(base.subquery()))
    rows = session.scalars(
        base.order_by(Job.created_at.desc()).limit(min(max(limit, 1), 200)).offset(max(offset, 0))
    )
    return {"total": total, "jobs": [history_entry(job) for job in rows]}


def history_entry(job: Job) -> dict:
    upload = job.upload
    return {
        "id": job.id,
        "upload_id": upload.id,
        "filename": upload.filename,
        "input_kind": upload.kind,
        "size_bytes": upload.size_bytes,
        "duration_s": upload.duration_s,
        "output_type": job.output_type,
        "model": job.model,
        "target_language": job.target_language,
        "status": job.status,
        "progress": job.progress,
        "error": job.error,
        "created_at": job.created_at,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
        # Waiting in the queue, then computing, then from the request to the result.
        "wait_s": _seconds(job.created_at, job.started_at),
        "compute_s": job.compute_s,
        "total_s": _seconds(job.created_at, job.finished_at),
        # The result can still be downloaded (files are purged after a while).
        "available": bool(job.artifacts) and upload.purged_at is None,
    }


def profile(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "email": user.email,
        "role": user.role,
        "created_at": user.created_at,
        "last_login_at": user.last_login_at,
        "disabled": user.disabled_at is not None,
        "has_password": user.password_hash is not None,
        "identities": [
            {"provider": i.provider, "email": i.email, "created_at": i.created_at,
             "last_login_at": i.last_login_at}
            for i in user.identities
        ],
    }


def _other_active_admins(session: Session, user: User) -> int:
    return session.scalar(
        select(func.count()).where(
            User.role == ROLE_ADMIN, User.disabled_at.is_(None), User.id != user.id
        )
    )


def _check_admin_kept(session: Session, user: User, action: str) -> None:
    if user.role == ROLE_ADMIN and user.disabled_at is None and not _other_active_admins(session, user):
        raise AccountConflict(f"Impossible de {action} le dernier administrateur actif")


def set_role(session: Session, user: User, role: str, acting: User | None = None) -> None:
    if role not in (ROLE_USER, ROLE_ADMIN):
        raise ValueError("Rôle inconnu")
    if role == user.role:
        return
    if acting is not None and acting.id == user.id:
        raise AccountConflict("Vous ne pouvez pas changer votre propre rôle")
    if role != ROLE_ADMIN:
        _check_admin_kept(session, user, "rétrograder")
    user.role = role


def set_disabled(session: Session, user: User, disabled: bool, acting: User | None = None) -> None:
    if disabled == (user.disabled_at is not None):
        return
    if acting is not None and acting.id == user.id:
        raise AccountConflict("Vous ne pouvez pas désactiver votre propre compte")
    if disabled:
        _check_admin_kept(session, user, "désactiver")
        user.disabled_at = utcnow()
        session.query(AuthSession).filter(AuthSession.user_id == user.id).delete()
    else:
        user.disabled_at = None


def delete_account(session: Session, user: User, settings: Settings, acting: User | None = None) -> None:
    """Remove an account, its files and its history. Raises AccountConflict when refused."""
    if acting is not None and acting.id == user.id:
        raise AccountConflict("Supprimez votre propre compte depuis l'application, pas depuis la console")
    _check_admin_kept(session, user, "supprimer")
    uploads = list(session.scalars(select(Upload).where(Upload.owner_id == user.id)))
    for upload in uploads:
        for job_id in session.scalars(select(Job.id).where(Job.upload_id == upload.id)):
            jobs.cancel(session, job_id)
    for upload in uploads:
        if upload.purged_at is None and not retention.delete_files(session, upload, settings):
            raise AccountConflict("Un fichier est encore en cours de traitement : réessayez dans un instant")
    for leftover in session.scalars(
        select(UploadSession).where(UploadSession.owner_id == user.id)
    ):
        retention.drop_upload_session(session, leftover, settings)
    session.delete(user)
    session.flush()


def list_users(session: Session, query: str = "", limit: int = 200) -> list[dict]:
    """Accounts with their activity, for the console; `query` filters on name and e-mail."""
    activity = (
        select(
            Upload.owner_id.label("owner_id"),
            func.count(Job.id).label("jobs"),
            func.sum(Job.compute_s).label("compute_s"),
            func.max(Job.created_at).label("last_job_at"),
        )
        .join(Job, Job.upload_id == Upload.id)
        .group_by(Upload.owner_id)
        .subquery()
    )
    stmt = (
        select(User, activity.c.jobs, activity.c.compute_s, activity.c.last_job_at)
        .outerjoin(activity, activity.c.owner_id == User.id)
        .order_by(User.created_at.desc())
        .limit(min(max(limit, 1), 1000))
    )
    if query:
        pattern = f"%{query.strip().lower()}%"
        stmt = stmt.where(or_(
            User.username.like(pattern), func.lower(User.email).like(pattern),
            func.lower(User.display_name).like(pattern),
        ))
    providers: dict[str, list[str]] = {}
    for user_id, provider in session.execute(select(UserIdentity.user_id, UserIdentity.provider)):
        providers.setdefault(user_id, []).append(provider)
    return [
        {
            "id": user.id,
            "username": user.username,
            "display_name": user.display_name,
            "email": user.email,
            "role": user.role,
            "disabled": user.disabled_at is not None,
            "has_password": user.password_hash is not None,
            "providers": providers.get(user.id, []),
            "created_at": user.created_at,
            "last_login_at": user.last_login_at,
            "jobs": jobs_count or 0,
            "compute_s": compute_s or 0.0,
            "last_job_at": last_job_at,
        }
        for user, jobs_count, compute_s, last_job_at in session.execute(stmt)
    ]
