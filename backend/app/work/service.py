from __future__ import annotations

"""
Deterministic, rules-based task assignment (Phase 1).

Goals:
- Explainable: scores are derived from simple, human-readable rules.
- Auditable: every assignment is persisted in `work.task_assignments`.
- Recomputable: rerunning the same job over the same inputs is safe and repeatable.

Important constraints:
- NO machine learning in Phase 1.
- Do not modify existing attendance logic; we only *read* attendance to inform availability.
"""

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.models import (
    AttendanceDaily,
    Employee,
    EmployeeSkill,
    TaskAssignment,
    TaskRequiredSkill,
    WorkTask,
)

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class CandidateScore:
    """
    In-memory candidate score used during one assignment decision.

    `score` is persisted on the TaskAssignment row for audit/debug.
    """

    employee_id: UUID
    employee_code: str
    employee_name: str
    score: float
    base_skill_score: float
    active_assignment_count: int
    is_present: bool | None  # True/False/Unknown


class AutoTaskAssigner:
    """
    Service class that implements Phase-1 deterministic auto assignment.
    """

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def assign_pending_tasks_for_store(
        self, *, store_id: UUID, business_date: date
    ) -> dict[str, int]:
        """
        Attempt to assign all pending tasks for a store for the given business date.

        Idempotency:
        - We only consider tasks in status='pending'.
        - Once assigned, we set status='assigned', so re-running won't duplicate.
        """

        tasks = self._get_pending_tasks_for_date(store_id=store_id, business_date=business_date)

        assigned = 0
        skipped = 0
        no_eligible = 0

        for task in tasks:
            if task.status != "pending":
                skipped += 1
                continue

            # Avoid creating duplicate assignment rows if the task was already assigned
            # but the status wasn't updated due to a prior crash/rollback.
            existing = (
                self.db.query(TaskAssignment.id)
                .filter(TaskAssignment.task_id == task.id)
                .limit(1)
                .first()
            )
            if existing is not None:
                skipped += 1
                continue

            assignment = self.assign_task(task_id=task.id, business_date=business_date)
            if assignment is None:
                no_eligible += 1
                continue
            assigned += 1

        return {
            "total": len(tasks),
            "assigned": assigned,
            "skipped": skipped,
            "no_eligible": no_eligible,
        }

    def assign_task(self, *, task_id: UUID, business_date: date) -> TaskAssignment | None:
        """
        Attempt to assign a single task.

        Returns the created TaskAssignment row, or None if no eligible employees exist.
        """

        task = self.db.get(WorkTask, task_id)
        if task is None:
            raise ValueError("task not found")

        if task.status != "pending":
            return None

        required_skills = (
            self.db.query(TaskRequiredSkill)
            .filter(TaskRequiredSkill.task_id == task.id)
            .all()
        )

        candidates = self._score_candidates(
            store_id=task.store_id,
            business_date=business_date,
            required_skills=required_skills,
        )

        if not candidates:
            return None

        best = self._pick_best_candidate(candidates)
        if best is None:
            return None

        now = _utcnow()
        assignment = TaskAssignment(
            task_id=task.id,
            employee_id=best.employee_id,
            assigned_by="auto",
            score=best.score,
            assigned_at=now,
        )

        task.status = "assigned"
        self.db.add(assignment)
        self.db.add(task)
        self.db.commit()
        self.db.refresh(assignment)
        return assignment

    # ------------------------------------------------------------------
    # Internal helpers (querying + scoring)
    # ------------------------------------------------------------------

    def _get_pending_tasks_for_date(
        self, *, store_id: UUID, business_date: date
    ) -> list[WorkTask]:
        """
        Fetch pending tasks for a store + date.

        We treat the "effective date" as:
        - window_start date if provided
        - otherwise, include tasks with no window_start (always eligible for assignment)
        """

        day_start = datetime(
            business_date.year,
            business_date.month,
            business_date.day,
            tzinfo=timezone.utc,
        )
        day_end = day_start + timedelta(days=1)

        # NOTE: We avoid complex timezone logic in Phase 1; everything is UTC.
        q = (
            self.db.query(WorkTask)
            .filter(WorkTask.store_id == store_id)
            .filter(WorkTask.status == "pending")
            .filter(
                sa.or_(
                    WorkTask.window_start.is_(None),
                    sa.and_(
                        WorkTask.window_start >= day_start,
                        WorkTask.window_start < day_end,
                    ),
                )
            )
            .order_by(WorkTask.priority.asc(), WorkTask.created_at.asc())
        )
        return q.all()

    def _score_candidates(
        self,
        *,
        store_id: UUID,
        business_date: date,
        required_skills: list[TaskRequiredSkill],
    ) -> list[CandidateScore]:
        """
        Build and score the candidate pool for one task.
        """

        employees: list[Employee] = (
            self.db.query(Employee)
            .filter(Employee.store_id == store_id)
            .filter(Employee.is_active.is_(True))
            .all()
        )
        if not employees:
            return []

        employee_ids = [e.id for e in employees]

        # Availability via attendance:
        # - If there is an attendance row and punch_in is NULL -> treat as absent (exclude).
        # - If there is no attendance row -> unknown (allowed but scored lower).
        attendance_by_employee = {
            r.employee_id: r
            for r in (
                self.db.query(AttendanceDaily)
                .filter(AttendanceDaily.store_id == store_id)
                .filter(AttendanceDaily.business_date == business_date)
                .filter(AttendanceDaily.employee_id.in_(employee_ids))
                .all()
            )
        }

        # Current workload (active assignments) used as a small penalty.
        # We consider tasks "active" if they are assigned/in_progress and the assignment
        # row is not completed yet.
        active_statuses = ("assigned", "in_progress")
        active_counts = dict(
            self.db.query(TaskAssignment.employee_id, sa.func.count(TaskAssignment.id))
            .join(WorkTask, WorkTask.id == TaskAssignment.task_id)
            .filter(WorkTask.store_id == store_id)
            .filter(WorkTask.status.in_(active_statuses))
            .filter(TaskAssignment.completed_at.is_(None))
            .group_by(TaskAssignment.employee_id)
            .all()
        )

        # Pull all employee skills for the relevant skills in one query.
        skill_ids = [rs.skill_id for rs in required_skills]
        employee_skill_rows: list[EmployeeSkill] = []
        if skill_ids:
            employee_skill_rows = (
                self.db.query(EmployeeSkill)
                .filter(EmployeeSkill.employee_id.in_(employee_ids))
                .filter(EmployeeSkill.skill_id.in_(skill_ids))
                .all()
            )

        skills_by_employee: dict[UUID, dict[UUID, EmployeeSkill]] = {}
        for row in employee_skill_rows:
            skills_by_employee.setdefault(row.employee_id, {})[row.skill_id] = row

        scored: list[CandidateScore] = []
        for e in employees:
            attendance = attendance_by_employee.get(e.id)
            # Exclude explicit absences (attendance row exists but no punch-in).
            if attendance is not None and attendance.punch_in is None:
                continue

            # If an employee has punched out already, treat them as unavailable in Phase 1.
            if attendance is not None and attendance.punch_out is not None:
                continue

            is_present = None
            if attendance is not None:
                is_present = attendance.punch_in is not None

            emp_skills = skills_by_employee.get(e.id, {})

            # Eligibility: satisfy ALL required skills.
            if not self._meets_required_skills(emp_skills, required_skills):
                continue

            base_skill_score = self._base_skill_score(emp_skills, required_skills)
            penalty = float(active_counts.get(e.id, 0)) * float(
                getattr(settings, "work_active_assignment_penalty", 0.25)
            )
            presence_bonus = (
                float(getattr(settings, "work_presence_bonus", 0.0))
                if is_present is True
                else 0.0
            )
            unknown_penalty = (
                float(getattr(settings, "work_unknown_presence_penalty", 0.0))
                if is_present is None
                else 0.0
            )

            score = float(base_skill_score + presence_bonus - unknown_penalty - penalty)

            scored.append(
                CandidateScore(
                    employee_id=e.id,
                    employee_code=e.employee_code,
                    employee_name=e.name,
                    score=score,
                    base_skill_score=base_skill_score,
                    active_assignment_count=int(active_counts.get(e.id, 0) or 0),
                    is_present=is_present,
                )
            )

        return scored

    @staticmethod
    def _meets_required_skills(
        employee_skills: dict[UUID, EmployeeSkill],
        required_skills: list[TaskRequiredSkill],
    ) -> bool:
        for req in required_skills:
            if not req.required:
                continue
            es = employee_skills.get(req.skill_id)
            if es is None:
                return False
            if int(es.proficiency) < int(req.min_proficiency):
                return False
        return True

    @staticmethod
    def _base_skill_score(
        employee_skills: dict[UUID, EmployeeSkill],
        required_skills: list[TaskRequiredSkill],
    ) -> float:
        """
        Explainable baseline:
          sum(proficiency * confidence) for each task-required skill the employee meets.

        Notes:
        - This includes optional skills as additional signal (required=false).
        - Skills below min_proficiency contribute 0.
        """
        total = 0.0
        for req in required_skills:
            es = employee_skills.get(req.skill_id)
            if es is None:
                continue
            if int(es.proficiency) < int(req.min_proficiency):
                continue
            total += float(es.proficiency) * float(es.confidence)
        return float(total)

    @staticmethod
    def _pick_best_candidate(candidates: list[CandidateScore]) -> CandidateScore | None:
        """
        Deterministic tie-breaking:
        1) higher score
        2) higher base_skill_score
        3) fewer active assignments
        4) employee_code lexicographically
        5) employee_id as a stable final tie-breaker
        """
        if not candidates:
            return None

        return sorted(
            candidates,
            key=lambda c: (
                -c.score,
                -c.base_skill_score,
                c.active_assignment_count,
                c.employee_code.lower(),
                str(c.employee_id),
            ),
        )[0]
