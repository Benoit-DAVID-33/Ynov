from collections import Counter

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain import JobStatus
from app.models import Job, Upload

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
