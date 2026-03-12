# Notifications

- In-app notifications are typically generated through workflow or module hooks and delivered through the notification outbox pipeline.
- Notification rules are module-specific, but the platform conventions are:
  - dedupe where needed
  - notify the smallest correct audience
  - avoid leaking data across participant boundaries

Common notification sources:
- workflow request lifecycle changes
- DMS verification and expiry events
- onboarding task/document updates
- payroll payslip publication

Module docs should describe exactly who is notified and when.
