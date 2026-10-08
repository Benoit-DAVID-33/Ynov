from app.domain import Segment
from app.subtitles import to_srt, to_text, to_vtt

SEGMENTS = [Segment(0.5, 2.0, " Hello world. "), Segment(3661.007, 3662.5, "Bye.")]


def test_srt_numbers_blocks_and_pads_timestamps():
    assert to_srt(SEGMENTS) == (
        "1\n00:00:00,500 --> 00:00:02,000\nHello world.\n"
        "\n"
        "2\n01:01:01,007 --> 01:01:02,500\nBye.\n"
    )


def test_vtt_uses_dot_separator_and_header():
    vtt = to_vtt(SEGMENTS)
    assert vtt.startswith("WEBVTT\n\n00:00:00.500 --> 00:00:02.000\nHello world.\n")


def test_text_has_no_timestamps():
    assert to_text(SEGMENTS) == "Hello world. Bye."


def test_speaker_is_prefixed():
    segments = [Segment(0, 1, "Hi.", speaker="Steve")]
    assert "[Steve] Hi." in to_srt(segments)
    assert to_text(segments) == "[Steve] Hi."

