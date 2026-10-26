from typing import Literal

from pydantic import BaseModel, Field


class PredictionInput(BaseModel):
    age: int = Field(ge=0, le=120, examples=[57])
    sex: Literal[0, 1] = Field(examples=[1], description="Même codage que heart.csv")


class PredictionOutput(BaseModel):
    prediction: Literal[0, 1]
    label: str
