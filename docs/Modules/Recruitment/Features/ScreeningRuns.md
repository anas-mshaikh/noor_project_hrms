# Screening Runs

This feature supplements `docs/Modules/Recruitment/Recruitment.Internal.md`.

## Overview
Screening runs retrieve, rank, and explain candidates for an opening.

## Purpose
Give recruiters a repeatable way to shortlist candidates using stored resume artifacts and ranking pipelines.

## Rules
- Screening is tied to a branch and opening.
- Results must stay scoped to the relevant opening and branch.
- Explanations and reranking behavior should be documented only where verified in code or source docs.

## Flows
- Create or review opening
- Upload resumes
- Run screening
- Review results and ATS actions

## Screens
- `/hr/openings`
- `/hr/runs`
- `/hr/pipeline`

## Backend/API notes
- `backend/app/api/v1/openings.py`
- `backend/app/api/v1/screening_runs.py`
- `backend/app/api/v1/ats.py`

## DB notes
- Needs Verification from current schema and migrations.

## Edge cases
- canceled or retried runs
- incomplete parsing or embedding
- stale ATS states

## Errors
- Needs Verification

## Tests
- Needs Verification

## Open questions
- Confirm the exact production status of the HR recruitment frontend surfaces.
