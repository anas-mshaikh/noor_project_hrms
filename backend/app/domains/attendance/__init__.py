from __future__ import annotations

# Register workflow side-effects for attendance corrections.
from app.domains.attendance.workflow_handler import AttendanceCorrectionWorkflowHandler
from app.domains.workflow import hooks as workflow_hooks


workflow_hooks.register("attendance.attendance_correction", AttendanceCorrectionWorkflowHandler())

