# Testing Guidelines (Enterprise)

This repo uses **pytest** and follows a domain-driven layout for tests.

Core goals:
- deterministic tests (no external calls)
- strong tenant isolation + RBAC coverage
- fast CI by default (slow tests are opt-in)
- minimal E2E tests (high value flows only)

## 1) Test pyramid

### Unit tests (`-m unit`)
Use for:
- pure functions (validation, normalization, mapping)
- date math / cursor parsing
- idempotency comparisons

Rules:
- no DB access
- no HTTP calls
- no sleeps/timeouts

### Integration tests (`-m integration`)
Use for:
- database + service-layer behavior
- transactions, constraints, `SELECT ... FOR UPDATE` flows

Rules:
- no HTTP
- use rollback-based DB fixtures when possible
- assert on DB rows and invariants

### API tests (`-m api`)
Use for:
- HTTP layer correctness (routes, auth, envelope)
- validation + error codes
- pagination contract (cursor format)

Rules:
- assert stable error `code` values (not brittle messages)
- prefer AAA structure in every test

### Contract tests (`-m contract`)
Use for:
- OpenAPI / schema rules
- "no legacy paths" constraints

### E2E tests (`-m e2e`)
Use sparingly for:
- highest value end-to-end flows across domains (1–3 per domain max)
  - e.g., onboarding packet -> HR profile change -> manager approve -> hr_core mutated

Rules:
- keep count low
- keep assertions to domain facts (statuses + DB rows)

## 2) Tenant isolation + RBAC (mandatory negative tests)

For every endpoint that mutates data, add negative tests for:
- **tenant isolation**: cross-tenant access must not leak existence
  - participant-only resources return **404**
- **RBAC deny**: missing permission returns **403**
- **participant-only**: non-owner cannot read/cancel/submit -> **404**
- **idempotency**:
  - same idempotency key + same payload returns same entity
  - same key + different payload -> **409** with stable code
- **concurrency safety**:
  - double-approve races return **409 workflow.step.already_decided**

## 3) Determinism rules (golden rules)

- Always generate unique codes using short UUID suffixes for:
  - workflow definition codes
  - employee codes
  - document type codes (in tests)
- Never depend on ordering unless you explicitly `ORDER BY` deterministic columns.
- Prefer `notification_worker.consume_once()` over sleeps.
- Always include explicit scope headers in API tests:
  - `X-Tenant-Id`, `X-Company-Id`, `X-Branch-Id`

## 4) Stability and maintainability

- Keep tests small and focused (one concept per test).
- Use reusable fixtures and factories to avoid copy-paste setup.
- Use AAA structure:
  - Arrange
  - Act
  - Assert

## 5) Markers and CI

- CI runs fast tests by default (`-m "not slow"`).
- Mark slow tests with `@pytest.mark.slow` so they are opt-in.

