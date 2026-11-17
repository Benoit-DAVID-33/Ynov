from prometheus_client import REGISTRY, generate_latest

from app import metrics
from app.db import session_scope
from app.models import Worker, utcnow


def _value(name, **labels):
    return REGISTRY.get_sample_value(name, labels) or 0.0


def test_api_requests_are_counted_by_route_template(client, submit):
    labels = {"service": "api", "method": "GET", "route": "/api/jobs/{job_id}", "status": "200"}
    before = _value("subtitle_http_requests_total", **labels)
    job = submit()
    client.get(f"/api/jobs/{job['id']}")
    client.get(f"/api/jobs/{job['id']}")
    # One series per route, never one per job identifier.
    assert _value("subtitle_http_requests_total", **labels) == before + 2
    static = {"service": "api", "method": "GET", "route": "static", "status": "200"}
    before = _value("subtitle_http_requests_total", **static)
    client.get("/app.js")
    assert _value("subtitle_http_requests_total", **static) == before + 1


def test_jobs_and_stages_are_measured_by_the_worker(submit, run_worker):
    done = {"output_type": "subtitles", "model": "fake", "status": "done"}
    before = _value("subtitle_jobs_total", **done)
    stage = {"stage": "transcription", "backend": "local"}
    stages_before = _value("subtitle_stage_duration_seconds_count", **stage)
    submit("a.mp4", "subtitles")
    run_worker()
    assert _value("subtitle_jobs_total", **done) == before + 1
    assert _value("subtitle_stage_duration_seconds_count", **stage) == stages_before + 1
    assert _value("subtitle_job_duration_seconds_count", output_type="subtitles", model="fake") >= 1


def test_failed_jobs_are_counted(submit, run_worker, monkeypatch):
    from app import media

    def broken(source, dest):
        raise media.MediaError("boom")

    monkeypatch.setattr(media, "extract_audio", broken)
    failed = {"output_type": "text", "model": "fake", "status": "failed"}
    before = _value("subtitle_jobs_total", **failed)
    submit("a.mp4", "text")
    run_worker()
    assert _value("subtitle_jobs_total", **failed) == before + 1


def test_database_gauges_are_read_at_scrape_time(client, submit, settings):
    metrics.register_database_collector(settings)
    submit("a.mp4")
    submit("b.mp4")
    with session_scope() as session:
        session.add(Worker(id="host:1", device="triton", heartbeat_at=utcnow()))
    text = generate_latest(REGISTRY).decode()
    assert "subtitle_database_up 1.0" in text
    assert 'subtitle_queue_jobs{status="queued"} 2.0' in text
    assert 'subtitle_workers_up{device="triton"} 1.0' in text
    assert "subtitle_queue_media_seconds 20.0" in text
    assert "subtitle_users_active 1.0" in text  # alice (the console, which creates admin, is not started)
