from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.domains.hr_core import repo, repo_mss
from app.domains.hr_core.policies import project_employee_360_mss
from app.domains.hr_core.schemas import MSSEmployeeProfileOut, MSSEmployeeSummaryOut
from app.shared.types import AuthContext


class MSSService:
    def _resolve_actor(self, db: Session, *, ctx: AuthContext) -> repo_mss.ActorEmployeeContext:
        actor = repo_mss.get_actor_employee_context(db, user_id=ctx.user_id)
        if actor is None:
            raise AppError(code="mss.not_linked", message="User is not linked to an employee", status_code=409)

        current = repo.get_current_employment(db, tenant_id=actor.tenant_id, company_id=actor.company_id, employee_id=actor.employee_id)
        if current is None:
            raise AppError(code="mss.no_current_employment", message="Employee has no current employment", status_code=409)

        return actor

    def list_team(
        self,
        db: Session,
        *,
        ctx: AuthContext,
        depth: str,
        q: str | None,
        status: str | None,
        branch_id: UUID | None,
        org_unit_id: UUID | None,
        limit: int,
        offset: int,
    ) -> tuple[list[MSSEmployeeSummaryOut], int]:
        if depth not in {"1", "all"}:
            raise AppError(code="mss.invalid_depth", message="depth must be '1' or 'all'", status_code=400)

        actor = self._resolve_actor(db, ctx=ctx)

        norm_status: str | None = None
        if status:
            s = status.strip().upper()
            if s == "DISABLED":
                s = "INACTIVE"
            norm_status = s

        rows, total = repo_mss.list_team_directory(
            db,
            tenant_id=actor.tenant_id,
            company_id=actor.company_id,
            actor_employee_id=actor.employee_id,
            depth_mode=depth,
            q=q,
            status=norm_status,
            branch_id=branch_id,
            org_unit_id=org_unit_id,
            limit=limit,
            offset=offset,
        )

        items = [
            MSSEmployeeSummaryOut(
                employee_id=r.employee_id,
                employee_code=r.employee_code,
                display_name=f"{r.first_name} {r.last_name}".strip(),
                status=r.status,  # type: ignore[arg-type]
                branch_id=r.branch_id,
                org_unit_id=r.org_unit_id,
                job_title_id=r.job_title_id,
                grade_id=r.grade_id,
                manager_employee_id=r.manager_employee_id,
                relationship_depth=r.relationship_depth,
            )
            for r in rows
        ]
        return items, total

    def get_team_member_profile(
        self,
        db: Session,
        *,
        ctx: AuthContext,
        employee_id: UUID,
    ) -> MSSEmployeeProfileOut:
        actor = self._resolve_actor(db, ctx=ctx)

        allowed = repo_mss.is_in_manager_subtree(
            db,
            tenant_id=actor.tenant_id,
            company_id=actor.company_id,
            actor_employee_id=actor.employee_id,
            target_employee_id=employee_id,
        )
        if not allowed:
            raise AppError(code="mss.forbidden_employee", message="Employee is not in your reporting tree", status_code=403)

        row = repo.get_employee_360_by_id(db, tenant_id=actor.tenant_id, company_id=actor.company_id, employee_id=employee_id)
        if row is None:
            raise AppError(code="hr.employee.not_found", message="Employee not found", status_code=404)

        return project_employee_360_mss(row)

