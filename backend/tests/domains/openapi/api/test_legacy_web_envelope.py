from __future__ import annotations

import os
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.models import Camera, Event, Job, Video


pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="DATABASE_URL not set; skipping API integration tests",
)


def test_health_is_enveloped(client_factory) -> None:
    client = client_factory(["app.api.v1.health"])
    r = client.get("/api/v1/health")
    assert r.status_code == 200, r.text
    assert r.json() == {"ok": True, "data": {"status": "ok"}}


def test_vision_cameras_list_is_enveloped(client_factory, tenant_factory, actor_factory) -> None:
    client = client_factory(["app.auth.router", "app.api.v1.cameras"])
    tenant = tenant_factory()
    admin = actor_factory(client, tenant, "ADMIN")

    r = client.get(f"/api/v1/branches/{tenant.branch_id}/cameras", headers=admin.headers())
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert isinstance(body["data"], list)


def test_results_download_event_snapshot_stays_raw(
    client_factory, tenant_factory, actor_factory, db_engine
) -> None:
    """
    File endpoints must remain raw (not the JSON envelope) on success.
    """
    client = client_factory(["app.auth.router", "app.api.v1.results"])
    tenant = tenant_factory()
    admin = actor_factory(client, tenant, "ADMIN")

    snapshot_rel = f"test_snapshots/{uuid.uuid4()}.jpg"
    snapshot_abs = Path(settings.data_dir) / snapshot_rel
    snapshot_abs.parent.mkdir(parents=True, exist_ok=True)
    snapshot_abs.write_bytes(b"fake-jpg-bytes")

    tenant_id = uuid.UUID(tenant.tenant_id)
    branch_id = uuid.UUID(tenant.branch_id)
    camera_id = uuid.uuid4()
    video_id = uuid.uuid4()
    job_id = uuid.uuid4()
    event_id = uuid.uuid4()

    with Session(db_engine) as db:
        cam = Camera(id=camera_id, tenant_id=tenant_id, branch_id=branch_id, name="T1", placement=None)
        db.add(cam)

        vid = Video(
            id=video_id,
            tenant_id=tenant_id,
            branch_id=branch_id,
            camera_id=camera_id,
            business_date=date(2026, 2, 1),
            file_path=f"videos/{tenant.tenant_id}/{tenant.branch_id}/{camera_id}/x.mp4",
        )
        db.add(vid)

        job = Job(
            id=job_id,
            tenant_id=tenant_id,
            video_id=video_id,
            status="DONE",
            progress=100,
        )
        db.add(job)

        ev = Event(
            id=event_id,
            tenant_id=tenant_id,
            job_id=job_id,
            ts=datetime(2026, 2, 1, 8, 0, tzinfo=timezone.utc),
            event_type="entry",
            entrance_id=None,
            track_key="t1",
            employee_id=None,
            confidence=0.9,
            snapshot_path=snapshot_rel,
            is_inferred=False,
            meta={},
        )
        db.add(ev)
        db.commit()

    r = client.get(
        f"/api/v1/branches/{tenant.branch_id}/events/{event_id}/snapshot",
        headers=admin.headers(),
    )
    assert r.status_code == 200, r.text
    assert r.headers.get("content-type", "").startswith("image/")
    assert r.content == b"fake-jpg-bytes"

    # Best-effort cleanup of the file (DB cleanup is handled by tenant teardown).
    snapshot_abs.unlink(missing_ok=True)


def test_face_list_is_enveloped(client_factory, tenant_factory, actor_factory) -> None:
    client = client_factory(["app.auth.router", "app.face_system.api"])
    tenant = tenant_factory()
    admin = actor_factory(client, tenant, "ADMIN")

    r = client.get(f"/api/v1/branches/{tenant.branch_id}/faces", headers=admin.headers())
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["data"]["tenant_id"] == tenant.tenant_id
    assert body["data"]["branch_id"] == tenant.branch_id
    assert isinstance(body["data"]["employees"], list)


def test_hr_openings_list_is_enveloped_and_opening_not_found_code(
    client_factory, tenant_factory, actor_factory
) -> None:
    client = client_factory(["app.auth.router", "app.api.v1.openings"])
    tenant = tenant_factory()
    admin = actor_factory(client, tenant, "ADMIN")

    r = client.get(f"/api/v1/branches/{tenant.branch_id}/openings", headers=admin.headers())
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert isinstance(body["data"], list)

    missing_id = uuid.uuid4()
    r2 = client.get(
        f"/api/v1/branches/{tenant.branch_id}/openings/{missing_id}",
        headers=admin.headers(),
    )
    assert r2.status_code == 404, r2.text
    j2 = r2.json()
    assert j2["ok"] is False
    assert j2["error"]["code"] == "hr.opening.not_found"
