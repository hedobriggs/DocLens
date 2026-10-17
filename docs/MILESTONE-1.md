# Milestone 1: reviewable workspace foundation

This is an opt-in synthetic-data vertical slice, submitted for independent review.
It is not a deployment or approval to use customer documents. The legacy RAG API,
admin cookie, local Qdrant directory and SQLite catalog are not imported or trusted
by this app. Existing main functionality remains available only outside platform
mode. In platform mode the Next.js proxy and upload-route guard block legacy routes, including
shared-admin login, dashboard, monitoring and RAG APIs.

## Implemented boundary

- Email/password identity with salted scrypt hashes, opaque random sessions stored
  as SHA-256 hashes, eight-hour expiry, logout revocation and disabled-user checks.
  Ten attempted logins per email hash in ten minutes are persisted/serialized in SQL.
  No browser-provided user/organisation identity is trusted. No self-signup.
- Explicit organisation and workspace memberships. Restricted workspaces require
  membership, including for organisation admins. Readers/reviewers can read;
  editors/workspace admins can upload. Org admin is not a content-access override.
- Versioned SQL migration, separate non-owner content and identity logins, forced
  RLS on every content/policy table, invoker-only policy functions and transaction-
  local principal context. Runtime cannot read credentials/sessions, identity role
  cannot read documents, neither can migrate. One-connection tests force pool reuse.
- Stable document UUIDs and immutable version UUIDs. Original SHA-256, object key
  **and object-store version ID**, uploader, source, jurisdiction, effective/received
  dates, extractor/chunker/model revision and page count are recorded. A filename
  never selects a replacement. An expected-version compare-and-swap protects the
  active pointer. SQL version/chunk/audit records cannot be updated/deleted by runtime.
- Private S3-compatible originals: conditional initial writes, version pinning,
  compliance retention (workspace minimum, 365 days for libraries), optional legal
  hold and read-time integrity checking. No public bucket or presigned URLs. An
  authenticated gateway rechecks current permissions on full/range downloads.
  Failed SQL commits can retain inaccessible original objects; cleanup is deferred.
- Source viewer pins version/hash/page/excerpt/hash. It does not invent OCR, glyph
  coordinates, bounding boxes or character offsets. New versions do not replace old
  originals/passages. No document deletion route, retention expiry job or hold-release
  route exists; administrative policy changes do not shorten an existing object lock.
- Separate library records with rights basis and review state, explicit user grants,
  plus owner-maintained approval of each exact reference version with authority and
  reviewer attribution. Workspace editors may select only an approved, permitted
  same-organisation library version. Every reader still needs a current library
  grant. Revoking approval/grant or library review removes it from workspace search.
- Dense/keyword search first resolves permitted current workspace versions and
  selected exact library versions in SQL/RLS, then scores only those passages, then
  reauthorizes results. This milestone uses bounded PostgreSQL JSON embeddings, not
  the legacy filename/vector collection. Semantic model is pinned to
  `all-MiniLM-L6-v2@1110a243fdf4706b3f48f1d95db1a4f5529b4d41`.
  Keyword matching is token overlap, not the legacy BM25/reranking algorithm.
  Qdrant-server indexing and scalable search belong to Milestone 2.
- Upload admission verifies current identity and write scope before parsing the
  multipart body. Bounds: 10 MiB PDF, 100 pages, 1000 extracted passages; two in-flight
  uploads per API process. No OCR. Workspace search fails closed over 1000 candidates.
  Membership/session revocation during storage, model or download I/O is rechecked.
- Next.js same-origin gateway: HttpOnly/SameSite Strict/Secure production cookie,
  configured public-origin check on mutations, route allowlist and no-store responses.
  Streaming API routes bypass Next proxy body cloning and enforce their own mode/origin/session guards.
  API and store credentials are server-only. In platform mode internal services are
  on private Compose networks; only the frontend has a loopback host port.
- Append-only actor/version audit events for upload, original/passage access and
  reference selection. Error responses/logs omit SQL/provider/storage exception
  bodies, passwords, original filenames and passage text.

Jobs, reports, exports and hosted generation have no platform routes. Their guessed
IDs return generic 404 after identity validation; there are no implementations to
claim isolated yet. Human review/export functionality is Milestone 3.

## Run validation without deployment

From the existing `/workspace/DocLens` checkout (no worktree required):

```sh
backend/.venv/bin/python -m pip install -r backend/requirements.txt -r backend/platform-requirements.txt
backend/.venv/bin/python -m pip check
backend/.venv/bin/python tests/milestone1/acceptance.py
HF_HOME=/workspace/.cache/huggingface HF_HUB_OFFLINE=1 OMP_NUM_THREADS=2 \
  backend/.venv/bin/python tests/milestone1/acceptance.py --real-model
backend/.venv/bin/python -m unittest discover -s tests -v
cd frontend
npm ci
npm run lint
npm run build
npm run test:platform
npm run test:e2e
```

