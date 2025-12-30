from fastapi import APIRouter

from app.api.v1.health import router as health_router
from app.api.v1.jobs import router as jobs_router
from app.api.v1.videos import router as videos_router
from app.api.v1.results import router as results_router
from app.api.v1.cameras import router as cameras_router


api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(videos_router)
api_router.include_router(jobs_router)
api_router.include_router(results_router)
api_router.include_router(cameras_router)
