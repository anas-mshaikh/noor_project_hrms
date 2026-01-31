"""DB vNext (0002): seed global defaults (roles, permissions, request types).

Revision ID: fc4c56b52118
Revises: 888da65cf59f
Create Date: 2026-01-29

This migration seeds global (non-tenant) defaults required for an enterprise
HRMS foundation:
- IAM roles + permission scaffolding
- Workflow request types

Tenant-specific defaults (e.g. document types) are seeded in 0003 for the demo
tenant (or by application logic when creating real tenants).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "fc4c56b52118"
down_revision = "888da65cf59f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Roles
    op.execute(
        sa.text(
            """
            INSERT INTO iam.roles (code, name, description)
            VALUES
              ('ADMIN', 'Administrator', 'Full access across the tenant'),
              ('HR_MANAGER', 'HR Manager', 'HR operations and approvals'),
              ('MANAGER', 'Manager', 'Line manager approvals and team operations'),
              ('EMPLOYEE', 'Employee', 'Standard employee access')
            ;
            """
        )
    )

    # Permissions (minimal MVP set). These are *codes only*; actual enforcement
    # will be implemented in the application layer later.
    op.execute(
        sa.text(
            """
            INSERT INTO iam.permissions (code, description)
            VALUES
              ('HR_CORE_READ', 'Read HR core records'),
              ('HR_CORE_WRITE', 'Write HR core records'),
              ('WORKFLOW_REQUEST_CREATE', 'Create workflow requests'),
              ('WORKFLOW_REQUEST_APPROVE', 'Approve workflow requests'),
              ('DMS_READ', 'Read documents'),
              ('DMS_WRITE', 'Upload/manage documents')
            ;
            """
        )
    )

    # Role -> Permission mapping.
    # NOTE: We intentionally keep this simple for Phase 1. The product will
    # likely evolve into permission groups / policies.
    op.execute(
        sa.text(
            """
            INSERT INTO iam.role_permissions (role_id, permission_id)
            SELECT r.id, p.id
            FROM iam.roles r
            JOIN iam.permissions p ON p.code IN (
              'HR_CORE_READ', 'HR_CORE_WRITE', 'WORKFLOW_REQUEST_CREATE',
              'WORKFLOW_REQUEST_APPROVE', 'DMS_READ', 'DMS_WRITE'
            )
            WHERE r.code = 'ADMIN'
            """
        )
    )
    op.execute(
        sa.text(
            """
            INSERT INTO iam.role_permissions (role_id, permission_id)
            SELECT r.id, p.id
            FROM iam.roles r
            JOIN iam.permissions p ON p.code IN (
              'HR_CORE_READ', 'HR_CORE_WRITE', 'WORKFLOW_REQUEST_CREATE',
              'WORKFLOW_REQUEST_APPROVE', 'DMS_READ', 'DMS_WRITE'
            )
            WHERE r.code = 'HR_MANAGER'
            """
        )
    )
    op.execute(
        sa.text(
            """
            INSERT INTO iam.role_permissions (role_id, permission_id)
            SELECT r.id, p.id
            FROM iam.roles r
            JOIN iam.permissions p ON p.code IN (
              'HR_CORE_READ', 'WORKFLOW_REQUEST_CREATE', 'WORKFLOW_REQUEST_APPROVE', 'DMS_READ'
            )
            WHERE r.code = 'MANAGER'
            """
        )
    )
    op.execute(
        sa.text(
            """
            INSERT INTO iam.role_permissions (role_id, permission_id)
            SELECT r.id, p.id
            FROM iam.roles r
            JOIN iam.permissions p ON p.code IN (
              'WORKFLOW_REQUEST_CREATE', 'DMS_READ'
            )
            WHERE r.code = 'EMPLOYEE'
            """
        )
    )

    # Workflow request types (global).
    op.execute(
        sa.text(
            """
            INSERT INTO workflow.request_types (code, name, description)
            VALUES
              ('LEAVE_REQUEST', 'Leave Request', 'Employee leave request'),
              ('DOCUMENT_REQUEST', 'Document Request', 'Request a document or verification'),
              ('EXPENSE_CLAIM', 'Expense Claim', 'Submit an expense claim for approval'),
              ('GENERAL_REQUEST', 'General Request', 'Generic request type for future workflows')
            ;
            """
        )
    )


def downgrade() -> None:
    # Best-effort cleanup for dev.
    op.execute(
        sa.text(
            """
            DELETE FROM iam.role_permissions rp
            USING iam.roles r, iam.permissions p
            WHERE rp.role_id = r.id
              AND rp.permission_id = p.id
              AND r.code IN ('ADMIN','HR_MANAGER','MANAGER','EMPLOYEE')
              AND p.code IN (
                'HR_CORE_READ','HR_CORE_WRITE','WORKFLOW_REQUEST_CREATE',
                'WORKFLOW_REQUEST_APPROVE','DMS_READ','DMS_WRITE'
              )
            """
        )
    )
    op.execute(
        sa.text(
            """
            DELETE FROM iam.permissions
            WHERE code IN (
              'HR_CORE_READ','HR_CORE_WRITE','WORKFLOW_REQUEST_CREATE',
              'WORKFLOW_REQUEST_APPROVE','DMS_READ','DMS_WRITE'
            )
            """
        )
    )
    op.execute(
        sa.text("DELETE FROM iam.roles WHERE code IN ('ADMIN','HR_MANAGER','MANAGER','EMPLOYEE')")
    )
    op.execute(
        sa.text(
            """
            DELETE FROM workflow.request_types
            WHERE code IN ('LEAVE_REQUEST','DOCUMENT_REQUEST','EXPENSE_CLAIM','GENERAL_REQUEST')
            """
        )
    )
