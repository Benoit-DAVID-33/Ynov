import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import media
from app.config import Settings
from app.main import create_app
from app.subtitles import Segment


class FakeTranscriber:
    def transcribe(self, audio_path: Path):
        return [Segment(0, 1.5, "Hello"), Segment(1.5, 3, "world")]


class BrokenTranscriber:
    def transcribe(self, audio_path: Path):
        raise RuntimeError("model crashed")


def make_client(tmp_path, transcriber, monkeypatch):
    monkeypatch.setattr(media, "probe_duration", lambda path: 10.0)
    settings = Settings(data_dir=tmp_path, transcriber="fake", whisper_model="", device="cpu",
                        workers=1, max_upload_mb=1, admin_token="secret")
    return TestClient(create_app(settings, lambda: transcriber))


def wait_for(client, job_id, status):
    for _ in range(100):
        job = client.get(f"/jobs/{job_id}").json()
        if job["status"] == status:
            return job
        time.sleep(0.05)
    pytest.fail(f"job never reached {status}: {job}")


def upload(client, name="talk.wav"):
    return client.post("/jobs", files={"file": (name, b"RIFFdata")})


def test_audio_to_text_flow(tmp_path, monkeypatch):
    with make_client(tmp_path, FakeTranscriber(), monkeypatch) as client:
        job = upload(client).json()
        assert job["allowed_outputs"] == ["subtitles", "text"]

        assert client.post(f"/jobs/{job['id']}/process", json={"output_format": "text"}).status_code == 202
        wait_for(client, job["id"], "done")

        assert client.get(f"/jobs/{job['id']}/result").text == "Hello world"
        assert client.get(f"/jobs/{job['id']}/preview").text == "Hello world"

        metrics = client.get("/admin/metrics", headers={"X-Admin-Token": "secret"}).json()
        assert metrics["inferences_done"] == 1
        assert metrics["inferences_done_by_type"] == {"text": 1}


def test_subtitles_result(tmp_path, monkeypatch):
    with make_client(tmp_path, FakeTranscriber(), monkeypatch) as client:
        job_id = upload(client).json()["id"]
        client.post(f"/jobs/{job_id}/process", json={"output_format": "subtitles"})
        wait_for(client, job_id, "done")
        assert "00:00:00,000 --> 00:00:01,500\nHello" in client.get(f"/jobs/{job_id}/result").text


def test_audio_cannot_produce_video(tmp_path, monkeypatch):
    with make_client(tmp_path, FakeTranscriber(), monkeypatch) as client:
        job_id = upload(client).json()["id"]
        res = client.post(f"/jobs/{job_id}/process", json={"output_format": "video_embedded"})
        assert res.status_code == 422


def test_rejects_unsupported_file(tmp_path, monkeypatch):
    with make_client(tmp_path, FakeTranscriber(), monkeypatch) as client:
        assert upload(client, "notes.pdf").status_code == 415


def test_rejects_too_large_file(tmp_path, monkeypatch):
    with make_client(tmp_path, FakeTranscriber(), monkeypatch) as client:
        res = client.post("/jobs", files={"file": ("big.wav", b"0" * (1024 * 1024 + 1))})
        assert res.status_code == 413


def test_failed_job_is_reported(tmp_path, monkeypatch):
    with make_client(tmp_path, BrokenTranscriber(), monkeypatch) as client:
        job_id = upload(client).json()["id"]
        client.post(f"/jobs/{job_id}/process", json={"output_format": "text"})
        job = wait_for(client, job_id, "failed")
        assert "model crashed" in job["error"]
        assert client.get(f"/jobs/{job_id}/result").status_code == 409
        metrics = client.get("/admin/metrics", headers={"X-Admin-Token": "secret"}).json()
        assert metrics["failed"] == 1


def test_admin_requires_token(tmp_path, monkeypatch):
    with make_client(tmp_path, FakeTranscriber(), monkeypatch) as client:
        assert client.get("/admin/metrics").status_code == 401
