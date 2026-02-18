from __future__ import annotations

"""
DMS domain package.

Import side-effects:
- Registers workflow terminal hooks for entity_type="dms.document".

The workflow engine imports this package indirectly when DMS routers/services
are imported, ensuring hooks are available in both API and worker processes.
"""

from app.domains.dms.workflow_handler import DmsDocumentWorkflowHandler
from app.domains.workflow import hooks as workflow_hooks


workflow_hooks.register("dms.document", DmsDocumentWorkflowHandler())

