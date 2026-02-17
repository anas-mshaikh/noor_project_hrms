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
)
