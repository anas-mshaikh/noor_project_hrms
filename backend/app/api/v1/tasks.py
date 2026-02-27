"""
tasks.py (Work module - Phase 1: Auto Task Assignment)

This router adds a NEW "work" domain for operational task management and a
deterministic auto-assignment job.

Key properties:
- explainable: assignment scores are derived from simple rules
- auditable: assignments are append-only rows in work.task_assignments
- recomputable: rerunning auto-assign is safe (idempotent) for pending tasks

IMPORTANT:
- This does NOT touch existing CCTV job routes/tables.
- This is Phase 1 only: no ML, no embeddings, no skill inference.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import UUID, uuid4

import sqlalchemy as sa
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.deps import require_permission
from app.auth.permissions import WORK_TASK_AUTO_ASSIGN, WORK_TASK_READ, WORK_TASK_WRITE
from app.core.errors import AppError
from app.core.responses import ok
from app.db.session import get_db
from app.models.models import (
    SkillTaxonomy,
    TaskRequiredSkill,
    WorkTask,
)
from app.work.queue import get_work_queue
from app.work.tasks import assign_tasks_job
from app.shared.types import AuthContext


router = APIRouter(tags=["tasks"])


def _utc_today() -> date:
    return datetime.now(timezone.utc).date()


# -----------------------------------------------------------------------------
# Pydantic schemas
# -----------------------------------------------------------------------------


class RequiredSkillIn(BaseModel):
    code: str = Field(..., description="Skill code (skills.skill_taxonomy.code)")
    name: str | None = Field(
        default=None,
        description="Optional human-friendly name (only used if we create the skill).",
    )
    category: str | None = Field(
        default=None,
        description="Optional category (only used if we create the skill).",
    )
    min_proficiency: int = 1
    required: bool = True


class TaskCreateRequest(BaseModel):
    name: str
    task_type: str | None = None
    priority: int = 3
    window_start: datetime | None = None
    window_end: datetime | None = None
    required_skills: list[RequiredSkillIn] = Field(default_factory=list)


class TaskOut(BaseModel):
    id: UUID
    tenant_id: UUID
    branch_id: UUID
    name: str
    task_type: str | None
    priority: int
    status: str
    window_start: datetime | None
    window_end: datetime | None
    created_at: datetime


class AutoAssignRequest(BaseModel):
    business_date: date = Field(default_factory=_utc_today)


class AutoAssignResponse(BaseModel):
    tenant_id: UUID
    branch_id: UUID
    business_date: date
    rq_job_id: str


class AssignmentOut(BaseModel):
    id: UUID
    task_id: UUID
    employee_id: UUID
    employee_code: str
    employee_name: str
    assigned_by: str
    score: float
    assigned_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------


def _task_out(t: WorkTask) -> TaskOut:
    return TaskOut(
        id=t.id,
        tenant_id=t.tenant_id,
        branch_id=t.branch_id,
        name=t.name,
        task_type=t.task_type,
        priority=t.priority,
        status=t.status,
        window_start=t.window_start,
        window_end=t.window_end,
        created_at=t.created_at,
    )


# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------


@router.post(
    "/branches/{branch_id}/tasks",
    status_code=status.HTTP_201_CREATED,
)
def create_task(
    branch_id: UUID,
    body: TaskCreateRequest,
    ctx: AuthContext = Depends(require_permission(WORK_TASK_WRITE)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    task = WorkTask(
        id=uuid4(),
        tenant_id=ctx.scope.tenant_id,
        branch_id=branch_id,
        name=body.name,
        task_type=body.task_type,
        priority=body.priority,
        status="pending",
        window_start=body.window_start,
        window_end=body.window_end,
    )
    db.add(task)

    # Upsert skill taxonomy entries (Phase 1 convenience).
    # This avoids requiring a separate UI just to seed skills.
    for s in body.required_skills:
        code = s.code.strip()
        if not code:
            raise AppError(code="validation_error", message="skill code cannot be empty", status_code=400)

        skill = (
            db.query(SkillTaxonomy)
            .filter(SkillTaxonomy.tenant_id == ctx.scope.tenant_id, SkillTaxonomy.code == code)
            .one_or_none()
        )
        if skill is None:
            skill = SkillTaxonomy(
                id=uuid4(),
                tenant_id=ctx.scope.tenant_id,
                code=code,
                name=(s.name or code),
                category=s.category,
            )
            db.add(skill)

        req = TaskRequiredSkill(
            task_id=task.id,
            skill_id=skill.id,
            min_proficiency=s.min_proficiency,
            required=s.required,
        )
        db.add(req)

    db.commit()
    db.refresh(task)
    return ok(_task_out(task).model_dump())


@router.get("/branches/{branch_id}/tasks")
def list_tasks(
    branch_id: UUID,
    ctx: AuthContext = Depends(require_permission(WORK_TASK_READ)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    tasks = (
        db.query(WorkTask)
        .filter(
            WorkTask.tenant_id == ctx.scope.tenant_id,
            WorkTask.branch_id == branch_id,
        )
        .order_by(WorkTask.created_at.desc())
        .all()
    )
    return ok([_task_out(t).model_dump() for t in tasks])


@router.post(
    "/branches/{branch_id}/tasks/auto-assign",
    status_code=status.HTTP_202_ACCEPTED,
)
def auto_assign_tasks(
    branch_id: UUID,
    body: AutoAssignRequest,
    ctx: AuthContext = Depends(require_permission(WORK_TASK_AUTO_ASSIGN)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    q = get_work_queue()
    job = q.enqueue(
        assign_tasks_job,
        kwargs={
            "tenant_id": str(ctx.scope.tenant_id),
            "branch_id": str(branch_id),
            "business_date": body.business_date.isoformat(),
        },
    )
    return ok(
        AutoAssignResponse(
            tenant_id=ctx.scope.tenant_id,
            branch_id=branch_id,
            business_date=body.business_date,
            rq_job_id=str(job.id),
        ).model_dump()
    )


@router.get("/branches/{branch_id}/tasks/{task_id}/assignments")
def get_task_assignments(
    branch_id: UUID,
    task_id: UUID,
    ctx: AuthContext = Depends(require_permission(WORK_TASK_READ)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    task = (
        db.query(WorkTask)
        .filter(
            WorkTask.id == task_id,
            WorkTask.tenant_id == ctx.scope.tenant_id,
            WorkTask.branch_id == branch_id,
        )
        .first()
    )
    if task is None:
        raise AppError(code="tasks.task.not_found", message="Task not found", status_code=404)

    rows = db.execute(
        sa.text(
            """
            SELECT
              a.id AS id,
              a.task_id AS task_id,
              a.employee_id AS employee_id,
              e.employee_code AS employee_code,
              p.first_name AS first_name,
              p.last_name AS last_name,
              a.assigned_by AS assigned_by,
              a.score AS score,
              a.assigned_at AS assigned_at,
              a.started_at AS started_at,
              a.completed_at AS completed_at
            FROM work.task_assignments a
            JOIN work.tasks t ON t.id = a.task_id
            JOIN hr_core.employees e ON e.id = a.employee_id
            JOIN hr_core.persons p ON p.id = e.person_id
            WHERE a.task_id = :task_id
              AND t.tenant_id = :tenant_id
              AND t.branch_id = :branch_id
            ORDER BY a.assigned_at DESC, a.id DESC
            """
        ),
        {"task_id": task_id, "tenant_id": ctx.scope.tenant_id, "branch_id": branch_id},
    ).all()

    out: list[AssignmentOut] = []
    for r in rows:
        full_name = f"{r.first_name} {r.last_name}".strip()
        out.append(
            AssignmentOut(
                id=r.id,
                task_id=r.task_id,
                employee_id=r.employee_id,
                employee_code=r.employee_code,
                employee_name=full_name,
                assigned_by=r.assigned_by,
                score=float(r.score),
                assigned_at=r.assigned_at,
                started_at=r.started_at,
                completed_at=r.completed_at,
            )
        )
    return ok([x.model_dump() for x in out])
