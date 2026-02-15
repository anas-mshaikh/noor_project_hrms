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

## DB vNext (enterprise foundation)

DB vNext introduces enterprise-ready HRMS foundation schemas (`tenancy`, `iam`, `hr_core`, `workflow`, `dms`) in the **same** Postgres database.

- Details: `docs/DB_VNEXT.md`
- Smoke test: `python3 backend/scripts/db_vnext_smoke_test.py`
  - In Docker Compose, this also runs automatically via the `tests` service.

Current API foundation state:
- Legacy `/api/v1/organizations*` and `/api/v1/stores*` routes are removed.
- Module APIs are branch-first (`/api/v1/branches/{branch_id}/...`).
- Protected endpoints are tenant-scoped and permission-driven (RBAC via `iam.*`).
- Multi-tenant users must send `X-Tenant-Id`; single-tenant users default automatically.
- Responses include `X-Correlation-Id`; errors include `correlation_id`.
- Critical IAM/HR mutations are audited in `audit.audit_log`.
- In-app notifications flow through `workflow.notification_outbox` -> `workflow.notifications`.

### Safety backup / restore (dev)

Backup (schema + data) using the Docker `db` container (no local Postgres tools required):

```bash
mkdir -p backups
docker compose exec -T db pg_dump -U attendance -d attendance --format=custom --file /tmp/attendance.dump
docker compose cp db:/tmp/attendance.dump ./backups/attendance.dump
```

Restore (OVERWRITES the database):

```bash
docker compose cp ./backups/attendance.dump db:/tmp/attendance.dump
docker compose exec -T db pg_restore -U attendance -d attendance --clean --if-exists /tmp/attendance.dump
```

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
- Provide `FIREBASE_SERVICE_ACCOUNT_PATH` (mounted in the container) and set `MOBILE_SYNC_ENABLED=true`.

## HR module (Phase 1: Openings + Resume parsing)

What it does:
- Create branch-scoped hiring openings
- Upload resumes to local disk
- Parse resumes in the background using RQ + Unstructured
- Store parsed artifacts locally (`parsed.json` + `clean.txt`) for debugging

Docker services:
- The `hr_worker` service listens on the RQ queue named `hr`.

Key endpoints:
- `POST /api/v1/branches/{branch_id}/openings`
- `GET  /api/v1/branches/{branch_id}/openings`
- `GET  /api/v1/branches/{branch_id}/openings/{opening_id}`
- `PATCH /api/v1/branches/{branch_id}/openings/{opening_id}`
- `POST /api/v1/branches/{branch_id}/openings/{opening_id}/resumes/upload` (multipart files)
- `GET  /api/v1/branches/{branch_id}/openings/{opening_id}/resumes`
- `GET  /api/v1/branches/{branch_id}/resumes/{resume_id}/parsed` (debug artifact JSON)

Local storage paths:
- Raw uploads: `backend/data/hr/resumes/{opening_id}/{resume_id}/original/...`
- Parsed artifacts: `backend/data/hr/resumes/{opening_id}/{resume_id}/parsed/parsed.json`

## HR module (Phase 2: Resume embeddings + debug search)

What it adds:
- Builds 2–3 derived "views" per parsed resume (`full`, `skills`, `experience`)
- Embeds those views with a local HuggingFace model (default: `BAAI/bge-m3`)
- Stores embeddings in Postgres via `pgvector` for later retrieval/ranking

How it runs:
- Parsing happens first (`UPLOADED -> PARSING -> PARSED`)
- After a resume is `PARSED`, the worker automatically enqueues an embedding job:
  `PENDING -> EMBEDDING -> EMBEDDED` (or `FAILED`)

Key debug endpoints:
- `GET  /api/v1/branches/{branch_id}/openings/{opening_id}/resumes/index-status`
- `GET  /api/v1/branches/{branch_id}/resumes/{resume_id}/views`
- `POST /api/v1/branches/{branch_id}/openings/{opening_id}/search` (disabled unless `HR_SEARCH_DEBUG_ENABLED=true`)

Config (env vars):
- `HR_EMBEDDINGS_ENABLED=true|false`
- `HR_EMBED_MODEL_NAME="BAAI/bge-m3"` (model switch lever)
- `HR_EMBED_DIM=1024` (must match DB `vector(dim)`; change requires a migration)
- `HR_EMBED_CACHE_DIR="./models/text_embeddings"` (mounted in Docker via `backend/models`)
- `HR_EMBED_DEVICE="cpu"`
- `HR_EMBED_MAX_SEQ_LENGTH=8192`
- `HR_EMBED_MAX_CHARS=12000`
- `HR_VIEW_MIN_CHARS=120`
- `HR_SEARCH_DEBUG_ENABLED=false|true`

Note on model switching:
- The DB column is `vector(1024)` because BGE-M3 outputs 1024-d embeddings.
- Switching to a model with a different embedding dimension will require a migration.

## HR module (Phase 3: ScreeningRun = retrieve + rerank)

