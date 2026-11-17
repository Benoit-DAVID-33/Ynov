"""Prometheus metrics of the application services.

Each service serves its own metrics on METRICS_PORT (internal network only), scraped by
the prometheus service of docker-compose.yml:

- api:    HTTP requests (count and latency per route);
- worker: jobs (outcome, duration) and the duration of each stage;
- admin:  state read from the database at scrape time (queue, workers, accounts,
          storage), so the figures are right whichever worker did the work.

The inference server (Triton) publishes its own metrics on its port 8002.
"""

import logging
import time
from contextlib import contextmanager
from datetime import timedelta

from prometheus_client import Counter, Histogram, start_http_server
from prometheus_client.core import GaugeMetricFamily, REGISTRY
from prometheus_client.registry import Collector

from app.config import Settings

log = logging.getLogger("metrics")

# Media and jobs last from seconds to hours: wide buckets.
_JOB_BUCKETS = (1, 2.5, 5, 10, 20, 30, 60, 120, 300, 600, 1200, 3600)
_HTTP_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10)

HTTP_REQUESTS = Counter(
    "subtitle_http_requests", "HTTP requests answered", ["service", "method", "route", "status"],
)
HTTP_LATENCY = Histogram(
    "subtitle_http_request_duration_seconds", "Time to answer an HTTP request",
    ["service", "method", "route"], buckets=_HTTP_BUCKETS,
)
JOBS = Counter(
    "subtitle_jobs", "Jobs finished by a worker", ["output_type", "model", "status"],
)
JOB_DURATION = Histogram(
    "subtitle_job_duration_seconds", "Processing time of a successful job, from start to files",
    ["output_type", "model"], buckets=_JOB_BUCKETS,
)
STAGE_DURATION = Histogram(
    "subtitle_stage_duration_seconds", "Time spent in each stage of a job",
    ["stage", "backend"], buckets=_JOB_BUCKETS,
)


@contextmanager
def timed_stage(stage: str, backend: str):
    started = time.perf_counter()
    try:
        yield
    finally:
        STAGE_DURATION.labels(stage, backend).observe(time.perf_counter() - started)


def serve(settings: Settings, service: str) -> None:
    """Expose /metrics of this process on METRICS_PORT (no-op when 0)."""
    if settings.metrics_port <= 0:
        return
    try:
        start_http_server(settings.metrics_port)
        log.info("%s metrics on port %d", service, settings.metrics_port)
    except OSError:
        # Port taken (a second process of the same service): metrics are optional.
        log.warning("metrics port %d unavailable", settings.metrics_port, exc_info=True)


def instrument_http(app, service: str) -> None:
    """Count and time the requests, labelled by route template (not by URL: bounded)."""

    @app.middleware("http")
    async def measure(request, call_next):
        started = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            route = request.scope.get("route")
            path = getattr(route, "path", None)
            if path is None or not request.url.path.startswith("/api/"):
                path = "static"
            HTTP_REQUESTS.labels(service, request.method, path, str(status)).inc()
            HTTP_LATENCY.labels(service, request.method, path).observe(time.perf_counter() - started)


class DatabaseCollector(Collector):
    """Gauges read from the database at each scrape (admin service)."""

    def __init__(self, settings: Settings):
        self.settings = settings

    def collect(self):
        from sqlalchemy import func, select

        from app.db import session_scope
        from app.domain import JobStatus
        from app.models import Job, Upload, User, Worker, utcnow

        up = GaugeMetricFamily("subtitle_database_up", "1 when the database answers")
        try:
            with session_scope() as session:
                by_status = dict(session.execute(
                    select(Job.status, func.count())
                    .where(Job.status.in_([JobStatus.QUEUED.value, JobStatus.PROCESSING.value]))
                    .group_by(Job.status)
                ).all())
                pending_media = session.scalar(
                    select(func.coalesce(func.sum(Upload.duration_s), 0.0))
                    .join(Job, Job.upload_id == Upload.id)
                    .where(Job.status == JobStatus.QUEUED.value)
                )
                alive_after = utcnow() - timedelta(seconds=self.settings.heartbeat_interval_s * 3)
                workers = session.execute(
                    select(Worker.device, func.count()).where(Worker.heartbeat_at >= alive_after)
                    .group_by(Worker.device)
                ).all()
                users = session.scalar(select(func.count()).select_from(User).where(User.disabled_at.is_(None)))
                kept_count, kept_bytes = session.execute(
                    select(func.count(), func.coalesce(func.sum(Upload.size_bytes), 0))
                    .where(Upload.purged_at.is_(None))
                ).one()
        except Exception:
            log.warning("metrics: database unavailable", exc_info=True)
            up.add_metric([], 0)
            yield up
            return
        up.add_metric([], 1)
        yield up

        queue = GaugeMetricFamily("subtitle_queue_jobs", "Jobs waiting or running", labels=["status"])
        for status in (JobStatus.QUEUED.value, JobStatus.PROCESSING.value):
            queue.add_metric([status], by_status.get(status, 0))
        yield queue
        yield GaugeMetricFamily(
            "subtitle_queue_media_seconds", "Duration of the media waiting in the queue", value=float(pending_media),
        )
        alive = GaugeMetricFamily("subtitle_workers_up", "Workers with a recent heartbeat", labels=["device"])
        for device, count in workers:
            alive.add_metric([device or "?"], count)
        yield alive
        yield GaugeMetricFamily("subtitle_users_active", "Accounts not disabled", value=users)
        yield GaugeMetricFamily("subtitle_storage_uploads", "Uploaded files still on disk", value=kept_count)
        yield GaugeMetricFamily("subtitle_storage_uploads_bytes", "Size of the uploaded files still on disk",
                                value=float(kept_bytes))


_collector: DatabaseCollector | None = None


def register_database_collector(settings: Settings) -> None:
    global _collector
    if _collector is None:
        _collector = DatabaseCollector(settings)
        REGISTRY.register(_collector)
    else:
        _collector.settings = settings
