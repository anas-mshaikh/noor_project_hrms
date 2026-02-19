"""
Profile change domain package (Milestone 6).

Responsibility:
- Persist employee profile change requests (first-class records).
- Integrate with Workflow Engine v1 via entity hooks so that terminal approvals
  apply changes to hr_core.* inside the same DB transaction.

Import side-effects:
- Registers workflow terminal hook for entity_type="hr_core.profile_change_request".
"""

from __future__ import annotations

from app.domains.profile_change.workflow_handler import ProfileChangeWorkflowHandler
from app.domains.workflow import hooks as workflow_hooks


# Register hook once at import time.
workflow_hooks.register(
    "hr_core.profile_change_request",
    ProfileChangeWorkflowHandler(),
)
