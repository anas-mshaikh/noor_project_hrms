"""
Onboarding v2 domain public service exports (Milestone 6).

The onboarding domain started with a single large service module. As the feature
set expanded (templates, bundles, ESS task submissions, DMS integration), the
implementation was split into smaller modules to keep each file readable and
aligned with common PEP 8 guidance ("small modules, clear responsibilities").

This file re-exports the public service classes so existing imports remain
stable:
- `OnboardingTemplateService`
- `OnboardingBundleService`
- `OnboardingTaskService`
"""

from __future__ import annotations

from app.domains.onboarding.service_bundles import OnboardingBundleService
from app.domains.onboarding.service_tasks import OnboardingTaskService
from app.domains.onboarding.service_templates import OnboardingTemplateService


__all__ = [
    "OnboardingBundleService",
    "OnboardingTaskService",
    "OnboardingTemplateService",
]
