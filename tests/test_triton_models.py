"""The Triton models themselves (triton/backend), run outside Triton.

triton_python_backend_utils, faster_whisper, ctranslate2 and sentencepiece are replaced
by small fakes: what is tested is our code (inputs, streamed responses, cancellation,
errors), not the libraries.
"""

import json
import sys
import types
from pathlib import Path

import numpy as np
import pytest

BACKEND = Path(__file__).resolve().parent.parent / "triton" / "backend"


# --- fake Triton Python backend ---------------------------------------------------------

class Tensor:
    def __init__(self, name, array):
        self.name, self.array = name, array

    def as_numpy(self):
        return self.array


class InferenceResponse:
    def __init__(self, output_tensors=None, error=None):
        self.outputs = {t.name: t.array for t in output_tensors or []}
        self.error = error


class TritonError:
    def __init__(self, message):
        self.message = message


class Sender:
    def __init__(self):
        self.sent = []

    def send(self, response=None, flags=0):
        self.sent.append((response, flags))


class Request:
    def __init__(self, cancel_after=None, **inputs):
        self.inputs = {name: Tensor(name, value) for name, value in inputs.items()}
        self.sender = Sender()
        self.cancel_after = cancel_after

    def get_response_sender(self):
        return self.sender

    def is_cancelled(self):
        segments = sum(1 for r, _ in self.sender.sent if r is not None and "TEXT" in r.outputs)
        return self.cancel_after is not None and segments >= self.cancel_after


def _fake_pb_utils():
    module = types.ModuleType("triton_python_backend_utils")
    module.Tensor = Tensor
    module.InferenceResponse = InferenceResponse
    module.TritonError = TritonError
    module.TRITONSERVER_RESPONSE_COMPLETE_FINAL = 1
    module.get_input_tensor_by_name = lambda request, name: request.inputs.get(name)
    return module


def _args(name, **parameters):
    config = {"parameters": {k: {"string_value": v} for k, v in parameters.items()}}
    return {"model_config": json.dumps(config), "model_name": name,
            "model_instance_kind": "CPU", "model_instance_device_id": "0"}


@pytest.fixture
def backend(monkeypatch):
    monkeypatch.syspath_prepend(str(BACKEND))
    monkeypatch.setitem(sys.modules, "triton_python_backend_utils", _fake_pb_utils())
    for name in list(sys.modules):
        if name.startswith("subtitle_models"):
            monkeypatch.delitem(sys.modules, name)
    return monkeypatch


# --- whisper ---------------------------------------------------------------------------

class _Segment:
    def __init__(self, start, end, text):
        self.start, self.end, self.text = start, end, text


@pytest.fixture
def whisper(backend):
    seen = {}

    class WhisperModel:
        def __init__(self, model, **options):
            seen["model"], seen["options"] = model, options

    class BatchedInferencePipeline:
        def __init__(self, model):
            pass

        def transcribe(self, audio, language, batch_size, without_timestamps):
            seen["audio"], seen["language"], seen["batch_size"] = audio, language, batch_size
            if len(audio) == 0:
                raise RuntimeError("empty audio")
            segments = [_Segment(0.0, 1.5, " Bonjour. "), _Segment(1.5, 2.0, "  "), _Segment(2.0, 3.0, "Merci.")]
            return iter(segments), types.SimpleNamespace(language="fr")

    module = types.ModuleType("faster_whisper")
    module.WhisperModel, module.BatchedInferencePipeline = WhisperModel, BatchedInferencePipeline
    backend.setitem(sys.modules, "faster_whisper", module)
    from subtitle_models.whisper import TritonPythonModel

    def make(**parameters):
        model = TritonPythonModel()
        model.initialize(_args("whisper_medium", whisper_model="medium", **parameters))
        return model

    return make, seen


def _run(model, request):
    assert model.execute([request]) is None  # decoupled: answers go through the sender
    model.finalize()  # waits for the worker threads
    return request.sender.sent


