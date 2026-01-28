"""
multi_schema_smoke_test.py

Smoke test for the multi-schema Postgres refactor.

Usage (inside backend container or local venv):
  python backend/scripts/multi_schema_smoke_test.py

Optional:
  python backend/scripts/multi_schema_smoke_test.py --database-url postgresql://...

This script is intentionally simple:
- It verifies that the expected schemas/tables are queryable.
- It runs a couple of FK join checks to catch schema/search_path issues.

It does NOT mutate data.
"""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import create_engine, text


SEARCH_PATH = "core,vision,attendance,hr,mobile,face,imports,analytics,skills,work,public"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--database-url",
        default=None,
        help="Override DATABASE_URL (defaults to app.core.config.settings.database_url).",
    )
    args = parser.parse_args()

    from app.core.config import settings  # local import for CLI ergonomics

    db_url = args.database_url or settings.database_url
    engine = create_engine(
        db_url,
        pool_pre_ping=True,
        connect_args={"options": f"-csearch_path={SEARCH_PATH}"},
    )

    table_checks = [
        # core
        "core.organizations",
        "core.stores",
        "core.employees",
        # vision
        "vision.cameras",
        "vision.videos",
        "vision.jobs",
        "vision.tracks",
        "vision.events",
        "vision.metrics_hourly",
        "vision.artifacts",
        # attendance
        "attendance.attendance_daily",
        "attendance.attendance_summary",
        # face
        "face.employee_faces",
        # imports
        "imports.datasets",
        "imports.month_state",
        # analytics
        "analytics.pos_summary",
        # hr
        "hr.hr_openings",
        "hr.hr_resume_batches",
        "hr.hr_resumes",
        "hr.hr_resume_views",
        "hr.hr_screening_runs",
        "hr.hr_screening_results",
        "hr.hr_screening_explanations",
        "hr.hr_pipeline_stages",
        "hr.hr_applications",
        "hr.hr_application_notes",
        "hr.hr_onboarding_plans",
        "hr.hr_onboarding_tasks",
        "hr.hr_employee_documents",
        # mobile
        "mobile.mobile_accounts",
        # skills
        "skills.skill_taxonomy",
        "skills.employee_skills",
        # work
        "work.tasks",
        "work.task_required_skills",
        "work.task_assignments",
        # alembic
        "public.alembic_version",
    ]

    join_checks = [
        (
            "core.stores -> core.organizations",
            """
            SELECT s.id, o.id
            FROM core.stores s
            JOIN core.organizations o ON o.id = s.org_id
            LIMIT 1
            """,
        ),
        (
            "vision.jobs -> vision.videos",
            """
            SELECT j.id, v.id
            FROM vision.jobs j
            JOIN vision.videos v ON v.id = j.video_id
            LIMIT 1
            """,
        ),
        (
            "hr.hr_resumes -> hr.hr_openings",
            """
            SELECT r.id, o.id
            FROM hr.hr_resumes r
            JOIN hr.hr_openings o ON o.id = r.opening_id
            LIMIT 1
            """,
        ),
        (
            "work.task_assignments -> core.employees",
            """
            SELECT a.id, e.id
            FROM work.task_assignments a
            JOIN core.employees e ON e.id = a.employee_id
            LIMIT 1
            """,
        ),
    ]

    failures: list[str] = []
    with engine.connect() as conn:
        for fqtn in table_checks:
            try:
                conn.execute(text(f"SELECT 1 FROM {fqtn} LIMIT 1"))
            except Exception as e:  # pragma: no cover - smoke-only
                failures.append(f"table check failed for {fqtn}: {e}")

        for name, sql in join_checks:
            try:
                conn.execute(text(sql))
            except Exception as e:  # pragma: no cover - smoke-only
                failures.append(f"join check failed for {name}: {e}")

    if failures:
        print("Multi-schema smoke test FAILED:", file=sys.stderr)
        for f in failures:
            print(f"- {f}", file=sys.stderr)
        return 1

    print("Multi-schema smoke test OK.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
