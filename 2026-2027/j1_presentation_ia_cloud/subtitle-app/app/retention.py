"""Automatic deletion of uploaded and produced files.

Each user keeps the files of their latest upload only. Database rows are
kept: the admin statistics and the text of past answers stay available.
"""

import logging
import shutil
from datetime import timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import jobs
from app.config import Settings
from app.models import Job, Upload, UploadSession, utcnow

log = logging.getLogger("retention")


def delete_files(session: Session, upload: Upload, settings: Settings) -> bool:
    """Delete the uploaded file and every result built from it.

    Returns False when a file is still in use (a worker that has not noticed a
    cancellation yet, on Windows): the next purge tries again.
    """
    try:
        Path(upload.path).unlink(missing_ok=True)
        for job in session.scalars(select(Job).where(Job.upload_id == upload.id)):
            folder = settings.results_dir / job.id
            if folder.exists():
                shutil.rmtree(folder)
            job.artifacts = []
    except OSError:
        return False
    upload.purged_at = utcnow()
    return True


def drop_upload_session(session: Session, upload_session: UploadSession, settings: Settings) -> None:
    """Forget an unfinished resumable upload and the bytes received so far."""
    try:
        (settings.partial_dir / f"{upload_session.id}.part").unlink(missing_ok=True)
    except OSError:
        return  # a chunk is being written right now: left for the next pass
    session.delete(upload_session)


def purge(session: Session, settings: Settings) -> int:
    """Delete the files of superseded, expired or deleted uploads. Returns how many uploads."""
    abandoned_before = utcnow() - timedelta(hours=settings.upload_session_hours)
    for abandoned in session.scalars(
        select(UploadSession).where(UploadSession.created_at < abandoned_before)
    ):
        drop_upload_session(session, abandoned, settings)

    uploads = session.scalars(
        select(Upload).where(Upload.purged_at.is_(None)).order_by(Upload.created_at.desc())
    ).all()
    active = set(session.scalars(select(Job.upload_id).where(Job.status.in_(jobs.ACTIVE))))
    expires_before = (
        utcnow() - timedelta(days=settings.retention_days) if settings.retention_days > 0 else None
    )

    purged = 0
    owners_seen = set()
    for upload in uploads:  # newest first
        if upload.delete_requested_at is not None:
            reason = "deleted by its owner"
        else:
            is_latest = upload.owner_id not in owners_seen
            owners_seen.add(upload.owner_id)
            expired = expires_before is not None and upload.created_at < expires_before
            if upload.id in active or (is_latest and not expired):
                continue
            reason = "expired" if expired else "superseded"

        if delete_files(session, upload, settings):
            purged += 1
            log.info("purged files of upload %s (%s)", upload.id, reason)
    return purged
