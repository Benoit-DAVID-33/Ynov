from app import jobs, media, pipeline
from app.db import session_scope
from app.domain import Segment
from app.models import Job, Upload
from app.transcription.fake import FakeTranscriber
from app.translation import translate_segments


# --- progress ---------------------------------------------------------------

def test_progress_is_reported_per_stage_and_never_goes_back(client, submit, settings):
    job = submit("clip.mp4", "video_embedded", translate_to="fr")
    with session_scope() as session:
        jobs.claim_next(session)
        claimed = session.get(Job, job["id"])
    reports = []
    pipeline.run_job(claimed, None, settings, lambda stage, fraction: reports.append((stage, fraction)))

    stages = list(dict.fromkeys(stage for stage, _ in reports))
    assert stages == ["transcription", "translation", "video"]
    fractions = [fraction for _, fraction in reports]
    assert fractions == sorted(fractions)
    # The stubbed encoder stops at 50 % of the last step (weights 10 + 1 + 4).
    assert fractions[0] == 0.0 and fractions[-1] == (10 + 1 + 0.5 * 4) / 15


def test_job_exposes_progress_while_processing_and_100_when_done(client, submit, run_worker):
    job = submit()
    assert client.get(f"/api/jobs/{job['id']}").json()["progress"] == 0
    with session_scope() as session:
        jobs.claim_next(session)
        jobs.set_progress(session, job["id"], "transcription", 42)
    running = client.get(f"/api/jobs/{job['id']}").json()
    assert (running["status"], running["stage"], running["progress"]) == ("processing", "transcription", 42)

    with session_scope() as session:
        session.get(Job, job["id"]).status = "queued"
    run_worker()
    done = client.get(f"/api/jobs/{job['id']}").json()
    assert (done["status"], done["stage"], done["progress"]) == ("done", None, 100)


# --- translation ------------------------------------------------------------

def test_config_lists_translation_targets(client):
    assert client.get("/api/config").json()["translation_targets"] == ["fr"]


def test_unavailable_translation_is_rejected(client):
    upload = client.post("/api/uploads", files={"file": ("a.wav", b"data")}).json()
    body = {"upload_id": upload["id"], "output_type": "text", "translate_to": "de"}
    assert client.post("/api/jobs", json=body).status_code == 422


def test_translated_subtitles_keep_timing_and_source_is_kept(client, submit, run_worker):
    job = submit("clip.mp4", "subtitles", translate_to="fr")
    run_worker()
    srt = client.get(f"/api/jobs/{job['id']}/download").text
    assert srt.startswith("1\n00:00:00,500 --> 00:00:02,000\n[fr] Hello world.\n")

    transcript = client.get(f"/api/jobs/{job['id']}/transcript").json()
    assert (transcript["language"], transcript["source_language"]) == ("fr", "en")
    assert transcript["text"] == "[fr] Hello world. [fr] This is a fake transcription."


def test_translation_after_original_reuses_the_transcription(client, submit, run_worker):
    first = submit("clip.mp4", "text")
    run_worker()
    body = {"upload_id": first["upload_id"], "output_type": "text", "translate_to": "fr"}
    second = client.post("/api/jobs", json=body).json()
    run_worker()
    assert FakeTranscriber.calls == 1
    assert client.get(f"/api/jobs/{second['id']}/download").text.startswith("[fr] Hello")
    assert client.get(f"/api/jobs/{first['id']}/download").text.startswith("Hello")


def test_sentence_split_over_several_subtitles_is_translated_as_a_whole():
    segments = [
        Segment(0, 2, "one two three four"),
        Segment(2, 3, "five six."),
        Segment(3, 4, "Next."),
    ]
    received = []

    def translate(texts):
        received.extend(texts)
        return [text.upper() for text in texts]

    result = translate_segments(segments, translate)
    assert received == ["one two three four five six.", "Next."]
    assert [(s.start, s.end, s.text) for s in result] == [
        (0, 2, "ONE TWO THREE FOUR"), (2, 3, "FIVE SIX."), (3, 4, "NEXT."),
    ]


# --- subtitle style ---------------------------------------------------------

def test_burned_subtitle_style_reaches_ffmpeg(client, submit, run_worker, fake_ffmpeg):
    submit("clip.mp4", "video_embedded", subtitle_style={"size": "large", "color": "#FFFF00"})
    run_worker()
    assert fake_ffmpeg["style"] == {"size": "large", "color": "#FFFF00"}
    assert fake_ffmpeg["duration_s"] == 10.0


def test_style_is_converted_to_a_libass_override():
    assert media._force_style(None) == ""
    assert media._force_style({"size": "large", "color": "#FFCC00"}) == (
        ":force_style='FontSize=26,PrimaryColour=&H0000CCFF'"
    )


def test_invalid_style_is_rejected(client):
    upload = client.post("/api/uploads", files={"file": ("a.mp4", b"data")}).json()
    for style in ({"size": "huge"}, {"color": "red"}, {"color": "#FFF'"}):
        body = {"upload_id": upload["id"], "output_type": "video_embedded", "subtitle_style": style}
        assert client.post("/api/jobs", json=body).status_code == 422


# --- fast lane --------------------------------------------------------------

def _set_duration(job, seconds):
    with session_scope() as session:
        session.get(Upload, job["upload_id"]).duration_s = seconds


def test_fast_lane_skips_long_media_queued_first(client, submit, settings):
    long_job, short_job, unknown = submit("long.mp4"), submit("short.mp4"), submit("unknown.mp4")
    _set_duration(long_job, 1800)
    _set_duration(short_job, 120)
    _set_duration(unknown, None)

    with session_scope() as session:
        assert jobs.claim_next(session, settings.fast_lane_max_s) == short_job["id"]
        # Nothing short left: the fast lane stays free rather than taking a long file.
        assert jobs.claim_next(session, settings.fast_lane_max_s) is None
        assert jobs.claim_next(session) == long_job["id"]
        assert jobs.claim_next(session) == unknown["id"]
