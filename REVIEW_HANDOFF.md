# Milestone 1 independent review handoff

Role split: Team Codex implemented this branch. Approval Codex independently reviews
and recommends approve/request changes; the user authorizes execution separately.
Do not modify application code, merge, push or deploy during review.

Branch: `milestone/1-workspace-isolation`.
Base: `8544b5880de9f85527c7275b5a82808db38ef880` (verified remote main).
Exact review head: use the full SHA in the user's handoff and verify `git rev-parse HEAD`.
All source/tests/configuration and the evidence below are committed at that head.
The remote milestone branch remains at the base: implementation is local only.
A self-contained Git bundle is supplied separately for transfer to another workspace.

## What to review

Read `docs/MILESTONE-1.md`, then inspect the entire base-to-head diff, especially:

1. `backend/platform_migrations/001_foundation.sql`: non-owner/no-bypass roles,
   separated identity/content privileges, forced RLS, explicit restricted-workspace
   memberships, immutable versions and append-only audits, exact-version library
   approvals, same-organisation reference selection and read-time enforcement.
2. `backend/platform_core.py`: verified/revocable sessions, identity-role separation,
   transaction-local principal context and pool reset, object version pinning,
   compliance retention/legal hold and SHA-256 checks. Organisation is derived from
   SQL workspace/library rows and membership joins, not a browser-supplied context.
   Principals can belong to multiple organisations; selection cannot mix their sources.
3. `backend/platform_api.py`: authorisation before multipart parsing, bounded upload,
   provenance, expected-version replacement, rechecks around I/O/inference, protected
   original/range/passage routes and SQL-permitted dense/keyword candidate sets.
   Provider generation, jobs, reports and exports are not implemented/exposed.
4. `frontend/app/api/platform/[...path]/route.ts`, `frontend/proxy.ts` and the legacy
   upload-route guard: opaque HttpOnly cookie, configured-origin mutation protection,
   no-store/private downloads, platform opt-in and no shared-admin fallback.
   Streaming routes bypass Next proxy body cloning; verify both upload boundaries.
5. `/workspaces`: sign in, select permitted workspace, upload version, inspect exact
   original/passages, search authorised sources and select library references.
6. Local service/bootstrap configuration and scope limitations in `docs/MILESTONE-1.md`.
   No deployment or legacy import has been performed. Neither native tests nor
   container acceptance establishes TLS/ingress, backup/restore or customer readiness.

## Reproduce checks

From the existing checkout, with Python 3.12, Docker and Chromium available:

```sh
backend/.venv/bin/python -m pip install -r backend/requirements.txt -r backend/platform-requirements.txt
backend/.venv/bin/python -m pip check
backend/.venv/bin/python tests/milestone1/acceptance.py
HF_HOME=/workspace/.cache/huggingface HF_HUB_OFFLINE=1 OMP_NUM_THREADS=2 \
  backend/.venv/bin/python tests/milestone1/acceptance.py --real-model
backend/.venv/bin/python -m unittest discover -s tests -v
backend/.venv/bin/python tests/milestone1/build_image.py
backend/.venv/bin/python tests/milestone1/image_smoke.py
cd frontend
npm ci
npm run lint
npm run build
npm run test:platform
npm run test:e2e
```

Use the installed environment's Python virtualenv or create one if absent. Download
the pinned embedding model with normal verified HTTPS if uncached; do not relabel
an offline cache failure as a passing real-model check. The image build helper uses
existing cloud proxy trust without disabling TLS. Integration runners use temporary
real PostgreSQL and private MinIO with restricted application credentials. Only the
default/browser embeddings are substituted; the explicit real-model run is genuine.
Browser fixtures are synthetic and the password is generated per run, never logged.

Also run `git diff --check`, Python compilation and
`docker compose -f compose.milestone1.yml config --no-interpolate --no-env-resolution --quiet`.
The Compose file is a local development example; the full stack has not been deployed.

## Evidence and limits

Raw final results are in `validation/milestone1-*.txt`; see
`docs/MILESTONE-1-VALIDATION.md` for counts and build details. The handoff includes
native and real-model isolation tests, actual production Next.js browser checks,
legacy regressions, and live non-root Python 3.11 image acceptance. Check the exact
commit independently rather than treating these files as independent approval.

The implementation is synthetic-only and bounded, with synchronous ingestion and
PostgreSQL JSON embeddings/token-overlap keyword search. Qdrant server, durable jobs,
orphan cleanup, richer ranking, administration UI/SSO/reset flows, reviewed legacy
migration, exports/review workflow and deployment/restore gates remain outside this
milestone. Reference version approval is an owner-operated action, not a browser
review flow. Archived pinned MinIO is a local test fixture, not a production choice.
Retained failed-upload objects can consume storage; deletion/hold release are not
provided. A timed-out upload may already have committed: reload before retrying.

Return prioritized findings with file/line references, acceptance checks, results
and an approve/request-changes recommendation. No push, merge or deployment.
