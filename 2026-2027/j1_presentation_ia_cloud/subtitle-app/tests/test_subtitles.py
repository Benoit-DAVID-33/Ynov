from app.domain import Segment
from app.subtitles import layout, to_srt, to_text, to_vtt

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



# --- scripts without spaces (Chinese) ----------------------------------------

def test_chinese_wraps_between_characters_at_half_the_width():
    text = "我们今天讨论的是联合国六种官方语言的字幕翻译问题以及如何提高质量"
    cues = layout([Segment(0, 4, text)])
    lines = [line for _start, _end, cue in cues for line in cue.split("\n")]
    assert "".join(lines) == text
    assert all(len(line) <= 21 for line in lines)


def test_chinese_and_latin_words_keep_their_spacing():
    segments = [Segment(0, 1, "我用 Python 写代码。"), Segment(1, 2, "很好。")]
    assert to_text(segments) == "我用Python写代码。很好。"
    assert to_text([Segment(0, 1, "Hello"), Segment(1, 2, "world.")]) == "Hello world."
