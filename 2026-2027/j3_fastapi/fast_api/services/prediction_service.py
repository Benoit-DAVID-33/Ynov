import pickle
from pathlib import Path

import pandas as pd

from ..schemas.prediction import PredictionInput, PredictionOutput

LABELS = ["Bonne santé", "Malade"]


class PredictionService:
    def __init__(self, model_path: Path):
        with open(model_path, "rb") as f:
            self.model = pickle.load(f)

    def predict(self, data: PredictionInput) -> PredictionOutput:
        features = pd.DataFrame([{"age": data.age, "sex": data.sex}])
        prediction = int(self.model.predict(features)[0])
        return PredictionOutput(prediction=prediction, label=LABELS[prediction])
