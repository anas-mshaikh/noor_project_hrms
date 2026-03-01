from __future__ import annotations

import time
import uuid
from sqlalchemy import text
from sqlalchemy.exc import OperationalError


def _is_deadlock_error(exc: BaseException) -> bool:
    """
    Best-effort detection for Postgres deadlock errors.

    In test cleanup we prefer retrying a few times rather than failing the entire
    suite due to transient lock ordering issues from background threads/tasks.
    """

    msg = str(exc).lower()
    if "deadlock detected" in msg:
        return True

    # SQLAlchemy often wraps psycopg errors as OperationalError with .orig.
    orig = getattr(exc, "orig", None)
    if orig is None:
        return False
    return orig.__class__.__name__.lower() == "deadlockdetected"


def _run_with_deadlock_retries(engine, *, fn, attempts: int = 5) -> None:
    for i in range(attempts):
        try:
            with engine.begin() as conn:
                fn(conn)
            return
        except OperationalError as e:
            if not _is_deadlock_error(e) or i == attempts - 1:
                raise
            # Exponential backoff: 0.1s, 0.2s, 0.4s, 0.8s...
            time.sleep(0.1 * (2**i))


def require_tables(conn, *fqtns: str) -> None:
    for fqtn in fqtns:
        exists = conn.execute(text("SELECT to_regclass(:fqtn)"), {"fqtn": fqtn}).scalar()
        assert exists is not None, f"Missing required table {fqtn}; did you run migrations?"


def role_id(conn, code: str) -> uuid.UUID:
    rid = conn.execute(text("SELECT id FROM iam.roles WHERE code = :code"), {"code": code}).scalar()
    assert rid is not None, f"Missing IAM role {code}; ensure seed migrations ran."
    return rid


def seed_tenant_company(
    engine,
    *,
    with_second_branch: bool = False,
    with_second_company: bool = False,
) -> dict[str, str]:
    """
    Seed a minimal tenant/company/branch hierarchy using raw SQL.

    Returns IDs as strings for easy JSON usage in API tests:
      tenant_id, company_id, branch_id, (optional) branch2_id, company2_id, branch3_id
    """

    tenant_id = uuid.uuid4()
    company_id = uuid.uuid4()
    branch_id = uuid.uuid4()

    branch2_id = uuid.uuid4() if with_second_branch else None
    company2_id = uuid.uuid4() if with_second_company else None
    branch3_id = uuid.uuid4() if with_second_company else None

    with engine.begin() as conn:
        require_tables(conn, "tenancy.tenants", "tenancy.companies", "tenancy.branches")

        conn.execute(
            text("INSERT INTO tenancy.tenants (id, name, status) VALUES (:id, :name, 'ACTIVE')"),
            {"id": tenant_id, "name": f"Tenant {tenant_id.hex[:6]}"},
        )
        conn.execute(
            text(
                """
                INSERT INTO tenancy.companies (id, tenant_id, name, legal_name, currency_code, timezone, status)
                VALUES (:id, :tenant_id, :name, :legal_name, 'SAR', 'Asia/Riyadh', 'ACTIVE')
                """
            ),
            {
                "id": company_id,
                "tenant_id": tenant_id,
                "name": f"Company {company_id.hex[:6]}",
                "legal_name": f"Company {company_id.hex[:6]} LLC",
            },
        )
        conn.execute(
            text(
                """
                INSERT INTO tenancy.branches (id, tenant_id, company_id, name, code, timezone, address, status)
                VALUES (:id, :tenant_id, :company_id, :name, :code, 'Asia/Riyadh', '{}'::jsonb, 'ACTIVE')
                """
            ),
            {
                "id": branch_id,
                "tenant_id": tenant_id,
                "company_id": company_id,
                "name": "HQ",
                "code": f"HQ{branch_id.hex[:4].upper()}",
            },
        )

        if branch2_id is not None:
            conn.execute(
                text(
                    """
                    INSERT INTO tenancy.branches (id, tenant_id, company_id, name, code, timezone, address, status)
                    VALUES (:id, :tenant_id, :company_id, :name, :code, 'Asia/Riyadh', '{}'::jsonb, 'ACTIVE')
                    """
                ),
                {
                    "id": branch2_id,
                    "tenant_id": tenant_id,
                    "company_id": company_id,
                    "name": "Branch 2",
                    "code": f"B2{branch2_id.hex[:4].upper()}",
                },
            )

        if company2_id is not None and branch3_id is not None:
            conn.execute(
                text(
                    """
                    INSERT INTO tenancy.companies (id, tenant_id, name, legal_name, currency_code, timezone, status)
                    VALUES (:id, :tenant_id, :name, :legal_name, 'SAR', 'Asia/Riyadh', 'ACTIVE')
                    """
                ),
                {
                    "id": company2_id,
                    "tenant_id": tenant_id,
                    "name": f"Company {company2_id.hex[:6]}",
                    "legal_name": f"Company {company2_id.hex[:6]} LLC",
                },
            )
            conn.execute(
                text(
                    """
                    INSERT INTO tenancy.branches (id, tenant_id, company_id, name, code, timezone, address, status)
                    VALUES (:id, :tenant_id, :company_id, :name, :code, 'Asia/Riyadh', '{}'::jsonb, 'ACTIVE')
                    """
                ),
                {
                    "id": branch3_id,
                    "tenant_id": tenant_id,
                    "company_id": company2_id,
                    "name": "C2-HQ",
                    "code": f"C2{branch3_id.hex[:4].upper()}",
                },
            )

    out = {"tenant_id": str(tenant_id), "company_id": str(company_id), "branch_id": str(branch_id)}
    if branch2_id is not None:
        out["branch2_id"] = str(branch2_id)
    if company2_id is not None and branch3_id is not None:
        out["company2_id"] = str(company2_id)
        out["branch3_id"] = str(branch3_id)
    return out


