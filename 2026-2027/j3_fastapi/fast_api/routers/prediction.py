from fastapi import APIRouter, Depends, Request

from ..schemas.prediction import PredictionInput, PredictionOutput
from ..services.prediction_service import PredictionService

router = APIRouter(prefix="/predict", tags=["prediction"])


def get_prediction_service(request: Request) -> PredictionService:
    return request.app.state.prediction_service


@router.post("", response_model=PredictionOutput)
def predict(
    data: PredictionInput,
    service: PredictionService = Depends(get_prediction_service),
) -> PredictionOutput:
    return service.predict(data)
