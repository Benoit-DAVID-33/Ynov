from collections import Counter
from datetime import date, timedelta

from sqlalchemy import Date, cast, distinct, func, select
from sqlalchemy.orm import Session

from app.domain import JobStatus
from app.models import Job, Upload, User, UserIdentity, utcnow

_PENDING = {JobStatus.QUEUED.value, JobStatus.PROCESSING.value}


def usage_stats(session: Session) -> dict:
    rows = session.execute(
        select(
            Upload.kind,
            Job.output_type,
            Job.status,
            func.count(),
            func.sum(Job.compute_s),
            func.sum(Upload.duration_s),
        )
        .join(Upload, Job.upload_id == Upload.id)
        .group_by(Upload.kind, Job.output_type, Job.status)
    ).all()

    groups = {
        "completed": lambda status: status == JobStatus.DONE.value,
        "unfinished": lambda status: status in _PENDING,
        "failed": lambda status: status == JobStatus.FAILED.value,
        "cancelled": lambda status: status == JobStatus.CANCELLED.value,
    }
    stats: dict = {
        name: {"total": 0, "by_output_type": Counter(), "by_input_kind": Counter()}
        for name in groups
    }
    compute_total = media_total = 0.0
    for kind, output_type, status, count, compute_s, duration_s in rows:
        for name, matches in groups.items():
            if matches(status):
                stats[name]["total"] += count
                stats[name]["by_output_type"][output_type] += count
                stats[name]["by_input_kind"][kind] += count
        if status == JobStatus.DONE.value:
            compute_total += compute_s or 0.0
            media_total += duration_s or 0.0

    done = stats["completed"]["total"]
    stats["avg_compute_s"] = compute_total / done if done else None
    # Below 1 means faster than real time.
    stats["avg_realtime_factor"] = compute_total / media_total if media_total else None
    return stats


def _day_series(rows, start: date, days: int, fields: tuple[str, ...]) -> list[dict]:
    """One entry per day from `start`, zero-filled: a chart needs the empty days too."""
    found = {row[0]: row[1:] for row in rows}
    series = []
    for offset in range(days):
        day = start + timedelta(days=offset)
        values = found.get(day, (0,) * len(fields))
        series.append({"day": day.isoformat(), **{f: v or 0 for f, v in zip(fields, values)}})
    return series


def _avg_p95(session: Session, expression, *where) -> dict:
    avg, p95 = session.execute(
        select(func.avg(expression), func.percentile_cont(0.95).within_group(expression)).where(*where)
    ).one()
    return {"avg": float(avg) if avg is not None else None, "p95": float(p95) if p95 is not None else None}


def metrics(session: Session, days: int = 30) -> dict:
    """Activity of the last `days` days, for the admin dashboard."""
    days = min(max(days, 1), 365)
    now = utcnow()
    start = (now - timedelta(days=days - 1)).date()
    since = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days - 1)
    job_day = cast(Job.created_at, Date)
    done = Job.status == JobStatus.DONE.value
    failed = Job.status == JobStatus.FAILED.value

    jobs_rows = session.execute(
        select(
            job_day,
            func.count(),
            func.count().filter(done),
            func.count().filter(failed),
            func.sum(Upload.duration_s).filter(done),
            func.sum(Job.compute_s).filter(done),
        )
        .join(Upload, Job.upload_id == Upload.id)
        .where(Job.created_at >= since)
        .group_by(job_day)
    ).all()
    user_day = cast(User.created_at, Date)
    users_rows = session.execute(
        select(user_day, func.count()).where(User.created_at >= since).group_by(user_day)
    ).all()
    active_rows = session.execute(
        select(job_day, func.count(distinct(Upload.owner_id)))
        .join(Upload, Job.upload_id == Upload.id)
        .where(Job.created_at >= since)
        .group_by(job_day)
    ).all()

    def active_since(delta: timedelta) -> int:
        return session.scalar(
            select(func.count(distinct(Upload.owner_id)))
            .join(Job, Job.upload_id == Upload.id)
            .where(Job.created_at >= now - delta)
        )

    by_model = [
        {"model": model, "jobs": count, "avg_compute_s": avg_compute,
         "realtime_factor": compute / media if compute and media else None}
        for model, count, avg_compute, compute, media in session.execute(
            select(Job.model, func.count(), func.avg(Job.compute_s), func.sum(Job.compute_s),
                   func.sum(Upload.duration_s))
            .join(Upload, Job.upload_id == Upload.id)
            .where(done, Job.created_at >= since)
            .group_by(Job.model)
            .order_by(func.count().desc())
        )
    ]
    by_language = [
        {"language": language, "jobs": count}
        for language, count in session.execute(
            select(Job.target_language, func.count())
            .where(Job.created_at >= since)
            .group_by(Job.target_language)
            .order_by(func.count().desc())
        )
    ]
    by_output = dict(session.execute(
        select(Job.output_type, func.count()).where(Job.created_at >= since).group_by(Job.output_type)
    ).all())
    by_status = dict(session.execute(
        select(Job.status, func.count()).where(Job.created_at >= since).group_by(Job.status)
    ).all())

    wait = func.extract("epoch", Job.started_at - Job.created_at)
    total = func.extract("epoch", Job.finished_at - Job.created_at)
    kept_count, kept_bytes = session.execute(
        select(func.count(), func.sum(Upload.size_bytes)).where(Upload.purged_at.is_(None))
    ).one()

    return {
        "days": days,
        "series": [
            {**jobs, **users, **active}
            for jobs, users, active in zip(
                _day_series(jobs_rows, start, days, ("jobs", "done", "failed", "media_s", "compute_s")),
                _day_series(users_rows, start, days, ("new_users",)),
                _day_series(active_rows, start, days, ("active_users",)),
            )
        ],
        "users": {
            "total": session.scalar(select(func.count()).select_from(User)),
            "admins": session.scalar(select(func.count()).where(User.role == "admin")),
            "disabled": session.scalar(select(func.count()).where(User.disabled_at.is_not(None))),
            "sso": session.scalar(select(func.count(distinct(UserIdentity.user_id)))),
            "new": sum(count for _, count in users_rows),
            "active_7d": active_since(timedelta(days=7)),
            "active_30d": active_since(timedelta(days=30)),
        },
        "jobs": {
            "total": sum(by_status.values()),
            "by_status": by_status,
            "by_output_type": by_output,
            "success_rate": (
                by_status.get(JobStatus.DONE.value, 0)
                / (by_status.get(JobStatus.DONE.value, 0) + by_status.get(JobStatus.FAILED.value, 0))
                if by_status.get(JobStatus.DONE.value) or by_status.get(JobStatus.FAILED.value) else None
            ),
            "wait_s": _avg_p95(session, wait, Job.started_at.is_not(None), Job.created_at >= since),
            "compute_s": _avg_p95(session, Job.compute_s, done, Job.created_at >= since),
            "total_s": _avg_p95(session, total, done, Job.created_at >= since),
        },
        "by_model": by_model,
        "by_language": by_language,
        "storage": {"uploads": kept_count, "uploads_bytes": kept_bytes or 0},
    }
