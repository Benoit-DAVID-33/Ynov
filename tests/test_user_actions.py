from pathlib import Path

from app import jobs, media, retention, worker
from app.db import session_scope
from app.domain import Segment, Transcription
from app.models import Job, Upload
from app.subtitles import layout, to_srt
from app.transcription.fake import FakeTranscriber


# --- subtitle layout --------------------------------------------------------

def test_short_subtitle_is_left_on_one_line():
    assert layout([Segment(0, 2, "Hello world.")]) == [(0, 2, "Hello world.")]


def test_long_subtitle_is_wrapped_on_two_balanced_lines():
    text = "one of your biggest messages in campaign slogans was"  # 52 characters
    [(start, end, cue)] = layout([Segment(4, 8, text)])
    first, second = cue.split("\n")
    assert (start, end) == (4, 8)
    assert f"{first} {second}" == text
    assert max(len(first), len(second)) <= 42 and abs(len(first) - len(second)) <= 8


def test_subtitle_too_long_for_two_lines_is_split_in_time():
    words = " ".join(f"word{i:02d}" for i in range(30))  # 209 characters
    cues = layout([Segment(10, 20, words)])
    assert len(cues) == 3
    assert all(len(line) <= 42 for _, _, cue in cues for line in cue.split("\n"))
    assert all(cue.count("\n") <= 1 for _, _, cue in cues)
    assert " ".join(cue.replace("\n", " ") for _, _, cue in cues) == words
    # Contiguous, covering exactly the original time span.
    assert cues[0][0] == 10 and cues[-1][1] == 20
    assert all(a[1] == b[0] for a, b in zip(cues, cues[1:]))


def test_narrower_lines_for_large_burned_in_text(client, submit, run_worker, settings):
    long_text = "the idea that serving the American people is a privilege"  # 56 characters

    class LongLine(FakeTranscriber):
        def transcribe(self, audio_path, on_progress):
            return Transcription("en", [Segment(0, 4, long_text)])

    from app.transcription import base
    base._instances[("modèle", "fake")] = LongLine()
    try:
        job = submit("clip.mp4", "video_embedded", subtitle_style={"size": "large", "color": "#FFFFFF"})
        run_worker()
    finally:
        del base._instances[("modèle", "fake")]
    srt = (settings.results_dir / job["id"] / "subtitles.srt").read_text(encoding="utf-8")
    lines = srt.strip().splitlines()[2:]
    assert len(lines) == 2 and all(len(line) <= media.LINE_CHARS["large"] for line in lines)


def test_empty_subtitles_are_not_written():
    assert to_srt([Segment(0, 1, "  "), Segment(1, 2, "Kept.")]).startswith("1\n00:00:01,000")


# --- detected language ------------------------------------------------------

def test_language_detected_by_the_model_is_stored_and_not_translated_to_itself(
    client, submit, run_worker
):
    class French(FakeTranscriber):
        def transcribe(self, audio_path, on_progress):
            return Transcription("fr", [Segment(0, 2, "Bonjour à tous.")])

    from app.transcription import base
    base._instances[("modèle", "fake")] = French()
    try:
        job = submit("reunion.wav", "text", translate_to="fr")
        run_worker()
    finally:
        del base._instances[("modèle", "fake")]
    transcript = client.get(f"/api/jobs/{job['id']}/transcript").json()
    assert (transcript["language"], transcript["source_language"]) == ("fr", "fr")
    assert transcript["text"] == "Bonjour à tous."  # not passed through the en->fr translator


# --- corrections ------------------------------------------------------------

def test_corrected_text_rebuilds_the_files_without_transcribing_again(
    client, submit, run_worker, fake_ffmpeg
):
    job = submit("clip.mp4", "video_embedded")
    run_worker()
    first_compute = client.get(f"/api/jobs/{job['id']}").json()["compute_s"]

    response = client.put(
        f"/api/jobs/{job['id']}/segments", json={"texts": ["Hello,  world!", ""]}
    )
    assert response.status_code == 200
    assert (response.json()["status"], response.json()["artifacts"]) == ("queued", [])
    assert client.get(f"/api/jobs/{job['id']}/download").status_code == 409

    fake_ffmpeg.clear()
    run_worker()
    done = client.get(f"/api/jobs/{job['id']}").json()
    assert done["status"] == "done" and done["compute_s"] > first_compute
    assert FakeTranscriber.calls == 1
    assert "on_progress" in fake_ffmpeg  # the video was burned again

    transcript = client.get(f"/api/jobs/{job['id']}/transcript").json()
    assert transcript["text"] == "Hello, world!"
    assert [s["text"] for s in transcript["segments"]] == ["Hello, world!", ""]


