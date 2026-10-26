import os
from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    project_name: str = "API de prédiction cardiaque"
    version: str = "1.0.0"
    api_v1_prefix: str = "/api/v1"
    model_path: Path = Path(
        os.getenv("MODEL_PATH", BASE_DIR / "datascience_model" / "first_model.sav")
    )


settings = Settings()
