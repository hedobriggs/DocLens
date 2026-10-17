# Milestone 1 validation evidence

Base: `8544b5880de9f85527c7275b5a82808db38ef880`.
Branch: `milestone/1-workspace-isolation`; use the exact handoff commit.
Validation date: 2026-10-17. No deployment or remote implementation push.

| Check | Final result | Scope |
| --- | --- | --- |
| Platform acceptance, Python 3.12 | 23 passed | Actual PostgreSQL/forced RLS, separate runtime/auth logins, retained private MinIO, deterministic embeddings |
| Same acceptance with pinned real model | 23 passed | Same assertions with genuine all-MiniLM-L6-v2 embeddings; no hosted-provider request |
| New platform production browser suite | 6 passed | Real Next.js + API + SQL + private retained objects; deterministic embedding only |
| Existing Python regression suite | 31 passed | Existing pricing, privacy, local Qdrant, replacement, upload and monitoring assertions |
| Existing production browser suite | 13 passed | Existing controlled-upstream timeout, authentication, monitoring and 25 MiB upload checks |
| Frontend lint / production build | Passed | Includes TypeScript and the new platform gateway/UI/proxy |
| Dependency consistency | Passed | Native virtualenv and non-root Python 3.11 image |
| Non-root API image build / live smoke | Passed | UID 10001, read-only container, real authentication, workspace RLS, original range, cross-firm denial, session revocation |
| Compose syntax / Python compilation / diff whitespace | Passed | Configuration validation, not full-stack deployment |

No skipped, disabled or expected-failure tests were reported in these runs. A known
PyMuPDF SWIG deprecation warning and Playwright NO_COLOR/FORCE_COLOR warning remain.
The expected simulated storage-outage test records only the exception class.
Raw current-run output: `validation/milestone1-python.txt`, `milestone1-real-model.txt`,
`milestone1-browser.txt`, `milestone1-legacy-browser.txt`, `milestone1-regression.txt`
and `milestone1-image.txt`.

The platform matrix includes two firms and two restricted workspaces in one firm,
readers/editors/reviewers/org admins, no-context SQL reads, forced connection reuse,
forged scope/identity fields, guessed IDs and range reads, revoked/expired/disabled
identities, membership revocation during upload/search/download I/O, stale version
replacement, private/retained/held original objects, hash failures, immutable SQL
rows, append-only audit privileges, revoked library grants/approval, per-version
reference approval and defensive rejection of cross-organisation source mixing even
for a principal with memberships/grants in both organisations.

Browser checks cover sign in/workspace selection/upload/pinned PDF/passages/search,
other-firm guessed IDs, legacy-route closure, org-admin restrictions, reader/no-upload
UI and logout, cross-origin mutation rejection, and an exact 10 MiB PDF transport
boundary plus oversize rejection. The padded transport fixture tests size, not dense
inference load. Initial multipart cleanup, origin handling and proxy body truncation
failures were diagnosed/fixed; final checks passed with the original assertions.
Playwright graceful shutdown was configured and verified to remove its own services;
remaining earlier temporary acceptance containers were removed. No test container
or service is intentionally left running.

Build helper: `tests/milestone1/build_image.py`; live image check:
`tests/milestone1/image_smoke.py`. The built image uses the source in this handoff
and production Python 3.11 dependencies. See `validation/milestone1-image.txt` for
the exact final image ID and live result. The build preserved artifact/TLS checks;
proxy CA material was mounted only as a BuildKit secret. This is not a published
image, clean-task restoration, deployed stack, backup/restore drill or customer-data
readiness claim. See `docs/MILESTONE-1.md` for the intentionally deferred gates.