What it adds:
- An async "ScreeningRun" pipeline per opening:
  1) **retrieve** Top-K candidates using embeddings (pgvector)
  2) **rerank** a candidate pool using `BAAI/bge-reranker-v2-m3` (local, CPU OK)
  3) persist ranked results for paging / audit

Key endpoints:
- `POST /api/v1/branches/{branch_id}/openings/{opening_id}/screening-runs` (create + enqueue)
- `GET  /api/v1/branches/{branch_id}/screening-runs/{run_id}` (poll status + progress)
- `POST /api/v1/branches/{branch_id}/screening-runs/{run_id}/cancel`
- `POST /api/v1/branches/{branch_id}/screening-runs/{run_id}/retry` (creates a new run)
- `GET  /api/v1/branches/{branch_id}/screening-runs/{run_id}/results?page=1&page_size=50`

Config (env vars):
- `HR_RERANK_ENABLED=true|false`
- `HR_RERANKER_MODEL_NAME="BAAI/bge-reranker-v2-m3"`
- `HR_RERANKER_BATCH_SIZE=32`
- `HR_RERANKER_MAX_CHARS=12000`
- `HR_SCREENING_JOB_TIMEOUT_SEC=3600`
- Defaults for run config (optional overrides):
  - `HR_SCREENING_DEFAULT_VIEW_TYPES='["skills","experience","full"]'`
  - `HR_SCREENING_DEFAULT_K_PER_VIEW=200`
  - `HR_SCREENING_DEFAULT_POOL_SIZE=400`
  - `HR_SCREENING_DEFAULT_TOP_N=200`

## HR module (Phase 4: Explanations = Gemini JSON, async)

What it adds:
- Post-ranking explanations for top ScreeningRun candidates using Gemini (structured JSON).
- Stored in Postgres (`hr_screening_explanations`) as **JSON only** (no raw resume text stored).
- Runs asynchronously via RQ (queue: `"hr"`) so ScreeningRuns are not blocked.

Key endpoints:
- `GET  /api/v1/branches/{branch_id}/screening-runs/{run_id}/results/{resume_id}/explanation`
- `POST /api/v1/branches/{branch_id}/screening-runs/{run_id}/explanations` (enqueue explain top N)
- `POST /api/v1/branches/{branch_id}/screening-runs/{run_id}/results/{resume_id}/explanation/recompute` (enqueue single)

Config (env vars):
- `GEMINI_API_KEY="..."` (required to run Phase 4)
- `GEMINI_MODEL="gemini-2.0-flash-lite-001"`
- `GEMINI_TIMEOUT_SEC=60`
- `GEMINI_MAX_TOP_N=20` (cost/latency control)

Behavior notes:
- If `GEMINI_API_KEY` is missing/empty, the backend will **skip auto-enqueueing** explanations
  after ScreeningRun completion, and manual endpoints will return a clear 400 error.

## HR module (Phase 5: ATS MVP = pipeline stages + applications)

What it adds:
- A minimal Applicant Tracking System (ATS) layer on top of Openings + Resumes.
- Treats each **resume** as the applicant (MVP simplification: 1 resume = 1 application).
- Lets you create applications from ScreeningRun results (bulk) or manually, then move them
  through a pipeline (Kanban stages) and add notes.

Default pipeline stages:
- Created automatically when an opening is created:
  `Applied -> Screened -> Interview -> Offer -> Hired (terminal) / Rejected (terminal)`

Key endpoints:
- `GET  /api/v1/branches/{branch_id}/openings/{opening_id}/pipeline-stages`
- `POST /api/v1/branches/{branch_id}/screening-runs/{run_id}/applications` (bulk add to pipeline)
  - `{ "top_n": 20, "stage_name": "Screened" }`
  - OR `{ "resume_ids": ["..."], "stage_name": "Screened" }`
- `POST /api/v1/branches/{branch_id}/openings/{opening_id}/applications` (manual add)
  - `{ "resume_id": "...", "stage_name": "Applied" }`
- `GET  /api/v1/branches/{branch_id}/openings/{opening_id}/applications` (Kanban list)
- `PATCH /api/v1/branches/{branch_id}/applications/{application_id}` (move stage)
- `POST /api/v1/branches/{branch_id}/applications/{application_id}/reject`
- `POST /api/v1/branches/{branch_id}/applications/{application_id}/hire`
- Notes:
  - `POST /api/v1/branches/{branch_id}/applications/{application_id}/notes`
  - `GET  /api/v1/branches/{branch_id}/applications/{application_id}/notes`

## Notifications (Milestone 1)

In-app notifications are enabled (email is intentionally deferred).

Worker pipeline:
- Producer table: `workflow.notification_outbox`
- Consumer process: `backend/app/worker/notification_worker.py`
- User inbox table: `workflow.notifications`

API endpoints:
- `GET  /api/v1/notifications?unread_only=0|1&limit&cursor`
- `GET  /api/v1/notifications/unread-count`
- `POST /api/v1/notifications/{id}/read`
- `POST /api/v1/notifications/read-all`

## Test status and commands

Primary backend validation:

```bash
docker compose up --build --abort-on-container-exit --exit-code-from tests tests
```

Current baseline:
- Backend tests pass in Docker (`18 passed`).
