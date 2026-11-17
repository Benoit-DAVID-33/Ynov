"""The worker side of Triton: streamed transcription, translation, model loading.

The server is replaced by a fake client that replays what Triton sends.
"""

import wave

import numpy as np
import pytest
from tritonclient.utils import InferenceServerException

from app import triton_client
from app.config import get_settings
from app.transcription.base import _transcriber_factories
from app.transcription.triton import TritonWhisper
from app.translation.base import available_targets
from app.translation.triton import TritonTranslator


class _Param:
    def __init__(self, value):
        self.bool_param = value


class _Response:
    def __init__(self, final):
        self.parameters = {"triton_final_response": _Param(True)} if final else {}


class FakeResult:
    def __init__(self, final=False, **outputs):
        self._outputs = outputs
        self._final = final

    def as_numpy(self, name):
        value = self._outputs.get(name)
        if value is None:
            return None
        if isinstance(value, str):
            return np.array([value.encode("utf-8")], dtype=np.object_)
        if isinstance(value, list):
            return np.array([v.encode("utf-8") for v in value], dtype=np.object_)
        return np.array([value], dtype=np.float32)

    def get_response(self):
        return _Response(self._final)


class FakeClient:
    """Records the calls; `stream` is what the server answers to the next request."""

    instances = []

    def __init__(self, stream=(), translation=None, ready=True, error=None):
        self.stream = stream
        self.translation = translation
        self.ready = ready
        self.error = error
        self.calls = []
        self.loaded = []
        self.closed = False
        self.stopped_with = None
        FakeClient.instances.append(self)

    def start_stream(self, callback):
        self.callback = callback

    def async_stream_infer(self, model, inputs, enable_empty_final_response):
        self.calls.append((model, inputs))
        assert enable_empty_final_response
        for item in self.stream:
            if isinstance(item, Exception):
                self.callback(None, item)
            else:
                self.callback(item, None)

    def stop_stream(self, cancel_requests=False):
        self.stopped_with = cancel_requests

    def infer(self, model, inputs, client_timeout):
        self.calls.append((model, inputs))
        if self.error:
            raise self.error
        return FakeResult(TRANSLATION=self.translation)

    def is_model_ready(self, model):
        if self.error:
            raise self.error
        return self.ready or model in self.loaded

    def load_model(self, model):
        self.loaded.append(model)

    def close(self):
        self.closed = True


@pytest.fixture
def triton(settings, monkeypatch):
    monkeypatch.setenv("INFERENCE_BACKEND", "triton")
    get_settings.cache_clear()
    FakeClient.instances = []

    def use(**answers):
        monkeypatch.setattr(triton_client, "connect", lambda settings: FakeClient(**answers))

    return use


@pytest.fixture
def audio(tmp_path):
    path = tmp_path / "audio.wav"
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(np.zeros(16000 * 10, dtype=np.int16).tobytes())  # 10 s
    return path


def test_segments_stream_in_with_progress(triton, audio):
    triton(stream=[
        FakeResult(LANGUAGE="en"),
        FakeResult(START=0.5, END=2.5, TEXT="Hello world."),
        FakeResult(START=2.5, END=5.0, TEXT="Second line."),
        FakeResult(final=True),
    ])
    progress = []
    result = TritonWhisper("whisper_medium_en").transcribe(audio, progress.append)

    assert result.language == "en"
    assert [(s.start, s.end, s.text) for s in result.segments] == [
        (0.5, 2.5, "Hello world."), (2.5, 5.0, "Second line."),
    ]
    assert progress == [0.25, 0.5]
    client = FakeClient.instances[0]
    model, (tensor,) = client.calls[0]
    assert model == "whisper_medium_en"
    assert (tensor.name(), tensor.datatype(), tensor.shape()) == ("AUDIO", "INT16", [160000])
    assert client.stopped_with is True and client.closed


