import wave

import pytest

from app.transcription.whisper import _read_wav


def _write_wav(path, rate, samples):
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(b"".join(s.to_bytes(2, "little", signed=True) for s in samples))


def test_wav_is_decoded_to_normalised_floats(tmp_path):
    _write_wav(tmp_path / "a.wav", 16000, [0, 16384, -32768])
    assert _read_wav(tmp_path / "a.wav").tolist() == [0.0, 0.5, -1.0]


def test_unexpected_sample_rate_is_rejected(tmp_path):
    _write_wav(tmp_path / "a.wav", 44100, [0])
    with pytest.raises(ValueError):
        _read_wav(tmp_path / "a.wav")
