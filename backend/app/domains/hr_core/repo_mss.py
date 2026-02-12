from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.domains.hr_core.models import Employee, EmployeeUserLink


@dataclass(frozen=True)
class ActorEmployeeContext:
    employee_id: UUID
    tenant_id: UUID
    company_id: UUID


@dataclass(frozen=True)
class TeamMemberRow:
    employee_id: UUID
    employee_code: str
    status: str
    first_name: str
    last_name: str
    email: str | None
    phone: str | None
    branch_id: UUID | None
    org_unit_id: UUID | None
    job_title_id: UUID | None
    grade_id: UUID | None
    manager_employee_id: UUID | None
    relationship_depth: int


def get_actor_employee_context(db: Session, *, user_id: UUID) -> ActorEmployeeContext | None:
    stmt = (
        sa.select(Employee.id, Employee.tenant_id, Employee.company_id)
        .select_from(EmployeeUserLink)
        .join(Employee, Employee.id == EmployeeUserLink.employee_id)
        .where(EmployeeUserLink.user_id == user_id)
    )
    row = db.execute(stmt).first()
    if row is None:
        return None
    return ActorEmployeeContext(employee_id=row[0], tenant_id=row[1], company_id=row[2])


def list_team_directory(
    db: Session,
    *,
    tenant_id: UUID,
    company_id: UUID,
    actor_employee_id: UUID,
    depth_mode: str,
    q: str | None,
    status: str | None,
    branch_id: UUID | None,
    org_unit_id: UUID | None,
    limit: int,
    offset: int,
) -> tuple[list[TeamMemberRow], int]:
    params: dict[str, object] = {
        "tenant_id": tenant_id,
        "company_id": company_id,
        "actor_employee_id": actor_employee_id,
        "limit": limit,
        "offset": offset,
    }

    where_parts: list[str] = [
        "e.tenant_id = :tenant_id",
        "e.company_id = :company_id",
    ]

    if status:
        where_parts.append("e.status = :status")
        params["status"] = status

    if branch_id is not None:
        where_parts.append("ce.branch_id = :branch_id")
        params["branch_id"] = branch_id

    if org_unit_id is not None:
        where_parts.append("ce.org_unit_id = :org_unit_id")
        params["org_unit_id"] = org_unit_id

    if q:
        where_parts.append(
            "(e.employee_code ILIKE :q OR p.first_name ILIKE :q OR p.last_name ILIKE :q OR p.email ILIKE :q OR p.phone ILIKE :q)"
        )
        params["q"] = f"%{q}%"

    where_sql = " AND ".join(where_parts) if where_parts else "TRUE"

    if depth_mode == "1":
        subtree_sql = """
        subtree AS (
          SELECT ce.employee_id, 1 AS depth
          FROM ce
          WHERE ce.manager_employee_id = :actor_employee_id
        )
        """
    else:
        subtree_sql = """
        subtree AS (
          SELECT ce.employee_id, 1 AS depth
          FROM ce
          WHERE ce.manager_employee_id = :actor_employee_id

          UNION ALL

          SELECT child.employee_id, s.depth + 1 AS depth
          FROM ce child
          JOIN subtree s ON child.manager_employee_id = s.employee_id
          WHERE s.depth < 50
        )
        """

    sql = sa.text(
        f"""
        WITH RECURSIVE current_employment AS (
          SELECT
            ee.employee_id,
            ee.manager_employee_id,
            ee.branch_id,
            ee.org_unit_id,
            ee.job_title_id,
            ee.grade_id,
            ROW_NUMBER() OVER (
              PARTITION BY ee.employee_id
              ORDER BY ee.is_primary DESC NULLS LAST, ee.start_date DESC, ee.id DESC
            ) AS rn
          FROM hr_core.employee_employment ee
          WHERE ee.tenant_id = :tenant_id
            AND ee.company_id = :company_id
            AND ee.end_date IS NULL
        ),
        ce AS (
          SELECT * FROM current_employment WHERE rn = 1
        ),
        {subtree_sql}
        SELECT
          e.id AS employee_id,
          e.employee_code,
          e.status,
          p.first_name,
          p.last_name,
          p.email,
          p.phone,
          ce.branch_id,
          ce.org_unit_id,
          ce.job_title_id,
          ce.grade_id,
          ce.manager_employee_id,
          subtree.depth AS relationship_depth
        FROM subtree
        JOIN hr_core.employees e ON e.id = subtree.employee_id
        JOIN hr_core.persons p ON p.id = e.person_id
        LEFT JOIN ce ON ce.employee_id = e.id
        WHERE {where_sql}
        ORDER BY subtree.depth ASC, e.employee_code ASC, e.created_at ASC, e.id ASC
        LIMIT :limit
        OFFSET :offset
        """
    )

    rows = db.execute(sql, params).all()
    items = [
        TeamMemberRow(
            employee_id=r.employee_id,
            employee_code=r.employee_code,
            status=r.status,
            first_name=r.first_name,
            last_name=r.last_name,
            email=r.email,
            phone=r.phone,
            branch_id=r.branch_id,
            org_unit_id=r.org_unit_id,
            job_title_id=r.job_title_id,
            grade_id=r.grade_id,
            manager_employee_id=r.manager_employee_id,
            relationship_depth=int(r.relationship_depth),
        )
        for r in rows
    ]

    count_sql = sa.text(
        f"""
        WITH RECURSIVE current_employment AS (
          SELECT
            ee.employee_id,
            ee.manager_employee_id,
            ee.branch_id,
            ee.org_unit_id,
            ROW_NUMBER() OVER (
              PARTITION BY ee.employee_id
              ORDER BY ee.is_primary DESC NULLS LAST, ee.start_date DESC, ee.id DESC
            ) AS rn
          FROM hr_core.employee_employment ee
          WHERE ee.tenant_id = :tenant_id
            AND ee.company_id = :company_id
            AND ee.end_date IS NULL
        ),
        ce AS (
          SELECT * FROM current_employment WHERE rn = 1
        ),
        {subtree_sql}
        SELECT COUNT(*)::INT
        FROM subtree
        JOIN hr_core.employees e ON e.id = subtree.employee_id
        JOIN hr_core.persons p ON p.id = e.person_id
        LEFT JOIN ce ON ce.employee_id = e.id
        WHERE {where_sql}
        """
    )
    total = int(db.execute(count_sql, params).scalar() or 0)

    return items, total


