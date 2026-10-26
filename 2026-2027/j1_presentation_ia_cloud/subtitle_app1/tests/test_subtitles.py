from app.subtitles import Segment, format_srt_time, to_srt, to_text


def test_format_srt_time():
    assert format_srt_time(0) == "00:00:00,000"
    assert format_srt_time(3661.5) == "01:01:01,500"
    assert format_srt_time(59.9996) == "00:01:00,000"


def test_to_srt():
    segments = [Segment(0.5, 2.0, "Hello"), Segment(2.0, 4.25, "world", speaker="A")]
    assert to_srt(segments) == (
        "1\n00:00:00,500 --> 00:00:02,000\nHello\n\n"
        "2\n00:00:02,000 --> 00:00:04,250\n[A] world\n"
    )


def test_to_text_has_no_timestamps():
    assert to_text([Segment(0, 1, " Hello "), Segment(1, 2, "world")]) == "Hello world"