The explicit integration runner provisions temporary real PostgreSQL and MinIO
containers, random synthetic credentials, non-owner SQL logins, a private retained
bucket and restricted object credentials. It cleans up its own resources. Default
inference is deterministic; `--real-model` runs the same assertions using actual
pinned embeddings, without a hosted-provider request. If the model is not cached,
first run with `HF_HUB_OFFLINE` unset to fetch it with normal TLS verification.

The platform browser suite uses real Next.js production routes, actual FastAPI,
PostgreSQL and MinIO, with deterministic embeddings. It generates a private random
fixture password; no actual credential is stored in the repository or test reports.
The legacy browser suite is separate and uses its existing controlled upstream.

Pinned PostgreSQL and archived Bitnami MinIO image digests appear in the runner
and local Compose example. The archived MinIO image is a **synthetic local test
fixture**, not a recommended production distribution. Production store selection,
security maintenance, TLS/ingress, backup/restore and provider policy require the
Milestone 4 deployment review. Do not interpret container acceptance as deployment.

## Local development / one-time provisioning

`compose.milestone1.yml` is separate from `docker-compose.yml`. It declares private
SQL/object services, one-time initialization jobs, API and frontend. Do not start
it with legacy volumes, an existing customer database or bucket. Review its required
environment variables and supply values securely through a local ignored environment
file or the environment settings; never put them in chat/source. Use independent
migration-owner, runtime, identity, object-owner and application credentials.
Database URLs target `database:5432` inside this Compose network. Use URL-encoded
passwords; do not dump resolved Compose configuration containing credentials.

The migration owner runs `platform_admin.py migrate` **once** on a new database,
then `platform_admin.py create-logins` with `PLATFORM_RUNTIME_PASSWORD` and
`PLATFORM_AUTH_PASSWORD`. This creates `doclens_web`/`doclens_identity` logins with
separate group grants. Repeat migrations/bootstrap intentionally fail rather than
reset existing data or rotate passwords. Owner credentials never enter the API.
`initialise-originals` creates an object-lock-enabled `originals` bucket and a
put/get/retention-only application identity using the committed object policy.
No anonymous, bucket-list, delete or object-administration grant is provided.
Wait for PostgreSQL and MinIO readiness before their one-time initialization jobs.
The Compose example itself has been syntax-validated, not deployed as a stack.

For a synthetic local population, use the owner-only command:

```sh
# Set PLATFORM_OWNER_DATABASE_URL and PLATFORM_FIXTURE_PASSWORD securely first.
backend/.venv/bin/python backend/platform_admin.py seed-synthetic --confirm-synthetic
```

This explicit operation creates two firms, two restricted workspaces in firm A,
one in firm B, six synthetic users and two synthetic libraries. It never imports
legacy data. Synthetic fixture email names are `alice`, `bob`, `carol`, `reader`,
`reviewer`, `org-admin` at `synthetic.invalid`. All use the explicitly supplied
fixture password; they are not production accounts. The owner must separately
record `platform.reference_approvals` for an exact library version before use.
There is no browser role/membership/provisioning editor in this milestone.

Native API entry point: `uvicorn platform_api:app --host 127.0.0.1 --port 8001`
from `backend`, with `PLATFORM_DATABASE_URL`, `PLATFORM_AUTH_DATABASE_URL`,
`PLATFORM_S3_ENDPOINT`, `PLATFORM_S3_BUCKET`, `PLATFORM_S3_ACCESS_KEY` and
`PLATFORM_S3_SECRET_KEY`. TLS is required by default. Local synthetic-only HTTP
object storage requires explicit `PLATFORM_SYNTHETIC_HTTP=1`.
Start frontend with `DOCLENS_PLATFORM_ENABLED=1`,
`PLATFORM_API_URL=http://127.0.0.1:8001`, and an exact
`PLATFORM_PUBLIC_ORIGIN` matching the browser origin. Open `/workspaces`.
Use HTTPS for production Secure cookies. No credentials or tokens go in URLs.

## Deferred gates / migration policy

No customer documents, multi-worker capacity claim, durable ingestion/job recovery,
Qdrant-server integration, orphan reclamation, database/object restore drill,
professional insurance findings, SSO/MFA/reset flows, administrative UI, deployment
or pilot approval is included. A frontend timeout cannot cancel a completed upload;
reload the document list before retrying. Objects surviving failed commits remain
locked and inaccessible, so storage growth needs Milestone 2 retention-aware cleanup.

Legacy migration is deliberately blocked: stop/back up the single-owner legacy
store, inventory original documents, obtain a reviewed explicit mapping from each
legacy record to organisation/workspace/document/version and provenance, rehearse
an import/rollback in a new schema/bucket, reconcile hashes/citations and get
approval before any live import. Ownership must never be inferred from filenames.
No importer or destructive automatic schema/data conversion is shipped here.