def test_corrections_apply_to_the_translated_text_and_carry_over(client, submit, run_worker):
    job = submit("clip.mp4", "subtitles", translate_to="fr")
    run_worker()
    client.put(f"/api/jobs/{job['id']}/segments", json={"texts": ["Bonjour.", "Ceci est corrigé."]})
    run_worker()
    assert "Ceci est corrigé." in client.get(f"/api/jobs/{job['id']}/download").text

    # Another output of the same file, same language: the corrections are kept...
    body = {"upload_id": job["upload_id"], "output_type": "text", "translate_to": "fr"}
    again = client.post("/api/jobs", json=body).json()
    # ...but not for the original language, which was not corrected.
    original = client.post("/api/jobs", json={**body, "translate_to": None}).json()
    run_worker()
    assert client.get(f"/api/jobs/{again['id']}/download").text == "Bonjour. Ceci est corrigé."
    assert client.get(f"/api/jobs/{original['id']}/download").text.startswith("Hello world.")


def test_correction_is_refused_when_invalid_or_not_allowed(client, stranger, submit, run_worker):
    job = submit()
    url = f"/api/jobs/{job['id']}/segments"
    assert client.put(url, json={"texts": ["a", "b"]}).status_code == 409  # not finished
    run_worker()
    assert client.put(url, json={"texts": ["only one"]}).status_code == 422
    assert client.put(url, json={"texts": ["x" * 501, "b"]}).status_code == 422
    assert stranger.put(url, json={"texts": ["a", "b"]}).status_code == 404


# --- cancel -----------------------------------------------------------------

def test_waiting_job_is_cancelled_and_never_processed(client, submit, run_worker):
    job = submit()
    cancelled = client.post(f"/api/jobs/{job['id']}/cancel")
    assert (cancelled.status_code, cancelled.json()["status"]) == (200, "cancelled")
    run_worker()
    assert FakeTranscriber.calls == 0
    assert client.get(f"/api/jobs/{job['id']}").json()["status"] == "cancelled"
    assert client.post(f"/api/jobs/{job['id']}/cancel").status_code == 409


def test_running_job_stops_at_its_next_progress_report(client, submit, settings, monkeypatch):
    job = submit("clip.mp4", "video_embedded")

    def burn_cancelled_meanwhile(video, srt, dest, **kwargs):
        dest.write_bytes(b"partial")
        client.post(f"/api/jobs/{job['id']}/cancel")
        kwargs["on_progress"](0.3)  # the worker finds out here
        raise AssertionError("the encoding should have been interrupted")

    monkeypatch.setattr(media, "burn_subtitles", burn_cancelled_meanwhile)
    monkeypatch.setattr(worker, "_PROGRESS_MIN_INTERVAL_S", 0)  # no throttling in the test
    worker.process_next(settings)

    assert client.get(f"/api/jobs/{job['id']}").json()["status"] == "cancelled"
    assert not (settings.results_dir / job["id"]).exists()


def test_only_the_owner_can_cancel(client, stranger, submit):
    job = submit()
    assert stranger.post(f"/api/jobs/{job['id']}/cancel").status_code == 404


def test_cancelled_jobs_are_counted_apart(client, admin_client, submit):
    client.post(f"/api/jobs/{submit()['id']}/cancel")
    admin_client.post("/api/login", json={"username": "admin", "password": "admin-secret"})
    stats = admin_client.get("/api/overview").json()["stats"]
    assert stats["cancelled"]["total"] == 1
    assert stats["unfinished"]["total"] == stats["failed"]["total"] == 0


# --- delete -----------------------------------------------------------------

def test_owner_deletes_their_file_and_results_at_once(client, stranger, submit, run_worker, settings):
    job = submit("clip.mp4", "subtitles")
    run_worker()
    waiting = client.post(
        "/api/jobs", json={"upload_id": job["upload_id"], "output_type": "text"}
    ).json()
    with session_scope() as session:
        path = Path(session.get(Upload, job["upload_id"]).path)

    assert stranger.delete(f"/api/uploads/{job['upload_id']}").status_code == 404
    assert path.exists()
    assert client.delete(f"/api/uploads/{job['upload_id']}").status_code == 204

    assert not path.exists() and not (settings.results_dir / job["id"]).exists()
    assert client.get(f"/api/jobs/{waiting['id']}").json()["status"] == "cancelled"
    assert client.get(f"/api/jobs/{job['id']}/download").status_code == 410
    assert client.get("/api/uploads/last").json()["upload"] is None
    body = {"upload_id": job["upload_id"], "output_type": "text"}
    assert client.post("/api/jobs", json=body).status_code == 410
    assert client.delete("/api/uploads/missing").status_code == 404


def test_file_locked_at_deletion_is_removed_by_the_next_purge(
    client, submit, run_worker, settings, monkeypatch
):
    job = submit()
    run_worker()
    with session_scope() as session:
        path = Path(session.get(Upload, job["upload_id"]).path)

    real_unlink = Path.unlink

    def locked(self, *args, **kwargs):
        raise PermissionError("file in use")

    monkeypatch.setattr(Path, "unlink", locked)
    assert client.delete(f"/api/uploads/{job['upload_id']}").status_code == 204
    assert path.exists()

    monkeypatch.setattr(Path, "unlink", real_unlink)
    with session_scope() as session:
        assert retention.purge(session, settings) == 1
    assert not path.exists()
    with session_scope() as session:
        assert session.get(Job, job["id"]).text.startswith("Hello")  # history kept
