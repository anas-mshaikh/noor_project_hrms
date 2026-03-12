# Audit Logging

- Critical HRMS mutations should record audit events with stable `action` and `entity_type` naming.
- Audit payloads should be minimal and should avoid leaking secrets or unnecessary PII.
- Module docs should list their own important audit events; this shared document defines the cross-cutting expectation that auditable state changes are traceable.

Typical audited actions include:
- create, update, assign, approve, reject, cancel, publish, verify, and finalize operations

Source references:
- `audit.audit_log`
- domain services under `backend/app/domains/*`
