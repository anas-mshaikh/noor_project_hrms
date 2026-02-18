"""
Pydantic schemas for the DMS (Document Management System) domain.

Design notes:
- Keep API shapes stable and explicit (Literal-based enums for status fields).
- Avoid exposing internal storage paths (object_key/bucket) in responses.
- Keep workflow payloads minimal; DMS domain tables are the canonical record.
"""

from __future__ import annotations


from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


# ------------------------------------------------------------------
# Files
# ------------------------------------------------------------------
StorageProvider = Literal["LOCAL", "S3"]
FileStatus = Literal["UPLOADING", "READY", "FAILED", "DELETED"]


class DmsFileOut(BaseModel):
    id: UUID
    tenant_id: UUID
    storage_provider: StorageProvider
    original_filename: str
    content_type: str
    size_bytes: int
    sha256: str | None
    status: FileStatus
    created_by_user_id: UUID | None
    created_at: datetime
    updated_at: datetime

    meta: dict[str, Any] | None = None


# ------------------------------------------------------------------
# Document types
# ------------------------------------------------------------------
class DocumentTypeCreateIn(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=200)
    requires_expiry: bool = False
    is_active: bool = True


class DocumentTypePatchIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    requires_expiry: bool | None = None
    is_active: bool | None = None


class DocumentTypeOut(BaseModel):
    id: UUID
    tenant_id: UUID
    code: str
    name: str
    requires_expiry: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime


class DocumentTypesOut(BaseModel):
    items: list[DocumentTypeOut]


# ------------------------------------------------------------------
# Documents + versions
# ------------------------------------------------------------------
DocumentStatus = Literal["DRAFT", "SUBMITTED", "VERIFIED", "REJECTED", "EXPIRED"]


class DocumentVersionOut(BaseModel):
    id: UUID
    tenant_id: UUID
    document_id: UUID
    file_id: UUID
    version: int
    notes: str | None
    created_by_user_id: UUID | None
    created_at: datetime


class EmployeeDocumentCreateIn(BaseModel):
    document_type_code: str = Field(min_length=1, max_length=64)
    file_id: UUID
    expires_at: date | None = None
    notes: str | None = Field(default=None, max_length=2000)


class DocumentAddVersionIn(BaseModel):
    file_id: UUID
    notes: str | None = Field(default=None, max_length=2000)


class DocumentOut(BaseModel):
    id: UUID
    tenant_id: UUID
    document_type_id: UUID
    document_type_code: str
    document_type_name: str
    owner_employee_id: UUID | None
    status: DocumentStatus
    expires_at: date | None

    current_version_id: UUID | None
    current_version: DocumentVersionOut | None

    verified_at: datetime | None
    verified_by_user_id: UUID | None
    rejected_reason: str | None
    created_by_user_id: UUID | None
    verification_workflow_request_id: UUID | None

    created_at: datetime
    updated_at: datetime

    meta: dict[str, Any] | None = None


class DocumentListOut(BaseModel):
    items: list[DocumentOut]
    next_cursor: str | None


class VerifyRequestOut(BaseModel):
    workflow_request_id: UUID


# ------------------------------------------------------------------
# Expiry rules + upcoming
# ------------------------------------------------------------------
class ExpiryRuleCreateIn(BaseModel):
    document_type_code: str = Field(min_length=1, max_length=64)
    days_before: int = Field(ge=0, le=3650)
    is_active: bool = True


class ExpiryRuleOut(BaseModel):
    id: UUID
    tenant_id: UUID
    document_type_id: UUID | None
    document_type_code: str | None
    document_type_name: str | None
    days_before: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ExpiryRulesOut(BaseModel):
    items: list[ExpiryRuleOut]


class UpcomingExpiryItemOut(BaseModel):
    document_id: UUID
    document_type_code: str
    document_type_name: str
    owner_employee_id: UUID | None
    expires_at: date
    days_left: int
    status: DocumentStatus


class UpcomingExpiryOut(BaseModel):
    items: list[UpcomingExpiryItemOut]
