from fastapi import APIRouter

from ...routers import prediction

api_router = APIRouter()
api_router.include_router(prediction.router)
