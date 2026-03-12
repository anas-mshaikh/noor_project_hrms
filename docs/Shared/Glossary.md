# Glossary

- **Tenant** - top-level isolation boundary for data, permissions, and configuration.
- **Company** - legal or operating entity under a tenant.
- **Branch** - operational location or sub-entity used for scope, calendars, and scheduling.
- **ESS** - Employee Self Service surface.
- **MSS** - Manager Self Service surface.
- **Workflow Request** - approval or review item tracked through `workflow.requests`.
- **Correlation ID** - request trace identifier returned in `X-Correlation-Id` and surfaced in error payloads.
- **Participant-safe** - a deny behavior that does not leak whether a resource exists.
- **Payrun** - a payroll calculation batch for a period and branch.
- **Payables** - payroll input layer that computes payable days and minutes.
- **Override** - a deterministic record that supersedes base status or schedule for a given employee/day.
- **Document Verification** - workflow-driven DMS review process for employee documents.
- **Employee 360** - consolidated HR profile and employment view for an employee.
- **Current employment** - the employee's active employment context used to derive company and branch in many flows.
- **Legacy Vision Attendance** - the earlier CCTV and import-based attendance pipeline retained for backward compatibility.
