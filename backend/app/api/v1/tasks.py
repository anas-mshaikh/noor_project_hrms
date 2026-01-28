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

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.models import (
    Employee,
    SkillTaxonomy,
    Store,
    TaskAssignment,
    TaskRequiredSkill,
    WorkTask,
)
from app.work.queue import get_work_queue
from app.work.tasks import assign_tasks_job


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
    store_id: UUID
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
    store_id: UUID
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
        store_id=t.store_id,
        name=t.name,
        task_type=t.task_type,
        priority=t.priority,
        status=t.status,
        window_start=t.window_start,
        window_end=t.window_end,
        created_at=t.created_at,
    )


def _assignment_out(a: TaskAssignment, *, employee: Employee) -> AssignmentOut:
    return AssignmentOut(
        id=a.id,
        task_id=a.task_id,
        employee_id=a.employee_id,
        employee_code=employee.employee_code,
        employee_name=employee.name,
        assigned_by=a.assigned_by,
        score=a.score,
        assigned_at=a.assigned_at,
        started_at=a.started_at,
        completed_at=a.completed_at,
    )


# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------


@router.post(
    "/stores/{store_id}/tasks",
    response_model=TaskOut,
    status_code=status.HTTP_201_CREATED,
)
def create_task(
    store_id: UUID, body: TaskCreateRequest, db: Session = Depends(get_db)
) -> TaskOut:
    store = db.get(Store, store_id)
    if store is None:
        raise HTTPException(status_code=404, detail="Store not found")

    task = WorkTask(
        id=uuid4(),
        store_id=store_id,
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
            raise HTTPException(status_code=400, detail="skill code cannot be empty")

        skill = db.query(SkillTaxonomy).filter(SkillTaxonomy.code == code).one_or_none()
        if skill is None:
            skill = SkillTaxonomy(
                id=uuid4(),
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
    return _task_out(task)


@router.get("/stores/{store_id}/tasks", response_model=list[TaskOut])
def list_tasks(store_id: UUID, db: Session = Depends(get_db)) -> list[TaskOut]:
    store = db.get(Store, store_id)
    if store is None:
        raise HTTPException(status_code=404, detail="Store not found")

    tasks = (
        db.query(WorkTask)
        .filter(WorkTask.store_id == store_id)
        .order_by(WorkTask.created_at.desc())
        .all()
    )
    return [_task_out(t) for t in tasks]


@router.post(
    "/stores/{store_id}/tasks/auto-assign",
    response_model=AutoAssignResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def auto_assign_tasks(
    store_id: UUID, body: AutoAssignRequest, db: Session = Depends(get_db)
) -> AutoAssignResponse:
    store = db.get(Store, store_id)
    if store is None:
        raise HTTPException(status_code=404, detail="Store not found")

    q = get_work_queue()
    job = q.enqueue(
        assign_tasks_job,
        kwargs={"store_id": str(store_id), "business_date": body.business_date.isoformat()},
    )
    return AutoAssignResponse(
        store_id=store_id, business_date=body.business_date, rq_job_id=str(job.id)
    )


@router.get("/tasks/{task_id}/assignments", response_model=list[AssignmentOut])
def get_task_assignments(
    task_id: UUID, db: Session = Depends(get_db)
) -> list[AssignmentOut]:
    task = db.get(WorkTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    rows = (
        db.query(TaskAssignment, Employee)
        .join(Employee, Employee.id == TaskAssignment.employee_id)
        .filter(TaskAssignment.task_id == task_id)
        .order_by(TaskAssignment.assigned_at.desc())
        .all()
    )

    return [_assignment_out(a, employee=e) for (a, e) in rows]
