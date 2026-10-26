from contextlib import asynccontextmanager

from fastapi import FastAPI

from .api.v1.api import api_router
from .core.config import settings
from .services.prediction_service import PredictionService


@asynccontextmanager
async def lifespan(app: FastAPI):
    # le modèle est chargé une seule fois au démarrage
    app.state.prediction_service = PredictionService(settings.model_path)
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.project_name,
        version=settings.version,
        lifespan=lifespan,
    )
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    @app.get("/health", tags=["health"])
    def health():
        return {"status": "ok"}

    return app


app = create_app()
