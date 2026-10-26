import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.domain import JobStatus


# Python None is stored as SQL NULL (not as the JSON value null), so that
# "IS NULL" filters mean what they say on every database.
_Json = JSON(none_as_null=True)


def utcnow() -> datetime:
    # Naive UTC: SQLite does not keep timezone information.
    return datetime.now(timezone.utc).replace(tzinfo=None)


def new_id() -> str:
    return uuid.uuid4().hex


class Upload(Base):
    __tablename__ = "uploads"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    filename: Mapped[str] = mapped_column(String(255))
    kind: Mapped[str] = mapped_column(String(16))
    path: Mapped[str] = mapped_column(String(1024))
    size_bytes: Mapped[int]
    duration_s: Mapped[float | None]
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    # Anonymous browser identifier (cookie): scopes "my latest file".
    owner_id: Mapped[str | None] = mapped_column(String(32), index=True)
    # Set when the files were deleted by the retention policy; rows are kept
    # for the usage statistics.
    purged_at: Mapped[datetime | None]
    # Set when the visitor asked to delete the file; the files go as soon as
    # no worker is using them any more.
    delete_requested_at: Mapped[datetime | None]


class UploadSession(Base):
    """A resumable upload in progress; its bytes are in <storage>/partial/<id>.part."""

    __tablename__ = "upload_sessions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(String(32), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    size_bytes: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    upload_id: Mapped[str] = mapped_column(ForeignKey("uploads.id"), index=True)
    output_type: Mapped[str] = mapped_column(String(32))
    model: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default=JobStatus.QUEUED.value, index=True)
    attempts: Mapped[int] = mapped_column(default=0)
    error: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(default=utcnow, index=True)
    started_at: Mapped[datetime | None]
    heartbeat_at: Mapped[datetime | None]
    finished_at: Mapped[datetime | None]
    compute_s: Mapped[float | None]
    stage: Mapped[str | None] = mapped_column(String(32))
    progress: Mapped[int] = mapped_column(default=0)  # percent

    # Requested: translation target and output options (subtitle style).
    target_language: Mapped[str | None] = mapped_column(String(8))
    options: Mapped[dict | None] = mapped_column(_Json)

    # Result. `segments` is always the source-language transcription (reused by
    # later jobs on the same file); `text` is the delivered text.
    language: Mapped[str | None] = mapped_column(String(8))
    segments: Mapped[list | None] = mapped_column(_Json)
    translated_segments: Mapped[list | None] = mapped_column(_Json)
    # Delivered subtitles as corrected by the visitor; when set, the files are
    # built from them instead of the model output.
    edited_segments: Mapped[list | None] = mapped_column(_Json)
    text: Mapped[str | None] = mapped_column(Text)
    artifacts: Mapped[list | None] = mapped_column(_Json)

    upload: Mapped[Upload] = relationship(lazy="joined")


class Worker(Base):
    """Liveness of the worker processes, for the admin console."""

    __tablename__ = "workers"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    started_at: Mapped[datetime] = mapped_column(default=utcnow)
    heartbeat_at: Mapped[datetime] = mapped_column(default=utcnow)
    device: Mapped[str | None] = mapped_column(String(8))  # cpu | cuda
