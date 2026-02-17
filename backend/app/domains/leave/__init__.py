from __future__ import annotations

# Register workflow side-effects for leave requests.
from app.domains.leave.workflow_handler import LeaveWorkflowHandler
from app.domains.workflow import hooks as workflow_hooks


workflow_hooks.register("leave.leave_request", LeaveWorkflowHandler())

