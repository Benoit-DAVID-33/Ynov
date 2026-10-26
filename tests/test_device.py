import pytest

from app import device
from app.config import Settings


def _settings(**values):
    return Settings(_env_file=None, **values)


@pytest.fixture
def cuda(monkeypatch):
    """Pretend an NVIDIA GPU is (or is not) usable."""

    def _set(available):
        monkeypatch.setattr(device, "_cuda_available", lambda: available)

    return _set


def test_cpu_is_used_when_asked_even_if_a_gpu_is_there(cuda):
    cuda(True)
    assert device.resolve_device(_settings(device="cpu")) == "cpu"


def test_gpu_request_without_usable_gpu_fails_instead_of_falling_back(cuda):
    cuda(False)
    with pytest.raises(RuntimeError, match="DEVICE=gpu"):
        device.resolve_device(_settings(device="gpu"))


def test_gpu_request_uses_the_gpu(cuda):
    cuda(True)
    assert device.resolve_device(_settings(device="gpu")) == "cuda"
    assert device.resolve_device(_settings(device="cuda")) == "cuda"


def test_auto_picks_the_gpu_only_when_usable(cuda):
    cuda(False)
    assert device.resolve_device(_settings(device="auto")) == "cpu"
    cuda(True)
    assert device.resolve_device(_settings(device="auto")) == "cuda"


def test_precision_follows_the_device():
    assert (device.compute_type("cuda"), device.compute_type("cpu")) == ("float16", "int8")


def test_default_model_and_batch_follow_the_device():
    cpu, gpu = _settings(device="cpu"), _settings(device="gpu")
    assert (cpu.effective_default_model, cpu.effective_batch_size) == ("whisper-small.en", 8)
    assert (gpu.effective_default_model, gpu.effective_batch_size) == ("whisper-medium.en", 16)


def test_explicit_settings_win_over_the_device_defaults():
    custom = _settings(device="gpu", default_model="whisper-small", batch_size=4)
    assert (custom.effective_default_model, custom.effective_batch_size) == ("whisper-small", 4)


def test_unknown_device_is_rejected():
    with pytest.raises(ValueError):
        _settings(device="tpu")
