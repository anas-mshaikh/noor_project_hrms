"""
Permission vocabulary (single source of truth).

We use colon-style permission codes in the application layer (RBAC enforcement)
and seed them into iam.permissions via migration.
"""

TENANCY_READ = "tenancy:read"
TENANCY_WRITE = "tenancy:write"

IAM_USER_READ = "iam:user:read"
IAM_USER_WRITE = "iam:user:write"
IAM_ROLE_ASSIGN = "iam:role:assign"
IAM_PERMISSION_READ = "iam:permission:read"

HR_EMPLOYEE_READ = "hr:employee:read"
HR_EMPLOYEE_WRITE = "hr:employee:write"
HR_TEAM_READ = "hr:team:read"

ESS_PROFILE_READ = "ess:profile:read"
ESS_PROFILE_WRITE = "ess:profile:write"

NOTIFICATIONS_READ = "notifications:read"

VISION_CAMERA_READ = "vision:camera:read"
VISION_CAMERA_WRITE = "vision:camera:write"
VISION_VIDEO_UPLOAD = "vision:video:upload"
VISION_JOB_RUN = "vision:job:run"
VISION_RESULTS_READ = "vision:results:read"

FACE_LIBRARY_READ = "face:library:read"
FACE_LIBRARY_WRITE = "face:library:write"
FACE_RECOGNIZE = "face:recognize"

WORK_TASK_READ = "work:task:read"
WORK_TASK_WRITE = "work:task:write"
WORK_TASK_AUTO_ASSIGN = "work:task:auto_assign"

IMPORTS_READ = "imports:read"
IMPORTS_WRITE = "imports:write"

MOBILE_SYNC = "mobile:sync"
MOBILE_ACCOUNTS_READ = "mobile:accounts:read"
MOBILE_ACCOUNTS_WRITE = "mobile:accounts:write"

# HR module (recruiting pipeline in schema `hr`)
HR_RECRUITING_READ = "hr:recruiting:read"
HR_RECRUITING_WRITE = "hr:recruiting:write"

# Workflow engine (schema `workflow`)
WORKFLOW_REQUEST_SUBMIT = "workflow:request:submit"
WORKFLOW_REQUEST_READ = "workflow:request:read"
WORKFLOW_REQUEST_APPROVE = "workflow:request:approve"
WORKFLOW_REQUEST_ADMIN = "workflow:request:admin"
WORKFLOW_DEFINITION_READ = "workflow:definition:read"
WORKFLOW_DEFINITION_WRITE = "workflow:definition:write"

# DMS (schema `dms`)
DMS_FILE_READ = "dms:file:read"
DMS_FILE_WRITE = "dms:file:write"
DMS_DOCUMENT_TYPE_READ = "dms:document-type:read"
DMS_DOCUMENT_TYPE_WRITE = "dms:document-type:write"
DMS_DOCUMENT_READ = "dms:document:read"
DMS_DOCUMENT_WRITE = "dms:document:write"
DMS_DOCUMENT_VERIFY = "dms:document:verify"
DMS_EXPIRY_READ = "dms:expiry:read"
DMS_EXPIRY_WRITE = "dms:expiry:write"

# Leave (schema `leave`)
LEAVE_TYPE_READ = "leave:type:read"
LEAVE_TYPE_WRITE = "leave:type:write"
LEAVE_POLICY_READ = "leave:policy:read"
LEAVE_POLICY_WRITE = "leave:policy:write"
LEAVE_ALLOCATION_WRITE = "leave:allocation:write"
LEAVE_BALANCE_READ = "leave:balance:read"
LEAVE_REQUEST_SUBMIT = "leave:request:submit"
LEAVE_REQUEST_READ = "leave:request:read"
LEAVE_TEAM_READ = "leave:team:read"
LEAVE_ADMIN_READ = "leave:admin:read"

# Attendance regularization (schema `attendance`)
ATTENDANCE_CORRECTION_SUBMIT = "attendance:correction:submit"
ATTENDANCE_CORRECTION_READ = "attendance:correction:read"
ATTENDANCE_TEAM_READ = "attendance:team:read"
ATTENDANCE_ADMIN_READ = "attendance:admin:read"

