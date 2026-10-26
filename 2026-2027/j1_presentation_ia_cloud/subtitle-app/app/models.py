import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, BigInteger, CheckConstraint, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.domain import JobStatus


# Python None is stored as SQL NULL (not as the JSON value null), so that
# "IS NULL" filters mean what they say on every database.
_Json = JSON(none_as_null=True)


def utcnow() -> datetime:
    # Naive UTC: every timestamp of the schema is stored without timezone.
    return datetime.now(timezone.utc).replace(tzinfo=None)


def new_id() -> str:
    return uuid.uuid4().hex


class User(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("role IN ('user', 'admin')", name="ck_users_role"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    # Lowercase, so that "Alice" and "alice" are the same account.
    username: Mapped[str] = mapped_column(String(32), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(16), default="user")
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    last_login_at: Mapped[datetime | None]
    # A disabled account cannot log in and its sessions stop working.
    disabled_at: Mapped[datetime | None]


class AuthSession(Base):
    """A login. Only the SHA-256 of the cookie token is kept: a database leak gives no session."""

    __tablename__ = "auth_sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(index=True)


class Upload(Base):
    """An input file. Its bytes are on disk at `path`; the database only holds the metadata."""

    __tablename__ = "uploads"
    __table_args__ = (Index("ix_uploads_owner_id_created_at", "owner_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    filename: Mapped[str] = mapped_column(String(255))
    kind: Mapped[str] = mapped_column(String(16))
    path: Mapped[str] = mapped_column(String(1024))
    size_bytes: Mapped[int] = mapped_column(BigInteger)  # up to 2 GiB and more: over INTEGER
    duration_s: Mapped[float | None]
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    # The account the file belongs to; its jobs and result files follow.
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    # Set when the files were deleted by the retention policy; rows are kept
    # for the usage statistics.
    purged_at: Mapped[datetime | None]
    # Set when the user asked to delete the file; the files go as soon as
    # no worker is using them any more.
    delete_requested_at: Mapped[datetime | None]


class UploadSession(Base):
    """A resumable upload in progress; its bytes are in <storage>/partial/<id>.part."""

    __tablename__ = "upload_sessions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    upload_id: Mapped[str] = mapped_column(ForeignKey("uploads.id", ondelete="CASCADE"), index=True)
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
