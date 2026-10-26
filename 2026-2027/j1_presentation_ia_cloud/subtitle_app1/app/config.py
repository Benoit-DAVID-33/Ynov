import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    transcriber: str
    whisper_model: str
    device: str
    workers: int
    max_upload_mb: int
    admin_token: str

    @property
    def jobs_dir(self) -> Path:
        return self.data_dir / "jobs"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "jobs.db"

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            data_dir=Path(os.getenv("DATA_DIR", "data")),
            transcriber=os.getenv("TRANSCRIBER", "whisper"),
            whisper_model=os.getenv("WHISPER_MODEL", "openai/whisper-medium"),
            device=os.getenv("DEVICE", "auto"),
            workers=int(os.getenv("WORKERS", "1")),
            max_upload_mb=int(os.getenv("MAX_UPLOAD_MB", "500")),
            admin_token=os.getenv("ADMIN_TOKEN", ""),
        )