# Attendance punching (schema `attendance`)
ATTENDANCE_PUNCH_SUBMIT = "attendance:punch:submit"
ATTENDANCE_PUNCH_READ = "attendance:punch:read"
ATTENDANCE_TIME_READ = "attendance:time:read"
ATTENDANCE_SETTINGS_WRITE = "attendance:settings:write"

# Roster v1 (schema `roster`)
ROSTER_SHIFT_READ = "roster:shift:read"
ROSTER_SHIFT_WRITE = "roster:shift:write"
ROSTER_ASSIGNMENT_READ = "roster:assignment:read"
ROSTER_ASSIGNMENT_WRITE = "roster:assignment:write"
ROSTER_OVERRIDE_READ = "roster:override:read"
ROSTER_OVERRIDE_WRITE = "roster:override:write"
ROSTER_DEFAULTS_WRITE = "roster:defaults:write"

# Payable summaries v1 (schema `attendance`)
ATTENDANCE_PAYABLE_READ = "attendance:payable:read"
ATTENDANCE_PAYABLE_TEAM_READ = "attendance:payable:team:read"
ATTENDANCE_PAYABLE_ADMIN_READ = "attendance:payable:admin:read"
ATTENDANCE_PAYABLE_RECOMPUTE = "attendance:payable:recompute"

# HR profile change (schema `hr_core`)
HR_PROFILE_CHANGE_SUBMIT = "hr:profile-change:submit"
HR_PROFILE_CHANGE_READ = "hr:profile-change:read"
HR_PROFILE_CHANGE_APPLY = "hr:profile-change:apply"

# Onboarding v2 (schema `onboarding`)
ONBOARDING_TEMPLATE_READ = "onboarding:template:read"
ONBOARDING_TEMPLATE_WRITE = "onboarding:template:write"
ONBOARDING_BUNDLE_READ = "onboarding:bundle:read"
ONBOARDING_BUNDLE_WRITE = "onboarding:bundle:write"
ONBOARDING_TASK_READ = "onboarding:task:read"
ONBOARDING_TASK_SUBMIT = "onboarding:task:submit"

# Payroll foundation v1 (schema `payroll`)
PAYROLL_CALENDAR_READ = "payroll:calendar:read"
PAYROLL_CALENDAR_WRITE = "payroll:calendar:write"
PAYROLL_COMPONENT_READ = "payroll:component:read"
PAYROLL_COMPONENT_WRITE = "payroll:component:write"
PAYROLL_STRUCTURE_READ = "payroll:structure:read"
PAYROLL_STRUCTURE_WRITE = "payroll:structure:write"
PAYROLL_COMPENSATION_READ = "payroll:compensation:read"
PAYROLL_COMPENSATION_WRITE = "payroll:compensation:write"
PAYROLL_PAYRUN_GENERATE = "payroll:payrun:generate"
PAYROLL_PAYRUN_READ = "payroll:payrun:read"
PAYROLL_PAYRUN_SUBMIT = "payroll:payrun:submit"
PAYROLL_PAYRUN_PUBLISH = "payroll:payrun:publish"
PAYROLL_PAYRUN_EXPORT = "payroll:payrun:export"
PAYROLL_PAYSLIP_READ = "payroll:payslip:read"
PAYROLL_PAYSLIP_PUBLISH = "payroll:payslip:publish"
PAYROLL_ADMIN_READ = "payroll:admin:read"


