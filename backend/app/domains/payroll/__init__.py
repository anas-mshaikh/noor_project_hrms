"""
Payroll domain package (Milestone 9).

Responsibility:
- Provide payroll setup primitives (calendars/periods, components, structures,
  compensations).
- Compute deterministic payruns and materialize payrun items/lines.
- Integrate with Workflow Engine v1 for payrun approvals via terminal hooks.
- Publish payslips as JSON documents stored in DMS (v1; PDF later).

Import side-effects:
- Registers workflow terminal hook for entity_type="payroll.payrun".
"""

from __future__ import annotations

from app.domains.payroll.workflow_handler import PayrunWorkflowHandler
from app.domains.workflow import hooks as workflow_hooks


workflow_hooks.register("payroll.payrun", PayrunWorkflowHandler())

