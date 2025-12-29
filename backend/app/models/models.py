import uuid
from datetime import date, datetime
from typing import Any

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Organization(Base):
    __tablename__ = "organizations"

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

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("organizations.id", ondelete="CASCADE"),
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
    videos: Mapped[list["Video"]] = relationship(back_populates="store")
    attendance_daily: Mapped[list["AttendanceDaily"]] = relationship(
        back_populates="store"
    )


class Camera(Base):
    __tablename__ = "cameras"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("stores.id", ondelete="CASCADE"),
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
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("stores.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    employee_code: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default=sa.true()
    )

    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )

    store: Mapped[Store] = relationship(back_populates="employees")
    faces: Mapped[list["EmployeeFace"]] = relationship(back_populates="employee")
    attendance_daily: Mapped[list["AttendanceDaily"]] = relationship(
        back_populates="employee"
    )


class EmployeeFace(Base):
    __tablename__ = "employee_faces"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("employees.id", ondelete="CASCADE"),
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


class Video(Base):
    __tablename__ = "videos"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("stores.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    camera_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("cameras.id", ondelete="CASCADE"),
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
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    video_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("videos.id", ondelete="CASCADE"),
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
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("jobs.id", ondelete="CASCADE"),
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
        sa.ForeignKey("employees.id", ondelete="SET NULL"),
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
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    ts: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)

    event_type: Mapped[str] = mapped_column(sa.String(16), nullable=False)

    entrance_id: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    track_key: Mapped[str] = mapped_column(sa.String(64), nullable=False)

    employee_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("employees.id", ondelete="SET NULL"),
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
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("stores.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    business_date: Mapped[date] = mapped_column(sa.Date, nullable=False, index=True)

    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("employees.id", ondelete="RESTRICT"),
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
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("jobs.id", ondelete="CASCADE"),
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
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("jobs.id", ondelete="CASCADE"),
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
