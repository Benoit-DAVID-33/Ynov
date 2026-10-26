import io
import zipfile

import pytest

from app import media
from app.transcription.fake import FakeTranscriber


def test_config_exposes_models_and_output_matrix(client):
    config = client.get("/api/config").json()
    assert config["models"] == ["fake"]
    assert config["allowed_outputs"]["audio"] == ["subtitles", "text"]
    assert len(config["allowed_outputs"]["video"]) == 4


def test_upload_rejects_other_formats(client):
    response = client.post("/api/uploads", files={"file": ("notes.pdf", b"data")})
    assert response.status_code == 415


def test_upload_rejects_empty_and_oversized_files(client, settings):
    assert client.post("/api/uploads", files={"file": ("a.wav", b"")}).status_code == 400
    too_big = b"x" * (settings.max_upload_mb * 1024 * 1024 + 1)
    assert client.post("/api/uploads", files={"file": ("a.wav", too_big)}).status_code == 413
    assert list(settings.uploads_dir.iterdir()) == []


@pytest.mark.parametrize("output_type", ["video_embedded", "video_subtitles"])
def test_audio_cannot_produce_video(client, output_type):
    upload = client.post("/api/uploads", files={"file": ("a.wav", b"data")}).json()
    assert upload["allowed_outputs"] == ["subtitles", "text"]
    response = client.post("/api/jobs", json={"upload_id": upload["id"], "output_type": output_type})
    assert response.status_code == 422


def test_unknown_model_and_upload_are_rejected(client):
    upload = client.post("/api/uploads", files={"file": ("a.wav", b"data")}).json()
    body = {"upload_id": upload["id"], "output_type": "text", "model": "whisper-medium.en"}
    assert client.post("/api/jobs", json=body).status_code == 422  # registered but not enabled
    body = {"upload_id": "missing", "output_type": "text"}
    assert client.post("/api/jobs", json=body).status_code == 404


def test_result_unavailable_until_done(client, submit):
    job = submit()
    assert job["status"] == "queued"
    assert job["queue_position"] == 1
    assert client.get(f"/api/jobs/{job['id']}/download").status_code == 409
    assert client.get(f"/api/jobs/{job['id']}/transcript").status_code == 409


def test_text_from_audio(client, submit, run_worker):
    job = submit("meeting.wav", "text")
    run_worker()

    done = client.get(f"/api/jobs/{job['id']}").json()
    assert done["status"] == "done"
    assert done["compute_s"] is not None

    download = client.get(f"/api/jobs/{job['id']}/download")
    assert download.text == "Hello world. This is a fake transcription."
    assert 'attachment; filename="meeting-transcript.txt"' in download.headers["content-disposition"]

    transcript = client.get(f"/api/jobs/{job['id']}/transcript").json()
    assert transcript["language"] == "en"
    assert transcript["segments"][0] == {"start": 0.5, "end": 2.0, "text": "Hello world.", "speaker": None}


def test_subtitles_only(client, submit, run_worker):
    job = submit("clip.mp4", "subtitles")
    run_worker()
    srt = client.get(f"/api/jobs/{job['id']}/download").text
    assert srt.startswith("1\n00:00:00,500 --> 00:00:02,000\nHello world.\n")
    vtt = client.get(f"/api/jobs/{job['id']}/files/subtitles.vtt")
    assert vtt.text.startswith("WEBVTT")
    assert vtt.headers["content-disposition"].startswith("inline")


def test_video_with_embedded_subtitles(client, submit, run_worker):
    job = submit("clip.mp4", "video_embedded")
    run_worker()
    download = client.get(f"/api/jobs/{job['id']}/download")
    assert download.headers["content-type"] == "video/mp4"
    assert download.content == b"burned"


def test_video_with_separate_subtitles_is_bundled(client, submit, run_worker):
    job = submit("clip.mp4", "video_subtitles")
    run_worker()
    done = client.get(f"/api/jobs/{job['id']}").json()
    assert [a["name"] for a in done["artifacts"]] == [
        "bundle.zip", "video.mp4", "subtitles.srt", "subtitles.vtt"
    ]
    bundle = client.get(f"/api/jobs/{job['id']}/download").content
    with zipfile.ZipFile(io.BytesIO(bundle)) as archive:
        assert sorted(archive.namelist()) == ["subtitles.srt", "video.mp4"]
        assert archive.read("video.mp4") == b"muxed"
    assert client.get(f"/api/jobs/{job['id']}/files/video.mp4").content == b"muxed"
    assert client.get(f"/api/jobs/{job['id']}/files/..%2Ftest.db").status_code == 404


def test_second_output_for_same_file_reuses_transcription(client, submit, run_worker):
    first = submit("clip.mp4", "text")
    run_worker()
    assert FakeTranscriber.calls == 1

    second = client.post(
        "/api/jobs", json={"upload_id": first["upload_id"], "output_type": "subtitles"}
    ).json()
    run_worker()
    assert FakeTranscriber.calls == 1
    assert client.get(f"/api/jobs/{second['id']}").json()["status"] == "done"


def test_failed_job_reports_error(client, submit, run_worker, monkeypatch):
    def broken(source, dest):
        raise media.MediaError("ffmpeg a échoué : piste audio absente")

    monkeypatch.setattr(media, "extract_audio", broken)
    job = submit()
    run_worker()
    failed = client.get(f"/api/jobs/{job['id']}").json()
    assert failed["status"] == "failed"
    assert "piste audio absente" in failed["error"]


def test_user_app_serves_its_page_and_nothing_from_the_admin(client):
    page = client.get("/").text
    assert "Sous-titrage" in page
    assert "admin" not in page.lower()
    assert client.get("/shared/style.css").status_code == 200
    assert client.get("/api/admin/stats").status_code == 404
    assert client.get("/api/overview").status_code == 404