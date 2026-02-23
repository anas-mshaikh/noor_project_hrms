from fastapi import APIRouter

from app.api.v1.health import router as health_router
from app.api.v1.jobs import router as jobs_router
from app.api.v1.videos import router as videos_router
from app.api.v1.results import router as results_router
from app.api.v1.cameras import router as cameras_router
from app.api.v1.imports import router as imports_router
from app.api.v1.openings import router as openings_router
from app.api.v1.screening_runs import router as screening_runs_router
from app.api.v1.ats import router as ats_router
from app.api.v1.tasks import router as tasks_router
from app.face_system.api import router as face_router
from app.mobile.accounts_router import router as mobile_accounts_router
from app.mobile.router import router as mobile_router
from app.auth.router import router as auth_router
from app.domains.notifications.router import router as notifications_router
from app.domains.tenancy.router import router as tenancy_router
from app.domains.iam.router import router as iam_router
from app.domains.hr_core.router_hr import router as hr_core_hr_router
from app.domains.hr_core.router_ess import router as hr_core_ess_router
from app.domains.hr_core.router_mss import router as hr_core_mss_router
from app.domains.leave.router_ess import router as leave_ess_router
from app.domains.leave.router_hr import router as leave_hr_router
from app.domains.leave.router_mss import router as leave_mss_router
from app.domains.attendance.router_ess import router as attendance_ess_router
from app.domains.attendance.router_admin import router as attendance_admin_router
from app.domains.attendance.router_mss import router as attendance_mss_router
from app.domains.roster.router import router as roster_router
from app.domains.dms.router_files import router as dms_files_router
from app.domains.dms.router_document_types import router as dms_document_types_router
from app.domains.dms.router_documents import router as dms_documents_router
from app.domains.dms.router_hr import router as dms_hr_router
from app.domains.dms.router_ess import router as dms_ess_router
from app.domains.dms.router_expiry import router as dms_expiry_router
from app.domains.profile_change.router_ess import router as profile_change_ess_router
from app.domains.profile_change.router_hr import router as profile_change_hr_router
from app.domains.onboarding.router_hr import router as onboarding_hr_router
from app.domains.onboarding.router_ess import router as onboarding_ess_router
from app.domains.workflow.router import router as workflow_router
from app.domains.payroll.router_admin import router as payroll_admin_router
from app.domains.payroll.router_ess import router as payroll_ess_router


api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(videos_router)
api_router.include_router(jobs_router)
api_router.include_router(results_router)
api_router.include_router(cameras_router)
api_router.include_router(imports_router)
api_router.include_router(openings_router)
api_router.include_router(screening_runs_router)
api_router.include_router(ats_router)
api_router.include_router(tasks_router)
api_router.include_router(face_router)
api_router.include_router(mobile_router)
api_router.include_router(mobile_accounts_router)
api_router.include_router(auth_router)
api_router.include_router(notifications_router)
api_router.include_router(tenancy_router)
api_router.include_router(iam_router)
api_router.include_router(hr_core_hr_router)
api_router.include_router(hr_core_ess_router)
api_router.include_router(hr_core_mss_router)
api_router.include_router(leave_ess_router)
api_router.include_router(leave_hr_router)
api_router.include_router(leave_mss_router)
api_router.include_router(attendance_ess_router)
api_router.include_router(attendance_admin_router)
api_router.include_router(attendance_mss_router)
api_router.include_router(roster_router)
api_router.include_router(dms_files_router)
api_router.include_router(dms_document_types_router)
api_router.include_router(dms_documents_router)
api_router.include_router(dms_hr_router)
api_router.include_router(dms_ess_router)
api_router.include_router(dms_expiry_router)
api_router.include_router(profile_change_ess_router)
api_router.include_router(profile_change_hr_router)
api_router.include_router(onboarding_hr_router)
api_router.include_router(onboarding_ess_router)
api_router.include_router(workflow_router)
api_router.include_router(payroll_admin_router)
api_router.include_router(payroll_ess_router)
