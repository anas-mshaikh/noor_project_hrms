# Documentation Index

This index points to the canonical module-first documentation for Noor HRMS.

## How to use this documentation

- Use `docs/MODULE_CATALOG.md` to find the authoritative internal and customer document for any module.
- Use `docs/Shared/` for platform-wide conventions that should not be duplicated inside modules.
- Use `docs/Modules/<ModuleName>/<ModuleName>.Internal.md` as the engineering and product source of truth.
- Use `docs/Modules/<ModuleName>/<ModuleName>.Customer.md` for client-facing, admin-facing, or end-user handoff.

## Core navigation

- Docs system overview: `docs/README.md`
- Module catalog: `docs/MODULE_CATALOG.md`
- Authoring rules: `docs/CONTRIBUTING.md`
- Shared platform docs: `docs/Shared/`
- Module docs: `docs/Modules/`

## Active HRMS modules

- `docs/Modules/TenancyOrganization/TenancyOrganization.Internal.md`
- `docs/Modules/AccessIAM/AccessIAM.Internal.md`
- `docs/Modules/Workflow/Workflow.Internal.md`
- `docs/Modules/HRCore/HRCore.Internal.md`
- `docs/Modules/Recruitment/Recruitment.Internal.md`
- `docs/Modules/Onboarding/Onboarding.Internal.md`
- `docs/Modules/ProfileChange/ProfileChange.Internal.md`
- `docs/Modules/Attendance/Attendance.Internal.md`
- `docs/Modules/Leave/Leave.Internal.md`
- `docs/Modules/DMS/DMS.Internal.md`
- `docs/Modules/Roster/Roster.Internal.md`
- `docs/Modules/Payables/Payables.Internal.md`
- `docs/Modules/Payroll/Payroll.Internal.md`

## Legacy and partial modules

- `docs/Modules/LegacyVisionAttendance/LegacyVisionAttendance.Internal.md`
- `docs/Modules/LegacyAdminImport/LegacyAdminImport.Internal.md`
- `docs/Modules/MobileMapping/MobileMapping.Internal.md`
- `docs/Modules/WorkTasks/WorkTasks.Internal.md`
- `docs/Modules/Notes/Notes.Internal.md`


## Support and reference material

- `docs/CI_CD/` - operational CI/CD, release, rollback, and support runbooks.
- `docs/backend/openapi/` - checked-in backend OpenAPI snapshot.
- `docs/references/` - external reference material preserved for context, not canonical product docs.
- `docs/Demo_videos/` - demo recordings preserved as supporting assets.

## Migration map

| Old path | New canonical path | Notes |
| --- | --- | --- |
| `docs/Modules/Leave/LEAVE.md` | `docs/Modules/Leave/Leave.Internal.md` | Retired and absorbed into the module master doc. |
| `docs/Modules/Attendance/ATTENDANCE_PUNCHING.md` | `docs/Modules/Attendance/Attendance.Internal.md` | Retired and folded into the Attendance master doc. |
| `docs/Modules/Attendance/ATTENDANCE_REGULARIZATION.md` | `docs/Modules/Attendance/Attendance.Internal.md` | Retired and folded into the Attendance master doc. |
| `docs/Modules/DMS/DMS.md` | `docs/Modules/DMS/DMS.Internal.md` | Retired and absorbed into the DMS master doc. |
| `docs/Modules/M7_DMS.md` | `docs/Modules/DMS/DMS.Internal.md` | Retired and folded into the DMS module docs. |
| `docs/Modules/Onboarding/ONBOARDING_V2.md` | `docs/Modules/Onboarding/Onboarding.Internal.md` | Retired and replaced by the canonical module master doc. |
| `docs/Modules/ESS/PROFILE_CHANGE_V1.md` | `docs/Modules/ProfileChange/ProfileChange.Internal.md` | Retired; profile change now has its own module folder. |
| `docs/Modules/Payroll/ROSTER_V1.md` | `docs/Modules/Roster/Roster.Internal.md` | Retired and split into the Roster module. |
| `docs/Modules/Payroll/PAYABLE_SUMMARIES_V1.md` | `docs/Modules/Payables/Payables.Internal.md` | Retired and split into the Payables module. |
| `docs/Modules/Payroll/PAYROLL_V1.md` | `docs/Modules/Payroll/Payroll.Internal.md` | Retired and replaced by the Payroll module master doc. |
| `docs/Modules/M8_ROSTER_PAYABLES.md` | `docs/Modules/Roster/Roster.Internal.md` and `docs/Modules/Payables/Payables.Internal.md` | Retired and split by business module. |
| `docs/Modules/M9_PAYROLL.md` | `docs/Modules/Payroll/Payroll.Internal.md` | Retired and folded into Payroll. |
| `docs/frontend/M4_HR_CORE_EMPLOYEE_360.md` | `docs/Modules/HRCore/HRCore.Internal.md` | Retired and folded into HR Core. |
| `docs/frontend/M5_WORKFLOW.md` | `docs/Modules/Workflow/Workflow.Internal.md` | Retired and folded into Workflow. |
| `docs/frontend/M6_ATTENDANCE_LEAVE.md` | `docs/Modules/Attendance/Attendance.Internal.md` and `docs/Modules/Leave/Leave.Internal.md` | Retired and split by business module. |
| `docs/backend/DB_&_API/API_CORE.md` | `docs/Shared/API-Conventions.md` and `docs/Shared/Error-Handling.md` | Retired and replaced by shared platform docs. |
| `docs/backend/DB_&_API/DB_VNEXT.md` | `docs/Shared/Architecture.md` and module data-model sections | Retired and absorbed into shared architecture plus module data-model sections. |

## Known gaps that still need human input

- Customer-approved wording for legacy and partial modules.
- Final screenshots, flows, and wireframes for modules that currently have no maintained visual assets.
- Support ownership and escalation contacts per module.
- Compliance, retention, and legal-policy language that is not verifiable from the codebase.
- Clarification of the long-term product direction for `Notes`, `WorkTasks`, and some mobile/legacy surfaces.
