import uuid
from decimal import Decimal
from datetime import date, datetime
from typing import Any, Optional

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Organization(Base):
    __tablename__ = "organizations"
    __table_args__ = {"schema": "core"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )

    stores: Mapped[list["Store"]] = relationship(back_populates="organization")


class Store(Base):
    __tablename__ = "stores"
    __table_args__ = {"schema": "core"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("core.organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    timezone: Mapped[str] = mapped_column(
        sa.String(64), nullable=False, server_default="UTC"
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )

    organization: Mapped[Organization] = relationship(back_populates="stores")
    cameras: Mapped[list["Camera"]] = relationship(back_populates="store")
    employees: Mapped[list["Employee"]] = relationship(back_populates="store")
    # Mobile login bootstrap mapping (Postgres source-of-truth, Firestore derived).
    mobile_accounts: Mapped[list["MobileAccount"]] = relationship(
        back_populates="store"
    )
    videos: Mapped[list["Video"]] = relationship(back_populates="store")
    attendance_daily: Mapped[list["AttendanceDaily"]] = relationship(
        back_populates="store"
    )
    # HR module (Phase 1): openings + resumes (store-scoped).
    hr_openings: Mapped[list["HROpening"]] = relationship(back_populates="store")
    # HR module (Phase 3): ScreeningRun runs (store-scoped).
    hr_screening_runs: Mapped[list["HRScreeningRun"]] = relationship(
        back_populates="store"
    )
    # HR module (Phase 5): ATS applications (store-scoped).
    # This is optional, but makes it easy to list/filter applications by store.
    hr_applications: Mapped[list["HRApplication"]] = relationship(
        back_populates="store"
    )


class Camera(Base):
    __tablename__ = "cameras"
    __table_args__ = {"schema": "vision"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("core.stores.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    placement: Mapped[str | None] = mapped_column(sa.String(200), nullable=True)

    calibration_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )

    store: Mapped[Store] = relationship(back_populates="cameras")
    videos: Mapped[list["Video"]] = relationship(back_populates="camera")


class Employee(Base):
    __tablename__ = "employees"
    __table_args__ = (
        sa.UniqueConstraint(
            "store_id", "employee_code", name="uq_employees_store_employee_code"
        ),
        sa.Index("ix_employees_store_active", "store_id", "is_active"),
        {"schema": "core"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("core.stores.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    employee_code: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    department: Mapped[str] = mapped_column(
        sa.String(200),
        nullable=False,
        server_default="Unknown",
    )
    is_active: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default=sa.true()
    )

    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
        nullable=False,
    )

    store: Mapped[Store] = relationship(back_populates="employees")
    faces: Mapped[list["EmployeeFace"]] = relationship(back_populates="employee")
    attendance_daily: Mapped[list["AttendanceDaily"]] = relationship(
        back_populates="employee"
    )
    # HR module (Phase 6): onboarding plans created from HIRED ATS applications.
    onboarding_plans: Mapped[list["HROnboardingPlan"]] = relationship(
        back_populates="employee"
    )


class EmployeeFace(Base):
    __tablename__ = "employee_faces"
    __table_args__ = {"schema": "face"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("core.employees.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # NOTE: If your face model isn’t 512-dim, change Vector(512) now (changing later requires a migration).

    embedding: Mapped[list[float]] = mapped_column(Vector(512), nullable=False)

    snapshot_path: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    quality_score: Mapped[float | None] = mapped_column(sa.Float, nullable=True)
    model_version: Mapped[str] = mapped_column(
        sa.String(64), nullable=False, server_default="unknown"
    )

    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )

    employee: Mapped[Employee] = relationship(back_populates="faces")


class MobileAccount(Base):
    """
    Mobile app bootstrap mapping.

    Why this table exists:
    - Firebase Auth gives the mobile app a `uid`, but our domain identity lives in Postgres.
    - The mobile app must be able to resolve org/store/employee in ONE read:
        Auth -> uid -> Firestore users/{uid} -> org_id/store_id/employee_code
    - Postgres is the source of truth; Firestore `users/{uid}` is a derived cache.
    """

    __tablename__ = "mobile_accounts"
    __table_args__ = (
        # An employee should have at most one active mapping per store.
        sa.UniqueConstraint(
            "store_id", "employee_id", name="uq_mobile_accounts_store_employee"
        ),
        # Firebase UID must be unique globally.
        sa.UniqueConstraint("firebase_uid", name="uq_mobile_accounts_firebase_uid"),
        # Common query patterns: list active users for a store, or lookup by employee_id.
        sa.Index("ix_mobile_accounts_store_active", "store_id", "active"),
        sa.Index("ix_mobile_accounts_employee_id", "employee_id"),
        {"schema": "mobile"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("core.organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("core.stores.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("core.employees.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Denormalized for readability and to avoid extra joins for auditing/logs.
    employee_code: Mapped[str] = mapped_column(sa.String(64), nullable=False)

    # Firebase Auth user id (uid). We use this as the Firestore doc id under users/{uid}.
    firebase_uid: Mapped[str] = mapped_column(sa.String(128), nullable=False)

    # Role for mobile app access control (future: "admin" for store managers).
    role: Mapped[str] = mapped_column(
        sa.String(32), nullable=False, server_default="employee"
    )

    # `active=false` means access is revoked; we keep the row for audit/re-provisioning.
    active: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default=sa.true()
    )

    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )

    store: Mapped["Store"] = relationship(back_populates="mobile_accounts")
    employee: Mapped["Employee"] = relationship()


class Video(Base):
    __tablename__ = "videos"
    __table_args__ = {"schema": "vision"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("core.stores.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    camera_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("vision.cameras.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    business_date: Mapped[date] = mapped_column(sa.Date, nullable=False, index=True)

    file_path: Mapped[str] = mapped_column(sa.Text, nullable=False)
    sha256: Mapped[str | None] = mapped_column(sa.String(64), nullable=True, index=True)

    duration_sec: Mapped[float | None] = mapped_column(sa.Float, nullable=True)
    fps: Mapped[float | None] = mapped_column(sa.Float, nullable=True)
    width: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    recorded_start_ts: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )

    uploaded_by: Mapped[str | None] = mapped_column(sa.String(200), nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )

    store: Mapped["Store"] = relationship(back_populates="videos")
    camera: Mapped["Camera"] = relationship(back_populates="videos")
    jobs: Mapped[list["Job"]] = relationship(back_populates="video")


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        sa.CheckConstraint(
            "status in ('PENDING','RUNNING','POSTPROCESSING','DONE','FAILED','CANCELED')",
            name="ck_jobs_status",
        ),
        {"schema": "vision"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    video_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("vision.videos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        sa.String(32), nullable=False, server_default="PENDING"
    )
    progress: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, server_default="0"
    )

    pipeline_version: Mapped[str] = mapped_column(
        sa.String(64), nullable=False, server_default="v1"
    )
    model_versions_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
    )
    config_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
    )

    error: Mapped[str | None] = mapped_column(sa.Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )

    video: Mapped["Video"] = relationship(back_populates="jobs")
    tracks: Mapped[list["Track"]] = relationship(back_populates="job")
    events: Mapped[list["Event"]] = relationship(back_populates="job")
    metrics_hourly: Mapped[list["MetricsHourly"]] = relationship(back_populates="job")
    artifacts: Mapped[list["Artifact"]] = relationship(back_populates="job")


class Track(Base):
    __tablename__ = "tracks"
    __table_args__ = (
        sa.UniqueConstraint("job_id", "track_key", name="uq_tracks_job_track_key"),
        sa.CheckConstraint(
            "assigned_type in ('employee','visitor','unknown')",
            name="ck_tracks_assigned_type",
        ),
        {"schema": "vision"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("vision.jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    track_key: Mapped[str] = mapped_column(sa.String(64), nullable=False)

    entrance_id: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)

    first_ts: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False
    )
    last_ts: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False
    )

    best_snapshot_path: Mapped[str | None] = mapped_column(sa.Text, nullable=True)

    assigned_type: Mapped[str] = mapped_column(
        sa.String(32), nullable=False, server_default="unknown"
    )
    employee_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("core.employees.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    identity_confidence: Mapped[float | None] = mapped_column(sa.Float, nullable=True)

    first_seen_zone: Mapped[str | None] = mapped_column(sa.String(16), nullable=True)
    last_seen_zone: Mapped[str | None] = mapped_column(sa.String(16), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )

    job: Mapped["Job"] = relationship(back_populates="tracks")


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        sa.CheckConstraint(
            "event_type in ('entry','exit')", name="ck_events_event_type"
        ),
        sa.Index("ix_events_job_id_ts", "job_id", "ts"),
        sa.Index("ix_events_employee_id_ts", "employee_id", "ts"),
        {"schema": "vision"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("vision.jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    ts: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)

    event_type: Mapped[str] = mapped_column(sa.String(16), nullable=False)

    entrance_id: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    track_key: Mapped[str] = mapped_column(sa.String(64), nullable=False)

    employee_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("core.employees.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    confidence: Mapped[float | None] = mapped_column(sa.Float, nullable=True)
    snapshot_path: Mapped[str | None] = mapped_column(sa.Text, nullable=True)

    is_inferred: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default=sa.false()
    )
    meta: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
    )

    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )

    job: Mapped["Job"] = relationship(back_populates="events")


class AttendanceDaily(Base):
    __tablename__ = "attendance_daily"
    __table_args__ = (
        sa.UniqueConstraint(
            "store_id",
            "business_date",
            "employee_id",
            name="uq_attendance_store_date_employee",
        ),
        {"schema": "attendance"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("core.stores.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    business_date: Mapped[date] = mapped_column(sa.Date, nullable=False, index=True)

    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("core.employees.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    punch_in: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    punch_out: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )

    total_minutes: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    confidence: Mapped[float | None] = mapped_column(sa.Float, nullable=True)

    anomalies_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
    )

    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )

    store: Mapped["Store"] = relationship(back_populates="attendance_daily")
    employee: Mapped["Employee"] = relationship(back_populates="attendance_daily")


class MetricsHourly(Base):
    __tablename__ = "metrics_hourly"
    __table_args__ = (
        sa.UniqueConstraint("job_id", "hour_start_ts", name="uq_metrics_job_hour"),
        {"schema": "vision"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("vision.jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    hour_start_ts: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False
    )

    entries: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default="0")
    exits: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default="0")
    unique_visitors: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, server_default="0"
    )
    avg_dwell_sec: Mapped[float | None] = mapped_column(sa.Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )

    job: Mapped["Job"] = relationship(back_populates="metrics_hourly")


class Artifact(Base):
    __tablename__ = "artifacts"
    __table_args__ = (
        sa.CheckConstraint("type in ('csv','pdf','json')", name="ck_artifacts_type"),
        {"schema": "vision"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("vision.jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    type: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    path: Mapped[str] = mapped_column(sa.Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )

    job: Mapped["Job"] = relationship(back_populates="artifacts")


# -----------------------------------------------------------------------------
# Phase 2: Admin Import (Excel -> Postgres -> optional Firebase replica)
# -----------------------------------------------------------------------------


class Dataset(Base):
    """
    A versioned upload for a given month (YYYY-MM).

    Idempotency:
    - We enforce uniqueness on (month_key, checksum). Uploading the exact same file
      again for the same month should return the existing dataset_id.
    """

    __tablename__ = "datasets"
    __table_args__ = (
        sa.UniqueConstraint("month_key", "checksum", name="uq_datasets_month_checksum"),
        sa.CheckConstraint(
            "status in ('VALIDATING','READY','FAILED')",
            name="ck_datasets_status",
        ),
        sa.CheckConstraint(
            "sync_status in ('DISABLED','PENDING','SYNCED','FAILED')",
            name="ck_datasets_sync_status",
        ),
        {"schema": "imports"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    month_key: Mapped[str] = mapped_column(sa.String(16), nullable=False, index=True)
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("core.stores.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    uploaded_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )
    uploaded_by: Mapped[str | None] = mapped_column(sa.String(200), nullable=True)

    status: Mapped[str] = mapped_column(
        sa.String(16), nullable=False, server_default="VALIDATING"
    )
    sync_status: Mapped[str] = mapped_column(
        sa.String(16), nullable=False, server_default="DISABLED"
    )

    raw_file_path: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    checksum: Mapped[str] = mapped_column(sa.String(64), nullable=False)

    store: Mapped[Optional["Store"]] = relationship()
    pos_rows: Mapped[list["PosSummary"]] = relationship(back_populates="dataset")
    attendance_rows: Mapped[list["AttendanceSummary"]] = relationship(
        back_populates="dataset"
    )


class MonthState(Base):
    """
    Tracks which dataset is currently "published" for a month_key.

    Postgres is the source of truth; if Firebase sync is enabled, we only update
    Firestore AFTER month_state is updated successfully (see publish endpoint).
    """

    __tablename__ = "month_state"
    __table_args__ = {"schema": "imports"}

    month_key: Mapped[str] = mapped_column(sa.String(16), primary_key=True)
    published_dataset_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("imports.datasets.id", ondelete="SET NULL"),
        nullable=True,
    )


class PosSummary(Base):
    __tablename__ = "pos_summary"
    __table_args__ = {"schema": "analytics"}

    dataset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("imports.datasets.id", ondelete="CASCADE"),
        primary_key=True,
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("core.employees.id", ondelete="RESTRICT"),
        primary_key=True,
    )

    qty: Mapped[Decimal | None] = mapped_column(sa.Numeric, nullable=True)
    net_sales: Mapped[Decimal | None] = mapped_column(sa.Numeric, nullable=True)
    bills: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    customers: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    return_customers: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)

    dataset: Mapped["Dataset"] = relationship(back_populates="pos_rows")


class AttendanceSummary(Base):
    __tablename__ = "attendance_summary"
    __table_args__ = {"schema": "attendance"}

    dataset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("imports.datasets.id", ondelete="CASCADE"),
        primary_key=True,
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("core.employees.id", ondelete="RESTRICT"),
        primary_key=True,
    )

    present: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    absent: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    work_minutes: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    stocking_done: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    stocking_missed: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)

    dataset: Mapped["Dataset"] = relationship(back_populates="attendance_rows")


# ---------------------------------------------------------------------------
# HR module (Phase 1 only): Openings + Resume parsing
# ---------------------------------------------------------------------------


class HROpening(Base):
    """
    Hiring opening (store-scoped).

    Notes:
    - This is intentionally named "Opening" (not "Job") to avoid conflict with CCTV jobs.
    - `jd_text` is required in Phase 1 so Unstructured parsing can be tested against realistic data later.
    """

    __tablename__ = "hr_openings"
    __table_args__ = {"schema": "hr"}
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("core.stores.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(sa.Text, nullable=False)
    jd_text: Mapped[str] = mapped_column(sa.Text, nullable=False)
    requirements_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
    )

    # ACTIVE | ARCHIVED
    status: Mapped[str] = mapped_column(
        sa.String(16), nullable=False, server_default="ACTIVE", index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
        nullable=False,
    )

    store: Mapped["Store"] = relationship(back_populates="hr_openings")
    resumes: Mapped[list["HRResume"]] = relationship(
        back_populates="opening", cascade="all, delete-orphan"
    )
    resume_batches: Mapped[list["HRResumeBatch"]] = relationship(
        back_populates="opening", cascade="all, delete-orphan"
    )
    screening_runs: Mapped[list["HRScreeningRun"]] = relationship(
        back_populates="opening", cascade="all, delete-orphan"
    )
    # HR module (Phase 5): ATS pipeline stages + applications.
    pipeline_stages: Mapped[list["HRPipelineStage"]] = relationship(
        back_populates="opening", cascade="all, delete-orphan"
    )
    applications: Mapped[list["HRApplication"]] = relationship(
        back_populates="opening", cascade="all, delete-orphan"
    )


class HRResumeBatch(Base):
    """
    Optional grouping record for a multi-file upload.

    This makes the UI simpler (you can show batch progress), but the parsing
    still runs per-resume in RQ.
    """

    __tablename__ = "hr_resume_batches"
    __table_args__ = {"schema": "hr"}
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    opening_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("hr.hr_openings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("core.stores.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    total_count: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )

    opening: Mapped["HROpening"] = relationship(back_populates="resume_batches")
    resumes: Mapped[list["HRResume"]] = relationship(back_populates="batch")


class HRResume(Base):
    """
    Resume uploaded to an opening.

    Storage:
    - file_path: raw upload stored under DATA_DIR/hr/resumes/...
    - parsed_path: parsed.json artifact stored under DATA_DIR/hr/resumes/.../parsed
    - clean_text_path: plain text for quick preview (debugging)
    """

    __tablename__ = "hr_resumes"
    __table_args__ = {"schema": "hr"}
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    opening_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("hr.hr_openings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("core.stores.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    batch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("hr.hr_resume_batches.id", ondelete="SET NULL"),
        nullable=True,
    )

    original_filename: Mapped[str] = mapped_column(sa.Text, nullable=False)
    file_path: Mapped[str] = mapped_column(sa.Text, nullable=False)
    parsed_path: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    clean_text_path: Mapped[str | None] = mapped_column(sa.Text, nullable=True)

    # UPLOADED | PARSING | PARSED | FAILED
    status: Mapped[str] = mapped_column(
        sa.String(16), nullable=False, server_default="UPLOADED", index=True
    )

    error: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    rq_job_id: Mapped[str | None] = mapped_column(sa.Text, nullable=True)

    # -----------------------------
    # Phase 2 (HR): embeddings status
    # -----------------------------
    # We keep embedding status separate from parsing status so:
    # - parsing can succeed but embedding can fail (e.g., model missing)
    # - the UI can show clear progress and retry decisions
    #
    # Values:
    #   PENDING   -> waiting for embedding (usually right after PARSED)
    #   EMBEDDING -> embedding task is running
    #   EMBEDDED  -> at least the "full" view is embedded and stored
    #   FAILED    -> embedding task failed (see embedding_error)
    embedding_status: Mapped[str] = mapped_column(
        sa.String(16),
        nullable=False,
        server_default="PENDING",
        index=True,
    )
    embedding_error: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    embedded_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
        nullable=False,
    )

    opening: Mapped["HROpening"] = relationship(back_populates="resumes")
    batch: Mapped[Optional["HRResumeBatch"]] = relationship(back_populates="resumes")

    # Phase 2: multiple text "views" per resume (full/skills/experience).
    views: Mapped[list["HRResumeView"]] = relationship(
        back_populates="resume", cascade="all, delete-orphan"
    )


class HRResumeView(Base):
    """
    Derived "view" text for one resume + its embedding.

    Why multiple views?
    - `full`: the full clean text (best recall)
    - `skills`: a focused skills section (better for skill-based search)
    - `experience`: a focused experience section (better for role fit)

    In Phase 2 we embed these views using BGE-M3 (1024-d) and store them in Postgres pgvector.
    """

    __tablename__ = "hr_resume_views"
    __table_args__ = (
        sa.UniqueConstraint(
            "resume_id", "view_type", name="uq_hr_resume_views_resume_type"
        ),
        {"schema": "hr"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    resume_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("hr.hr_resumes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # full | skills | experience
    view_type: Mapped[str] = mapped_column(sa.String(16), nullable=False, index=True)

    # sha256 hex of the normalized + truncated text used for embedding
    text_hash: Mapped[str] = mapped_column(sa.String(64), nullable=False)

    # BGE-M3 embeddings are 1024 dimensions.
    embedding: Mapped[list[float] | None] = mapped_column(Vector(dim=1024), nullable=True)

    # Optional: store an approximate token count for debugging.
    tokens: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
        nullable=False,
    )

    resume: Mapped["HRResume"] = relationship(back_populates="views")


# ---------------------------------------------------------------------------
# HR module (Phase 3): Screening runs (retrieve + rerank)
# ---------------------------------------------------------------------------


class HRScreeningRun(Base):
    """
    Async ScreeningRun for an opening.

    A ScreeningRun is the HR equivalent of a "job", but we intentionally do NOT reuse
    the CCTV `jobs` table/routes.

    Pipeline (Phase 3):
    1) Retrieve candidate resumes using vector similarity (pgvector) over resume views.
    2) Rerank the candidate pool using a cross-encoder reranker (BGE reranker v2 M3).
    3) Persist ranked results for paging / audit.
    """

    __tablename__ = "hr_screening_runs"
    __table_args__ = {"schema": "hr"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    opening_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("hr.hr_openings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("core.stores.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # QUEUED|RUNNING|DONE|FAILED|CANCELLED
    status: Mapped[str] = mapped_column(
        sa.String(16),
        nullable=False,
        server_default="QUEUED",
        index=True,
    )

    # Run configuration and model versions are stored for audit/debugging.
    config_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
    )
    model_versions_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
    )

    rq_job_id: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    error: Mapped[str | None] = mapped_column(sa.Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )

    # Simple progress counters for UI polling.
    progress_total: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, server_default="0"
    )
    progress_done: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, server_default="0"
    )

    opening: Mapped["HROpening"] = relationship(back_populates="screening_runs")
    store: Mapped["Store"] = relationship(back_populates="hr_screening_runs")
    results: Mapped[list["HRScreeningResult"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class HRScreeningResult(Base):
    """
    Ranked result row for a ScreeningRun.

    Primary key is (run_id, resume_id) so each resume appears at most once per run.
    """

    __tablename__ = "hr_screening_results"
    __table_args__ = (
        sa.Index("ix_hr_screening_results_run_rank", "run_id", "rank"),
        {"schema": "hr"},
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("hr.hr_screening_runs.id", ondelete="CASCADE"),
        primary_key=True,
    )
    resume_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("hr.hr_resumes.id", ondelete="CASCADE"),
        primary_key=True,
    )

    rank: Mapped[int] = mapped_column(sa.Integer, nullable=False)

    # `final_score` is the UI-friendly score used for filtering/sorting in the UI.
    # We keep it normalized in 0..1 so clients can treat it like a probability-like score.
    #
    # Current behavior (Phase 3):
    # - rerank_score: raw reranker logit (unbounded; can be negative)
    # - final_score: 0..1 blend of retrieval similarity and sigmoid(rerank_score)
    #   (weights are configurable via HR_SCREENING_SCORE_W_* settings)
    final_score: Mapped[float] = mapped_column(sa.Float, nullable=False)

    # Keep component scores for debugging/tuning.
    rerank_score: Mapped[float | None] = mapped_column(sa.Float, nullable=True)
    retrieval_score: Mapped[float | None] = mapped_column(sa.Float, nullable=True)
    best_view_type: Mapped[str | None] = mapped_column(sa.String(16), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )

    run: Mapped["HRScreeningRun"] = relationship(back_populates="results")
    resume: Mapped["HRResume"] = relationship()


class HRScreeningExplanation(Base):
    """
    Structured LLM explanation for one ScreeningRun result row.

    Why a separate table?
    - Explanations are generated asynchronously (after ranking) and may be regenerated.
    - We store only structured JSON for UI display; we do NOT store raw resume text in DB.

    Primary key is (run_id, resume_id) so each resume has at most one explanation per run.
    If you change prompt/model, the backend overwrites this row deterministically.
    """

    __tablename__ = "hr_screening_explanations"
    __table_args__ = (
        sa.Index("ix_hr_screening_explanations_run_created_at", "run_id", "created_at"),
        {"schema": "hr"},
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("hr.hr_screening_runs.id", ondelete="CASCADE"),
        primary_key=True,
    )
    resume_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("hr.hr_resumes.id", ondelete="CASCADE"),
        primary_key=True,
    )

    # Optional: snapshot rank at the time of explanation generation.
    rank: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)

    model_name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    prompt_version: Mapped[str] = mapped_column(sa.Text, nullable=False)

    explanation_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
        index=True,
    )

    run: Mapped["HRScreeningRun"] = relationship()
    resume: Mapped["HRResume"] = relationship()


# ---------------------------------------------------------------------------
# HR module (Phase 5): ATS MVP (resume == applicant)
# ---------------------------------------------------------------------------


class HRPipelineStage(Base):
    """
    Pipeline stage for an opening (Kanban columns).

    Why stages are opening-scoped:
    - Different openings may want different pipelines (e.g., "Phone Screen" vs "Interview 1").
    - Keeping stages per opening keeps the MVP flexible without a global taxonomy.

    We create a default set of stages automatically when an opening is created:
      Applied -> Screened -> Interview -> Offer -> Hired / Rejected
    """

    __tablename__ = "hr_pipeline_stages"
    __table_args__ = (
        sa.UniqueConstraint(
            "opening_id", "name", name="uq_hr_pipeline_stages_opening_name"
        ),
        sa.Index("ix_hr_pipeline_stages_opening_sort", "opening_id", "sort_order"),
        {"schema": "hr"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    opening_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("hr.hr_openings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    sort_order: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    is_terminal: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default=sa.false()
    )

    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )

    opening: Mapped["HROpening"] = relationship(back_populates="pipeline_stages")


class HRApplication(Base):
    """
    ATS application row.

    MVP simplification:
    - We treat each resume as the applicant (1 resume = 1 application).
    - Uniqueness is enforced by UNIQUE(opening_id, resume_id).

    Notes:
    - `status` is a lightweight terminal marker; the stage is the primary pipeline position.
    - `source_run_id` links an application to the ScreeningRun that created it (if any).
    """

    __tablename__ = "hr_applications"
    __table_args__ = (
        sa.UniqueConstraint(
            "opening_id", "resume_id", name="uq_hr_applications_opening_resume"
        ),
        sa.Index("ix_hr_applications_opening_id", "opening_id"),
        sa.Index("ix_hr_applications_stage_id", "stage_id"),
        sa.Index("ix_hr_applications_store_id", "store_id"),
        sa.Index("ix_hr_applications_status", "status"),
        {"schema": "hr"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    opening_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("hr.hr_openings.id", ondelete="CASCADE"),
        nullable=False,
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("core.stores.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    resume_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("hr.hr_resumes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Phase 6: once a HIRED application is converted, link it to the canonical Employee row.
    employee_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("core.employees.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    hired_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    start_date: Mapped[date | None] = mapped_column(sa.Date, nullable=True)

    stage_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("hr.hr_pipeline_stages.id", ondelete="SET NULL"),
        nullable=True,
    )

    # ACTIVE|REJECTED|HIRED
    status: Mapped[str] = mapped_column(
        sa.String(16), nullable=False, server_default="ACTIVE", index=True
    )

    source_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("hr.hr_screening_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
        nullable=False,
    )

    opening: Mapped["HROpening"] = relationship(back_populates="applications")
    store: Mapped["Store"] = relationship(back_populates="hr_applications")
    resume: Mapped["HRResume"] = relationship()
    stage: Mapped["HRPipelineStage"] = relationship()
    # Optional link to the canonical Employee once a HIRED application is converted.
    # Use Optional[...] instead of `"Employee" | None` because this file does not use
    # `from __future__ import annotations`, and the `|` operator would be evaluated
    # at runtime (causing a TypeError when used inside a quoted forward ref).
    employee: Mapped[Optional["Employee"]] = relationship()
    notes: Mapped[list["HRApplicationNote"]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )


class HRApplicationNote(Base):
    """
    Free-form notes on an application.

    We keep notes as a separate table so:
    - the application row stays small,
    - we can paginate/stream notes later,
    - and we avoid write contention on the main application record.
    """

    __tablename__ = "hr_application_notes"
    __table_args__ = (
        sa.Index(
            "ix_hr_application_notes_application_created_at",
            "application_id",
            "created_at",
        ),
        {"schema": "hr"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("hr.hr_applications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    author_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    note: Mapped[str] = mapped_column(sa.Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )

    application: Mapped["HRApplication"] = relationship(back_populates="notes")


class HROnboardingPlan(Base):
    """
    Onboarding plan for a newly hired employee.

    Key goals:
    - Persist a checklist (tasks) so managers can track onboarding progress.
    - Track required documents uploaded locally (IDs, contract, bank details, etc).
    - Keep the plan tied to the canonical Employee identity in our system.
    """

    __tablename__ = "hr_onboarding_plans"
    __table_args__ = (
        sa.Index("ix_hr_onboarding_plans_employee_id", "employee_id"),
        sa.Index("ix_hr_onboarding_plans_store_id", "store_id"),
        sa.Index("ix_hr_onboarding_plans_status", "status"),
        {"schema": "hr"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("core.stores.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("core.employees.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    application_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("hr.hr_applications.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # ACTIVE|COMPLETED|CANCELLED
    status: Mapped[str] = mapped_column(
        sa.String(16), nullable=False, server_default="ACTIVE", index=True
    )
    start_date: Mapped[date | None] = mapped_column(sa.Date, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
        nullable=False,
    )

    employee: Mapped["Employee"] = relationship(back_populates="onboarding_plans")
    store: Mapped["Store"] = relationship()
    # Optional link back to the originating ATS application.
    application: Mapped[Optional["HRApplication"]] = relationship()

    tasks: Mapped[list["HROnboardingTask"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan"
    )
    documents: Mapped[list["HREmployeeDocument"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan"
    )


class HROnboardingTask(Base):
    """
    One onboarding checklist item.

    The `metadata_json` field allows the UI to attach structured meaning without changing
    schema frequently (e.g., document type required, target endpoint for an ACTION).
    """

    __tablename__ = "hr_onboarding_tasks"
    __table_args__ = (
        sa.Index("ix_hr_onboarding_tasks_plan_sort", "plan_id", "sort_order"),
        sa.Index("ix_hr_onboarding_tasks_plan_status", "plan_id", "status"),
        {"schema": "hr"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("hr.hr_onboarding_plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(sa.Text, nullable=False)
    # TASK|DOCUMENT|ACTION
    task_type: Mapped[str] = mapped_column(
        sa.String(16), nullable=False, server_default="TASK"
    )
    # PENDING|DONE|BLOCKED
    status: Mapped[str] = mapped_column(
        sa.String(16), nullable=False, server_default="PENDING", index=True
    )
    sort_order: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, server_default="0"
    )

    due_date: Mapped[date | None] = mapped_column(sa.Date, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )

    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
    )

    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
        nullable=False,
    )

    plan: Mapped["HROnboardingPlan"] = relationship(back_populates="tasks")


class HREmployeeDocument(Base):
    """
    One onboarding document uploaded for an employee.

    Storage:
    - file_path is stored as a path RELATIVE to settings.data_dir (portable).
    - files are stored under: hr/onboarding/{employee_id}/{document_id}/files/{filename}
    """

    __tablename__ = "hr_employee_documents"
    __table_args__ = (
        sa.Index("ix_hr_employee_documents_employee_id", "employee_id"),
        sa.Index("ix_hr_employee_documents_plan_id", "plan_id"),
        sa.Index("ix_hr_employee_documents_doc_type", "doc_type"),
        {"schema": "hr"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("hr.hr_onboarding_plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("core.employees.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    doc_type: Mapped[str] = mapped_column(sa.String(32), nullable=False, index=True)
    original_filename: Mapped[str] = mapped_column(sa.Text, nullable=False)
    file_path: Mapped[str] = mapped_column(sa.Text, nullable=False)

    # UPLOADED|VERIFIED|REJECTED
    status: Mapped[str] = mapped_column(
        sa.String(16), nullable=False, server_default="UPLOADED", index=True
    )
    verified_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )

    plan: Mapped["HROnboardingPlan"] = relationship(back_populates="documents")
    employee: Mapped["Employee"] = relationship()
