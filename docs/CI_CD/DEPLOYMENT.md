# Deployment

## Preconditions
- Required CI checks are green.
- `docs/PROD_RELEASE_CHECKLIST.md` is complete for the release.
- Rollback owner is assigned.

## Standard release path
- Merge to `main`.
- Run the `Release Bundle` workflow.
- Validate staging with the release checklist.
- Promote the approved build through the deployment system used by the environment owner.

## Post-deploy checks
- Smoke key routes.
- Confirm there are no repeated support issues tied to the new version.
- Archive the release notes and bundle artifact.

## Notes
- This repo does not yet encode environment-specific deployment automation in source.
- Keep deployment-specific secrets and environment wiring out of GitHub Actions unless explicitly approved later.