def test_whisper_streams_language_then_segments_then_final(whisper):
    make, seen = whisper
    sent = _run(make(language="", batch_size="8"), Request(AUDIO=np.array([16384, -32768], dtype=np.int16)))

    assert seen["model"] == "medium" and seen["options"]["compute_type"] == "int8"
    assert seen["audio"].tolist() == [0.5, -1.0] and seen["language"] is None and seen["batch_size"] == 8
    outputs = [response.outputs for response, _ in sent[:-1]]
    assert outputs[0]["LANGUAGE"].tolist() == [b"fr"]
    assert [(o["START"][0], o["END"][0], o["TEXT"][0]) for o in outputs[1:]] == [
        (0.0, 1.5, b"Bonjour."), (2.0, 3.0, b"Merci."),  # blank segment skipped
    ]
    assert sent[-1] == (None, 1)  # final flag


def test_english_model_keeps_its_fixed_language(whisper):
    make, seen = whisper
    sent = _run(make(language="en"), Request(AUDIO=np.zeros(4, dtype=np.int16)))
    assert seen["language"] == "en"
    assert sent[0][0].outputs["LANGUAGE"].tolist() == [b"en"]


def test_cancelled_request_stops_between_segments(whisper):
    make, _ = whisper
    sent = _run(make(), Request(cancel_after=1, AUDIO=np.zeros(4, dtype=np.int16)))
    texts = [r.outputs["TEXT"][0] for r, _ in sent if r is not None and "TEXT" in r.outputs]
    assert texts == [b"Bonjour."] and sent[-1] == (None, 1)


def test_failure_is_sent_as_an_error_response(whisper):
    make, _ = whisper
    sent = _run(make(), Request(AUDIO=np.zeros(0, dtype=np.int16)))
    response, flags = sent[-1]
    assert response.error.message == "empty audio" and flags == 1


# --- translator ------------------------------------------------------------------------

@pytest.fixture
def translator(backend, tmp_path):
    for name in ("opus-mt-en-fr", "opus-mt-en-zh"):
        (tmp_path / name).mkdir()
        (tmp_path / name / "model.bin").write_bytes(b"x")

    class Translator:
        def __init__(self, path, **options):
            self.lang = Path(path).name[-2:]

        def translate_batch(self, batches, beam_size, max_batch_size):
            return [types.SimpleNamespace(hypotheses=[[f"<{self.lang}>", *tokens]]) for tokens in batches]

    class SentencePieceProcessor:
        def __init__(self, path):
            pass

        def encode(self, text, out_type):
            return text.split()

        def decode(self, tokens):
            return " ".join(tokens)

    backend.setitem(sys.modules, "ctranslate2", types.SimpleNamespace(Translator=Translator))
    backend.setitem(sys.modules, "sentencepiece", types.SimpleNamespace(SentencePieceProcessor=SentencePieceProcessor))
    from subtitle_models.translator import TritonPythonModel

    model = TritonPythonModel()
    model.initialize(_args("translator", models_dir=str(tmp_path)))
    return model


def _strings(*values):
    return np.array([v.encode("utf-8") for v in values], dtype=np.object_)


def test_translator_loads_the_models_present(translator):
    assert sorted(translator.translators) == ["fr", "zh"]


def test_translator_routes_to_the_target_and_adds_the_variant_token(translator):
    fr, zh = translator.execute([
        Request(TEXT=_strings("Hello there"), TARGET=_strings("fr")),
        Request(TEXT=_strings("Hi"), TARGET=_strings("zh")),
    ])
    assert fr.outputs["TRANSLATION"].tolist() == [b"<fr> Hello there </s>"]
    assert zh.outputs["TRANSLATION"].tolist() == [b"<zh> >>cmn_Hans<< Hi </s>"]


def test_unknown_target_is_an_error_not_a_crash(translator):
    (response,) = translator.execute([Request(TEXT=_strings("Hello"), TARGET=_strings("de"))])
    assert "no translator to 'de'" in response.error.message
