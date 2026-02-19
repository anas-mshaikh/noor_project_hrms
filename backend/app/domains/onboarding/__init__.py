"""
Onboarding v2 domain package (Milestone 6).

Responsibility:
- HR defines onboarding templates and template tasks.
- HR instantiates an employee bundle (snapshot tasks).
- ESS submits tasks (forms, documents, acknowledgements).
- Packet submission integrates with HR profile change requests (workflow-powered).

This package intentionally has no import side-effects (no workflow hooks). Any
terminal side-effects are handled by the relevant domain hooks:
- Profile change requests: app.domains.profile_change
- DMS document verification: app.domains.dms
"""

from __future__ import annotations