def test_server_error_is_reported_to_the_job(triton, audio):
    triton(stream=[InferenceServerException("model is not ready")])
    with pytest.raises(triton_client.InferenceUnavailable, match="Serveur d'inférence : model is not ready"):
        TritonWhisper("whisper_medium_en").transcribe(audio, lambda fraction: None)
    assert FakeClient.instances[0].closed


def test_cancelled_job_stops_the_stream(triton, audio):
    class Cancelled(Exception):
        pass

    def on_progress(fraction):
        raise Cancelled

    triton(stream=[FakeResult(LANGUAGE="en"), FakeResult(START=0.0, END=1.0, TEXT="a"),
                   FakeResult(START=1.0, END=2.0, TEXT="b"), FakeResult(final=True)])
    with pytest.raises(Cancelled):
        TritonWhisper("whisper_medium_en").transcribe(audio, on_progress)
    assert FakeClient.instances[0].stopped_with is True


def test_answer_without_language_is_refused(triton, audio):
    triton(stream=[FakeResult(final=True)])
    with pytest.raises(triton_client.InferenceUnavailable, match="incomplète"):
        TritonWhisper("whisper_medium_en").transcribe(audio, lambda fraction: None)


def test_translation_sends_sentences_and_target(triton):
    triton(translation=["Bonjour.", "Deuxième phrase."])
    assert TritonTranslator("fr").translate(["Hello.", "Second sentence."]) == ["Bonjour.", "Deuxième phrase."]
    model, (texts, target) = FakeClient.instances[0].calls[0]
    assert model == "translator"
    assert (texts.name(), texts.shape(), target.name()) == ("TEXT", [2], "TARGET")
    assert TritonTranslator("fr").translate([]) == []


def test_translation_error_is_reported(triton):
    triton(error=InferenceServerException("unavailable"))
    with pytest.raises(triton_client.InferenceUnavailable, match="unavailable"):
        TritonTranslator("fr").translate(["Hello."])


def test_missing_model_is_loaded_on_demand(triton):
    triton(ready=False)
    TritonWhisper("whisper_small").load()
    assert FakeClient.instances[0].loaded == ["whisper_small"]


def test_unreachable_server_fails_the_load_clearly(triton):
    triton(error=InferenceServerException("failed to connect to all addresses"))
    with pytest.raises(triton_client.InferenceUnavailable, match="failed to connect"):
        TritonTranslator("fr").load()


def test_registry_points_every_whisper_to_its_triton_model(triton):
    names = {name: _transcriber_factories[name]() for name in
             ("whisper-medium.en", "whisper-small.en", "whisper-medium", "whisper-large-v3-turbo")}
    assert {n: (type(t).__name__, t.model) for n, t in names.items()} == {
        "whisper-medium.en": ("TritonWhisper", "whisper_medium_en"),
        "whisper-small.en": ("TritonWhisper", "whisper_small_en"),
        "whisper-medium": ("TritonWhisper", "whisper_medium"),
        "whisper-large-v3-turbo": ("TritonWhisper", "whisper_large_v3_turbo"),
    }


def test_translation_targets_come_from_the_settings_with_triton(triton, monkeypatch):
    # The models live in the Triton image: the worker does not need them on disk.
    monkeypatch.setenv("ENABLED_TRANSLATORS", "opus-mt-en-fr,opus-mt-en-zh")
    get_settings.cache_clear()
    assert available_targets() == ["fr", "zh"]


def test_model_repository_matches_the_registry():
    """Every Whisper of the registry has its directory in triton/model_repository."""
    from pathlib import Path

    repository = Path(__file__).resolve().parent.parent / "triton" / "model_repository"
    for name in ("whisper_medium_en", "whisper_small_en", "whisper_medium", "whisper_small",
                 "whisper_large_v3_turbo", "translator"):
        config = (repository / name / "config.pbtxt").read_text(encoding="utf-8")
        assert f'name: "{name}"' in config
        assert (repository / name / "1" / "model.py").is_file()
