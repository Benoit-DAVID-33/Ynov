"""Initial schema: accounts, sessions, uploads, jobs, workers.

Revision ID: 0001
Revises:
Create Date: 2026-10-26
"""
import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Tables of the versions that predate accounts (files tied to an anonymous cookie, no
    # migrations). Their uploads belong to nobody and are abandoned.
    for legacy in ("jobs", "upload_sessions", "uploads", "workers"):
        op.execute(f"DROP TABLE IF EXISTS {legacy} CASCADE")

    op.create_table(
        "users",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("username", sa.String(32), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_login_at", sa.DateTime()),
        sa.Column("disabled_at", sa.DateTime()),
        sa.UniqueConstraint("username"),
        sa.CheckConstraint("role IN ('user', 'admin')", name="ck_users_role"),
    )

    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(32), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"])
    op.create_index("ix_auth_sessions_expires_at", "auth_sessions", ["expires_at"])

    op.create_table(
        "uploads",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("path", sa.String(1024), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("duration_s", sa.Float()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("owner_id", sa.String(32), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("purged_at", sa.DateTime()),
        sa.Column("delete_requested_at", sa.DateTime()),
    )
    op.create_index("ix_uploads_owner_id_created_at", "uploads", ["owner_id", "created_at"])

    op.create_table(
        "upload_sessions",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("owner_id", sa.String(32), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_upload_sessions_owner_id", "upload_sessions", ["owner_id"])

    op.create_table(
        "jobs",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("upload_id", sa.String(32), sa.ForeignKey("uploads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("output_type", sa.String(32), nullable=False),
        sa.Column("model", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("error", sa.Text()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime()),
        sa.Column("heartbeat_at", sa.DateTime()),
        sa.Column("finished_at", sa.DateTime()),
        sa.Column("compute_s", sa.Float()),
        sa.Column("stage", sa.String(32)),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("target_language", sa.String(8)),
        sa.Column("options", sa.JSON()),
        sa.Column("language", sa.String(8)),
        sa.Column("segments", sa.JSON()),
        sa.Column("translated_segments", sa.JSON()),
        sa.Column("edited_segments", sa.JSON()),
        sa.Column("text", sa.Text()),
        sa.Column("artifacts", sa.JSON()),
    )
    op.create_index("ix_jobs_upload_id", "jobs", ["upload_id"])
    op.create_index("ix_jobs_status", "jobs", ["status"])
    op.create_index("ix_jobs_created_at", "jobs", ["created_at"])

    op.create_table(
        "workers",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("heartbeat_at", sa.DateTime(), nullable=False),
        sa.Column("device", sa.String(8)),
    )


def downgrade() -> None:
    for table in ("workers", "jobs", "upload_sessions", "uploads", "auth_sessions", "users"):
        op.drop_table(table)