ALL_PERMISSION_CODES: tuple[str, ...] = (
    TENANCY_READ,
    TENANCY_WRITE,
    IAM_USER_READ,
    IAM_USER_WRITE,
    IAM_ROLE_ASSIGN,
    IAM_PERMISSION_READ,
    HR_EMPLOYEE_READ,
    HR_EMPLOYEE_WRITE,
    HR_TEAM_READ,
    ESS_PROFILE_READ,
    ESS_PROFILE_WRITE,
    NOTIFICATIONS_READ,
    VISION_CAMERA_READ,
    VISION_CAMERA_WRITE,
    VISION_VIDEO_UPLOAD,
    VISION_JOB_RUN,
    VISION_RESULTS_READ,
    FACE_LIBRARY_READ,
    FACE_LIBRARY_WRITE,
    FACE_RECOGNIZE,
    WORK_TASK_READ,
    WORK_TASK_WRITE,
    WORK_TASK_AUTO_ASSIGN,
    IMPORTS_READ,
    IMPORTS_WRITE,
    MOBILE_SYNC,
    MOBILE_ACCOUNTS_READ,
    MOBILE_ACCOUNTS_WRITE,
    HR_RECRUITING_READ,
    HR_RECRUITING_WRITE,
    WORKFLOW_REQUEST_SUBMIT,
    WORKFLOW_REQUEST_READ,
    WORKFLOW_REQUEST_APPROVE,
    WORKFLOW_REQUEST_ADMIN,
    WORKFLOW_DEFINITION_READ,
    WORKFLOW_DEFINITION_WRITE,
    DMS_FILE_READ,
    DMS_FILE_WRITE,
    DMS_DOCUMENT_TYPE_READ,
    DMS_DOCUMENT_TYPE_WRITE,
    DMS_DOCUMENT_READ,
    DMS_DOCUMENT_WRITE,
    DMS_DOCUMENT_VERIFY,
    DMS_EXPIRY_READ,
    DMS_EXPIRY_WRITE,
    LEAVE_TYPE_READ,
    LEAVE_TYPE_WRITE,
    LEAVE_POLICY_READ,
    LEAVE_POLICY_WRITE,
    LEAVE_ALLOCATION_WRITE,
    LEAVE_BALANCE_READ,
    LEAVE_REQUEST_SUBMIT,
    LEAVE_REQUEST_READ,
    LEAVE_TEAM_READ,
    LEAVE_ADMIN_READ,
    ATTENDANCE_CORRECTION_SUBMIT,
    ATTENDANCE_CORRECTION_READ,
    ATTENDANCE_TEAM_READ,
    ATTENDANCE_ADMIN_READ,
    ATTENDANCE_PUNCH_SUBMIT,
    ATTENDANCE_PUNCH_READ,
    ATTENDANCE_TIME_READ,
    ATTENDANCE_SETTINGS_WRITE,
    ROSTER_SHIFT_READ,
    ROSTER_SHIFT_WRITE,
    ROSTER_ASSIGNMENT_READ,
    ROSTER_ASSIGNMENT_WRITE,
    ROSTER_OVERRIDE_READ,
    ROSTER_OVERRIDE_WRITE,
    ROSTER_DEFAULTS_WRITE,
    ATTENDANCE_PAYABLE_READ,
    ATTENDANCE_PAYABLE_TEAM_READ,
    ATTENDANCE_PAYABLE_ADMIN_READ,
    ATTENDANCE_PAYABLE_RECOMPUTE,
    HR_PROFILE_CHANGE_SUBMIT,
    HR_PROFILE_CHANGE_READ,
    HR_PROFILE_CHANGE_APPLY,
    ONBOARDING_TEMPLATE_READ,
    ONBOARDING_TEMPLATE_WRITE,
    ONBOARDING_BUNDLE_READ,
    ONBOARDING_BUNDLE_WRITE,
    ONBOARDING_TASK_READ,
    ONBOARDING_TASK_SUBMIT,
    PAYROLL_CALENDAR_READ,
    PAYROLL_CALENDAR_WRITE,
    PAYROLL_COMPONENT_READ,
    PAYROLL_COMPONENT_WRITE,
    PAYROLL_STRUCTURE_READ,
    PAYROLL_STRUCTURE_WRITE,
    PAYROLL_COMPENSATION_READ,
    PAYROLL_COMPENSATION_WRITE,
    PAYROLL_PAYRUN_GENERATE,
    PAYROLL_PAYRUN_READ,
    PAYROLL_PAYRUN_SUBMIT,
    PAYROLL_PAYRUN_PUBLISH,
    PAYROLL_PAYRUN_EXPORT,
    PAYROLL_PAYSLIP_READ,
    PAYROLL_PAYSLIP_PUBLISH,
    PAYROLL_ADMIN_READ,
)