def seed_user(
    engine,
    *,
    tenant_id: str,
    company_id: str,
    branch_id: str,
    role_code: str,
    email_prefix: str | None = None,
    password: str = "StrongPass123",
) -> dict[str, str]:
    """
    Seed an IAM user + a scoped role assignment.
    """

    user_id = uuid.uuid4()
    email = f"{(email_prefix or role_code).lower()}+{user_id.hex[:10]}@example.com"

    from app.auth.passwords import hash_password

    with engine.begin() as conn:
        require_tables(conn, "iam.users", "iam.roles", "iam.user_roles")

        conn.execute(
            text(
                """
                INSERT INTO iam.users (id, email, phone, password_hash, status)
                VALUES (:id, :email, NULL, :password_hash, 'ACTIVE')
                """
            ),
            {"id": user_id, "email": email, "password_hash": hash_password(password)},
        )
        conn.execute(
            text(
                """
                INSERT INTO iam.user_roles (user_id, tenant_id, company_id, branch_id, role_id)
                VALUES (:user_id, :tenant_id, :company_id, :branch_id, :role_id)
                """
            ),
            {
                "user_id": user_id,
                "tenant_id": tenant_id,
                "company_id": company_id,
                "branch_id": branch_id,
                "role_id": role_id(conn, role_code),
            },
        )

    return {"user_id": str(user_id), "email": email, "password": password}


def cleanup(engine, *, tenant_id: str | None, user_ids: list[str]) -> None:
    # Delete tenant first (cascades to tenancy + scoped user_roles). Users are global in iam, so delete explicitly.
    if tenant_id is not None:
        _run_with_deadlock_retries(
            engine,
            fn=lambda conn: conn.execute(text("DELETE FROM tenancy.tenants WHERE id = :id"), {"id": tenant_id}),
        )

    if user_ids:
        def _delete_users(conn) -> None:
            for uid in user_ids:
                conn.execute(text("DELETE FROM iam.users WHERE id = :id"), {"id": uid})

        _run_with_deadlock_retries(engine, fn=_delete_users)
