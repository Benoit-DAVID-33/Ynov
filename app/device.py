"""Where the models run: CPU or NVIDIA GPU, chosen at launch with DEVICE."""

import os
import sys
from functools import lru_cache
from pathlib import Path

from app.config import Settings

_GPU_HELP = (
    "DEVICE=gpu mais aucun GPU NVIDIA n'est utilisable. Vérifiez le pilote NVIDIA "
    "(nvidia-smi), les bibliothèques CUDA (pip install -r requirements-gpu.txt) et, sous "
    "Docker, le NVIDIA Container Toolkit ; ou relancez avec DEVICE=cpu."
)


def _expose_nvidia_dlls() -> None:
    """Windows only: make the cuBLAS / cuDNN DLLs installed by pip loadable.

    On Linux the equivalent is LD_LIBRARY_PATH, set in the Dockerfile.
    """
    if sys.platform != "win32":
        return
    for site in map(Path, sys.path):
        for bin_dir in site.glob("nvidia/*/bin"):
            os.add_dll_directory(str(bin_dir))
            os.environ["PATH"] = f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"


@lru_cache
def _cuda_available() -> bool:
    _expose_nvidia_dlls()
    import ctranslate2

    return ctranslate2.get_cuda_device_count() > 0


def resolve_device(settings: Settings) -> str:
    """"cuda" or "cpu". An explicit GPU request never silently falls back to the CPU."""
    if settings.wants_gpu:
        if not _cuda_available():
            raise RuntimeError(_GPU_HELP)
        return "cuda"
    if settings.device == "auto" and _cuda_available():
        return "cuda"
    return "cpu"


def compute_type(device: str) -> str:
    # Half precision on GPU; 8-bit quantisation is what makes the CPU fast enough.
    return "float16" if device == "cuda" else "int8"