def is_in_manager_subtree(
    db: Session,
    *,
    tenant_id: UUID,
    company_id: UUID,
    actor_employee_id: UUID,
    target_employee_id: UUID,
) -> bool:
    # More efficient than scanning the entire subtree: walk UP the target's manager chain.
    row = db.execute(
        sa.text(
            """
            WITH RECURSIVE current_employment AS (
              SELECT
                ee.employee_id,
                ee.manager_employee_id,
                ROW_NUMBER() OVER (
                  PARTITION BY ee.employee_id
                  ORDER BY ee.is_primary DESC NULLS LAST, ee.start_date DESC, ee.id DESC
                ) AS rn
              FROM hr_core.employee_employment ee
              WHERE ee.tenant_id = :tenant_id
                AND ee.company_id = :company_id
                AND ee.end_date IS NULL
            ),
            ce AS (
              SELECT * FROM current_employment WHERE rn = 1
            ),
            chain AS (
              SELECT employee_id, manager_employee_id, 1 AS depth
              FROM ce
              WHERE employee_id = :target_employee_id

              UNION ALL

              SELECT ce.employee_id, ce.manager_employee_id, c.depth + 1 AS depth
              FROM ce
              JOIN chain c ON ce.employee_id = c.manager_employee_id
              WHERE c.manager_employee_id IS NOT NULL
                AND c.depth < 50
            )
            SELECT 1
            FROM chain
            WHERE manager_employee_id = :actor_employee_id
            LIMIT 1
            """
        ),
        {
            "tenant_id": tenant_id,
            "company_id": company_id,
            "actor_employee_id": actor_employee_id,
            "target_employee_id": target_employee_id,
        },
    ).first()
    return row is not None
