"""DMS v1: harden/extend schema for files + employee document library + expiry.

Revision ID: d1c0a7e2b3f4
Revises: c8a3b4d5e6f7
Create Date: 2026-02-18

Milestone 5 introduces an enterprise-safe DMS layer:
- dms.files gains upload lifecycle columns (status, created_by_user_id)
- dms.documents becomes employee-owned and supports verification status
- dms.document_versions adds metadata for immutable versioning
- dms.document_links gains uniqueness for polymorphic attachments
- dms.expiry_rules/events gain columns to support idempotent expiry notifications
- workflow.request_types gains DOCUMENT_VERIFICATION

This migration is intentionally additive/safe:
- new columns are nullable where needed for existing rows
- status check constraints are migrated with a defensive backfill
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as psql


# revision identifiers, used by Alembic.
revision = "d1c0a7e2b3f4"
down_revision = "c8a3b4d5e6f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # dms.files
    # ------------------------------------------------------------------
    op.add_column(
        "files",
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'READY'")),
        schema="dms",
    )
    op.add_column(
        "files",
        sa.Column("created_by_user_id", psql.UUID(as_uuid=True), nullable=True),
        schema="dms",
    )
    op.create_check_constraint(
        "ck_dms_files_status",
        "files",
        "status in ('UPLOADING','READY','FAILED','DELETED')",
        schema="dms",
    )
    op.create_foreign_key(
        "fk_files_created_by_user_id",
        source_table="files",
        referent_table="users",
        local_cols=["created_by_user_id"],
        remote_cols=["id"],
        source_schema="dms",
        referent_schema="iam",
        ondelete="SET NULL",
    )

    # Harden common metadata fields so services can rely on them.
    op.execute(sa.text("UPDATE dms.files SET content_type = 'application/octet-stream' WHERE content_type IS NULL"))
    op.execute(sa.text("UPDATE dms.files SET size_bytes = 0 WHERE size_bytes IS NULL"))
    op.execute(sa.text("UPDATE dms.files SET original_filename = 'unknown' WHERE original_filename IS NULL"))

    op.alter_column("files", "content_type", existing_type=sa.Text(), nullable=False, schema="dms")
    op.alter_column("files", "size_bytes", existing_type=sa.BigInteger(), nullable=False, schema="dms")
    op.alter_column("files", "original_filename", existing_type=sa.Text(), nullable=False, schema="dms")

    op.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_files_tenant_created_at ON dms.files (tenant_id, created_at DESC)"))

    # ------------------------------------------------------------------
    # dms.document_types
    # ------------------------------------------------------------------
    op.add_column(
        "document_types",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        schema="dms",
    )
    op.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_document_types_tenant_is_active ON dms.document_types (tenant_id, is_active)"
        )
    )

    # ------------------------------------------------------------------
    # dms.documents
    # ------------------------------------------------------------------
    op.add_column(
        "documents",
        sa.Column("owner_employee_id", psql.UUID(as_uuid=True), nullable=True),
        schema="dms",
    )
    op.add_column(
        "documents",
        sa.Column("current_version_id", psql.UUID(as_uuid=True), nullable=True),
        schema="dms",
    )
    op.add_column(
        "documents",
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        schema="dms",
    )
    op.add_column(
        "documents",
        sa.Column("verified_by_user_id", psql.UUID(as_uuid=True), nullable=True),
        schema="dms",
    )
    op.add_column(
        "documents",
        sa.Column("rejected_reason", sa.Text(), nullable=True),
        schema="dms",
    )
    op.add_column(
        "documents",
        sa.Column("created_by_user_id", psql.UUID(as_uuid=True), nullable=True),
        schema="dms",
    )
    op.add_column(
        "documents",
        sa.Column("verification_workflow_request_id", psql.UUID(as_uuid=True), nullable=True),
        schema="dms",
    )

    # Migrate old status values (baseline used ACTIVE/ARCHIVED).
    op.execute(sa.text("UPDATE dms.documents SET status = 'SUBMITTED' WHERE status = 'ACTIVE'"))
    op.execute(sa.text("UPDATE dms.documents SET status = 'REJECTED' WHERE status = 'ARCHIVED'"))

    # Replace CHECK constraint to support v1 lifecycle.
    op.drop_constraint("ck_dms_documents_status", "documents", schema="dms", type_="check")
    op.create_check_constraint(
        "ck_dms_documents_status",
        "documents",
        "status in ('DRAFT','SUBMITTED','VERIFIED','REJECTED','EXPIRED')",
        schema="dms",
    )

    op.create_foreign_key(
        "fk_documents_owner_employee_id",
        source_table="documents",
        referent_table="employees",
        local_cols=["owner_employee_id"],
        remote_cols=["id"],
        source_schema="dms",
        referent_schema="hr_core",
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_documents_verified_by_user_id",
        source_table="documents",
        referent_table="users",
        local_cols=["verified_by_user_id"],
        remote_cols=["id"],
        source_schema="dms",
        referent_schema="iam",
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_documents_created_by_user_id",
        source_table="documents",
        referent_table="users",
        local_cols=["created_by_user_id"],
        remote_cols=["id"],
        source_schema="dms",
        referent_schema="iam",
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_documents_current_version_id",
        source_table="documents",
        referent_table="document_versions",
        local_cols=["current_version_id"],
        remote_cols=["id"],
        source_schema="dms",
        referent_schema="dms",
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_documents_verification_workflow_request_id",
        source_table="documents",
        referent_table="requests",
        local_cols=["verification_workflow_request_id"],
        remote_cols=["id"],
        source_schema="dms",
        referent_schema="workflow",
        ondelete="SET NULL",
    )

    op.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_documents_tenant_owner ON dms.documents (tenant_id, owner_employee_id)"))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_documents_tenant_status ON dms.documents (tenant_id, status)"))

    # ------------------------------------------------------------------
    # dms.document_versions
    # ------------------------------------------------------------------
    op.add_column("document_versions", sa.Column("notes", sa.Text(), nullable=True), schema="dms")
    op.add_column(
        "document_versions",
        sa.Column("created_by_user_id", psql.UUID(as_uuid=True), nullable=True),
        schema="dms",
    )

    # Uniqueness should include tenant_id (vNext-style). Baseline used (document_id, version).
    op.drop_constraint("uq_document_versions_doc_v", "document_versions", schema="dms", type_="unique")
    op.create_unique_constraint(
        "uq_document_versions_doc_v",
        "document_versions",
        ["tenant_id", "document_id", "version"],
        schema="dms",
    )
    op.create_foreign_key(
        "fk_document_versions_created_by_user_id",
        source_table="document_versions",
        referent_table="users",
        local_cols=["created_by_user_id"],
        remote_cols=["id"],
        source_schema="dms",
        referent_schema="iam",
        ondelete="SET NULL",
    )
    op.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_document_versions_tenant_doc_created_at ON dms.document_versions (tenant_id, document_id, created_at DESC)"
        )
    )

    # ------------------------------------------------------------------
    # dms.document_links
    # ------------------------------------------------------------------
    # Defensive de-duplication before enforcing uniqueness (dev DBs may contain duplicates).
    op.execute(
        sa.text(
            """
            DELETE FROM dms.document_links dl
            USING (
              SELECT
                -- Postgres does not define MIN/MAX aggregates for uuid in all versions.
                -- We cast to text for a deterministic choice of "one row to keep".
                MIN(id::text)::uuid AS keep_id,
                tenant_id,
                document_id,
                entity_type,
                entity_id
              FROM dms.document_links
              GROUP BY tenant_id, document_id, entity_type, entity_id
              HAVING COUNT(*) > 1
            ) dups
            WHERE dl.tenant_id = dups.tenant_id
              AND dl.document_id = dups.document_id
              AND dl.entity_type = dups.entity_type
              AND dl.entity_id = dups.entity_id
              AND dl.id <> dups.keep_id
            """
        )
    )
    op.create_unique_constraint(
        "uq_document_links_tenant_document_entity",
        "document_links",
        ["tenant_id", "document_id", "entity_type", "entity_id"],
        schema="dms",
    )

    # ------------------------------------------------------------------
    # dms.expiry_rules
    # ------------------------------------------------------------------
    op.add_column(
        "expiry_rules",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        schema="dms",
    )
    op.create_check_constraint(
        "ck_expiry_rules_days_before",
        "expiry_rules",
        "days_before >= 0",
        schema="dms",
    )
    op.create_index(
        "uq_expiry_rules_tenant_document_type_days_before",
        "expiry_rules",
        ["tenant_id", "document_type_id", "days_before"],
        unique=True,
        schema="dms",
        postgresql_where=sa.text("document_type_id IS NOT NULL"),
    )

    # ------------------------------------------------------------------
    # dms.expiry_events
    # ------------------------------------------------------------------
    op.add_column("expiry_events", sa.Column("notify_on_date", sa.Date(), nullable=True), schema="dms")
    op.add_column("expiry_events", sa.Column("event_type", sa.Text(), nullable=True), schema="dms")
    op.create_check_constraint(
        "ck_expiry_events_event_type",
        "expiry_events",
        "event_type IS NULL OR event_type in ('EXPIRING','EXPIRED')",
        schema="dms",
    )
    op.create_index(
        "ix_expiry_events_tenant_notify_on_date",
        "expiry_events",
        ["tenant_id", "notify_on_date"],
        unique=False,
        schema="dms",
    )
    op.create_index(
        "uq_expiry_events_tenant_document_notify_on_event",
        "expiry_events",
        ["tenant_id", "document_id", "notify_on_date", "event_type"],
        unique=True,
        schema="dms",
        postgresql_where=sa.text("notify_on_date IS NOT NULL AND event_type IS NOT NULL"),
    )

    # ------------------------------------------------------------------
    # workflow.request_types: DOCUMENT_VERIFICATION
    # ------------------------------------------------------------------
    op.execute(
        sa.text(
            """
            INSERT INTO workflow.request_types (code, name, description)
            VALUES (
              'DOCUMENT_VERIFICATION',
              'Document verification',
              'Workflow used by HR to verify employee documents'
            )
            ON CONFLICT (code) DO NOTHING
            """
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM workflow.request_types WHERE code = 'DOCUMENT_VERIFICATION'"))

    # dms.expiry_events
    op.drop_index("uq_expiry_events_tenant_document_notify_on_event", table_name="expiry_events", schema="dms")
    op.drop_index("ix_expiry_events_tenant_notify_on_date", table_name="expiry_events", schema="dms")
    op.drop_constraint("ck_expiry_events_event_type", "expiry_events", schema="dms", type_="check")
    op.drop_column("expiry_events", "event_type", schema="dms")
    op.drop_column("expiry_events", "notify_on_date", schema="dms")

    # dms.expiry_rules
    op.drop_index("uq_expiry_rules_tenant_document_type_days_before", table_name="expiry_rules", schema="dms")
    op.drop_constraint("ck_expiry_rules_days_before", "expiry_rules", schema="dms", type_="check")
    op.drop_column("expiry_rules", "is_active", schema="dms")

    # dms.document_links
    op.drop_constraint(
        "uq_document_links_tenant_document_entity",
        "document_links",
        schema="dms",
        type_="unique",
    )

    # dms.document_versions
    op.drop_index("ix_document_versions_tenant_doc_created_at", table_name="document_versions", schema="dms")
    op.drop_constraint("fk_document_versions_created_by_user_id", "document_versions", schema="dms", type_="foreignkey")
    op.drop_constraint("uq_document_versions_doc_v", "document_versions", schema="dms", type_="unique")
    op.create_unique_constraint(
        "uq_document_versions_doc_v",
        "document_versions",
        ["document_id", "version"],
        schema="dms",
    )
    op.drop_column("document_versions", "created_by_user_id", schema="dms")
    op.drop_column("document_versions", "notes", schema="dms")

    # dms.documents
    op.drop_index("ix_documents_tenant_status", table_name="documents", schema="dms")
    op.drop_index("ix_documents_tenant_owner", table_name="documents", schema="dms")
    op.drop_constraint("fk_documents_verification_workflow_request_id", "documents", schema="dms", type_="foreignkey")
    op.drop_constraint("fk_documents_current_version_id", "documents", schema="dms", type_="foreignkey")
    op.drop_constraint("fk_documents_created_by_user_id", "documents", schema="dms", type_="foreignkey")
    op.drop_constraint("fk_documents_verified_by_user_id", "documents", schema="dms", type_="foreignkey")
    op.drop_constraint("fk_documents_owner_employee_id", "documents", schema="dms", type_="foreignkey")
    op.drop_constraint("ck_dms_documents_status", "documents", schema="dms", type_="check")
    op.create_check_constraint(
        "ck_dms_documents_status",
        "documents",
        "status in ('ACTIVE','ARCHIVED')",
        schema="dms",
    )
    op.drop_column("documents", "verification_workflow_request_id", schema="dms")
    op.drop_column("documents", "created_by_user_id", schema="dms")
    op.drop_column("documents", "rejected_reason", schema="dms")
    op.drop_column("documents", "verified_by_user_id", schema="dms")
    op.drop_column("documents", "verified_at", schema="dms")
    op.drop_column("documents", "current_version_id", schema="dms")
    op.drop_column("documents", "owner_employee_id", schema="dms")

    # dms.document_types
    op.drop_index("ix_document_types_tenant_is_active", table_name="document_types", schema="dms")
    op.drop_column("document_types", "is_active", schema="dms")

    # dms.files
    op.execute(sa.text("DROP INDEX IF EXISTS dms.ix_files_tenant_created_at"))
    op.drop_constraint("fk_files_created_by_user_id", "files", schema="dms", type_="foreignkey")
    op.drop_constraint("ck_dms_files_status", "files", schema="dms", type_="check")
    op.alter_column("files", "original_filename", existing_type=sa.Text(), nullable=True, schema="dms")
    op.alter_column("files", "size_bytes", existing_type=sa.BigInteger(), nullable=True, schema="dms")
    op.alter_column("files", "content_type", existing_type=sa.Text(), nullable=True, schema="dms")
    op.drop_column("files", "created_by_user_id", schema="dms")
    op.drop_column("files", "status", schema="dms")
