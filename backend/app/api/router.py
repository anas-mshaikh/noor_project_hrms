from fastapi import APIRouter

from app.api.v1.health import router as health_router
from app.api.v1.jobs import router as jobs_router
from app.api.v1.videos import router as videos_router
from app.api.v1.results import router as results_router
from app.api.v1.cameras import router as cameras_router
from app.api.v1.organizations import router as organizations_router
from app.api.v1.stores import router as stores_router
from app.api.v1.employees import router as employees_router
from app.api.v1.imports import router as imports_router
from app.api.v1.openings import router as openings_router
from app.api.v1.screening_runs import router as screening_runs_router
from app.api.v1.ats import router as ats_router
from app.api.v1.onboarding import router as onboarding_router
from app.face_system.api import router as face_router
from app.mobile.accounts_router import router as mobile_accounts_router
from app.mobile.router import router as mobile_router


api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(videos_router)
api_router.include_router(jobs_router)
api_router.include_router(results_router)
api_router.include_router(cameras_router)
api_router.include_router(organizations_router)
api_router.include_router(stores_router)
api_router.include_router(employees_router)
api_router.include_router(imports_router)
api_router.include_router(openings_router)
api_router.include_router(screening_runs_router)
api_router.include_router(ats_router)
api_router.include_router(onboarding_router)
api_router.include_router(face_router)
api_router.include_router(mobile_router)
api_router.include_router(mobile_accounts_router)
