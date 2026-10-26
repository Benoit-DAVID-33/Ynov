from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


# What changes with the device. A GPU affords the bigger model and bigger
# batches; on CPU the small model is the one that stays faster than real time
# with 10 simultaneous users (measures in docs/ARCHITECTURE.md).
DEVICE_DEFAULTS = {
    "cpu": {"default_model": "whisper-small.en", "batch_size": 8},
    "gpu": {"default_model": "whisper-medium.en", "batch_size": 16},
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # PostgreSQL only. The default matches the development database of .env.example.
    database_url: str = "postgresql+psycopg://subtitle:subtitle@127.0.0.1:5432/subtitle"
    storage_dir: Path = Path("./data")
    max_upload_mb: int = 2048
    # Cost (compute time, memory) grows with the duration, not with the file size.
    max_duration_s: float = 7200.0
    # Resumable uploads: size of the chunks sent by the browser, and how long an
    # unfinished upload is kept before its bytes are dropped.
    upload_chunk_mb: int = 8
    upload_session_hours: float = 24.0
    # Queue admission. A new job is refused when the media already waiting or
    # being processed (in seconds, counting only what is left of running jobs)
    # plus its own duration exceed this. Rule of thumb: this many seconds of
    # media take (compute time / media duration) times as long to clear.
    max_pending_media_s: float = 14400.0
    max_pending_jobs_per_visitor: int = 4
    # Each user keeps the files of their latest upload only; even those are
    # deleted after this many days (0 = never).
    retention_days: float = 7.0

    # Comma-separated names from the transcriber registry, exposed to users.
    enabled_models: str = "whisper-medium.en,whisper-small.en,whisper-medium,whisper-small"
    # Empty = chosen from the device, see DEVICE_DEFAULTS.
    default_model: str = ""
    # Comma-separated names from the translator registry.
    enabled_translators: str = "opus-mt-en-fr"
    translation_models_dir: Path = Path("./models")
    # Optional name from the speaker identifier registry.
    speaker_identifier: str = ""
    # Where the models run. "auto" uses an NVIDIA GPU when one is usable; "gpu"
    # requires one and fails clearly otherwise.
    device: Literal["auto", "cpu", "gpu", "cuda"] = "auto"
    batch_size: int = 0  # 0 = chosen from the device
    cpu_threads: int = 0  # CPU inference only; 0 = library default
    # x264 preset for burned-in subtitles: faster presets trade file size for speed.
    # superfast is the slowest one that met the 10-user target on the CPU-only
    # reference machine (see docs/ARCHITECTURE.md).
    burn_preset: Literal["ultrafast", "superfast", "veryfast", "faster", "fast", "medium"] = "superfast"

    # Accounts. A login session lasts this many days; behind an HTTPS reverse proxy that
    # hides the scheme from the application, cookie_secure forces the Secure flag.
    session_days: float = 30.0
    cookie_secure: bool = False
    # Accounts created per hour from one IP address (behind a proxy, everyone shares it).
    max_registrations_per_hour: int = 20
    # Admin console (separate service). The first administrator account is created from
    # these two values when no administrator exists yet; later changes are ignored
    # (use `python -m app.users`). An empty password is replaced by a random one,
    # printed once on the console's standard error.
    admin_username: str = "admin"
    admin_password: str = ""
    # Where the admin console probes the user-facing API.
    api_url: str = "http://localhost:8000"

    # Jobs processed at the same time by one worker.
    worker_concurrency: int = 3
    # Among them, slots that only take media shorter than fast_lane_max_s, so
    # that a short file never waits behind long ones.
    fast_lane_slots: int = 1
    fast_lane_max_s: float = 300.0
    poll_interval_s: float = 1.0
    heartbeat_interval_s: float = 10.0
    stale_after_s: float = 60.0
    max_attempts: int = 3

    @property
    def wants_gpu(self) -> bool:
        return self.device in ("gpu", "cuda")

    @property
    def _device_defaults(self) -> dict:
        return DEVICE_DEFAULTS["gpu" if self.wants_gpu else "cpu"]

    @property
    def effective_default_model(self) -> str:
        return self.default_model or self._device_defaults["default_model"]

    @property
    def effective_batch_size(self) -> int:
        return self.batch_size or self._device_defaults["batch_size"]

    @property
    def model_names(self) -> list[str]:
        return _split(self.enabled_models)

    @property
    def translator_names(self) -> list[str]:
        return _split(self.enabled_translators)

    @property
    def uploads_dir(self) -> Path:
        return self.storage_dir / "uploads"

    @property
    def partial_dir(self) -> Path:
        return self.storage_dir / "partial"

    @property
    def results_dir(self) -> Path:
        return self.storage_dir / "results"

    @property
    def logs_dir(self) -> Path:
        return self.storage_dir / "logs"


def _split(names: str) -> list[str]:
    return [n.strip() for n in names.split(",") if n.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
