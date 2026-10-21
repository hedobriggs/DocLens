# Proposed single supported release

Use the portable Docker package as the supported deployment of the reviewed
single-admin PDF question-answering application. The app source and image build
contexts remain unchanged by this documentation cleanup.

## Cleanup scope

- Replace the outdated root introduction with a single link to the portable setup (done).
- Keep backend/frontend source, locked dependencies, portable packaging, safety tests
  and validation evidence.
- After checking references, retire earlier root docker-compose.yml and
  backend/Dockerfile and frontend/Dockerfile from the supported installation path.
  They remain present for now; deleting them requires updating dependent validation tools.
- Preserve historical review evidence and Git history for rollback.
- Do not delete remote branches until their unmerged work has been accounted for.

## Main integration decision required

Main baseline: 31eb3455cd5dc02c47f343d62328d41c8a2c3458.
Portable application baseline: 66db29f0b072fd9821869f4ffef008883ce0509b.
These are different product lines, not just different packaging files.

Replacing main with this application tree removes, among other files:

- backend/platform_api.py, platform_core.py, platform_jobs.py and platform_admin.py
- backend/platform_migrations/001_foundation.sql, 002_durable_jobs.sql and
  003_null_safe_admission.sql
- frontend/app/workspaces/page.tsx and frontend/app/monitoring/page.tsx
- frontend/app/api/platform/[...path]/route.ts
- compose.milestone1.yml and platform validation tests

Choose whether those platform features should be retained and integrated, or
retired from the default product. Until that decision, do not replace main or
label those files redundant. Any eventual default-branch change needs a reviewed
full diff, a preserved rollback reference, and validation of the resulting tree.
No existing database or volume should be migrated or removed as file cleanup.
