# Attendance System

Phase 1 (CCTV attendance, offline):
- Upload door camera video → worker processes → events + attendance + analytics

Phase 2 (Admin Import, Excel → Postgres → optional Firebase replica):
- Admin uploads monthly `.xlsx` (POS + Attendance sheets) → backend parses/validates → stores normalized summaries in Postgres
- Optional publish step can sync summary-only docs to Firebase Firestore for a mobile app

## Local dev (Docker Compose)

Run:

```bash
docker compose up --build
```

Services:
- Web (Next.js): `http://localhost:3000`
- API (FastAPI docs): `http://localhost:8000/docs`
- Postgres (pgvector): `localhost:5432` (db/user/pass: `attendance`)
- Adminer (DB UI): `http://localhost:8080`

Notes:
- DB migrations run automatically via the `migrate` service.
- Persistent data and outputs live under `backend/data/` (mounted into containers).
- Models live under `backend/models/` (mounted into containers).

## Phase 2 Admin Import (Excel)

Frontend page:
- `http://localhost:3000/admin/import`

Dev-only admin gate:
- In docker-compose, `ADMIN_PASSWORD` defaults to `admin`. Override with:
  ```bash
  ADMIN_PASSWORD="your-secret" docker compose up --build
  ```

Backend endpoints:
- `POST /api/v1/imports` (multipart: `file`, optional `month_key=YYYY-MM`, optional `uploaded_by`)
- `POST /api/v1/imports/{dataset_id}/publish`
- `GET /api/v1/months/{month_key}/leaderboard`

Import retry behavior:
- Uploads are idempotent per month by `(month_key, checksum)` (same file returns the same `dataset_id`).
- If an import previously `FAILED`, re-uploading the same file will re-validate it (controlled by `IMPORTS_REVALIDATE_FAILED_ON_REUPLOAD`, default `true`).

Firebase sync (optional):
- Set `FIREBASE_SYNC_ENABLED=true` and provide `FIREBASE_SERVICE_ACCOUNT_PATH` (mounted in the container).
