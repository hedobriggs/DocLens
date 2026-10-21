# DocLens cleanup review

Base: `22270341adc1768a16c38038a89a59a0c0e1fc65` on
`package/portable-docker`. This is one reviewable cleanup candidate; no merge,
remote-branch deletion, deployment or original-installation change is included.

## What was removed

314 tracked files are removed from the current tree:

- `validation/`: generated logs, image inventories, screenshots and duplicated
  evidence JSON. They belong in review/CI artifacts, not application source.
- Seven superseded review/handoff documents under `docs/`. Their history is kept;
  current architecture, testing and cleanup scope replace them.
- `recovery/`: earlier one-off Mac trial/reconstruction contexts and patches.
  This does not delete or authorize changing anyone's actual recovery copy.
- Root `docker-compose.yml`, backend/frontend Dockerfiles and their unused
  `monitoring/` configuration: superseded by the standalone deployment package.
- Earlier exploratory benchmark/timeout/smoke scripts and duplicate browser
  harnesses. Retained regression suites cover upload recovery, comprehensive
  answers, publication, keyboard, contrast and actual gateway failure behavior.
- The manual `backend/test_retrieval.py` experiment with a hardcoded personal
  document name; it was not an automated test or production module.
- Generated frontend README, unused Next.js starter SVGs, repeated package
  quickstart/consolidation/validation files and old image inventories/raw logs.

Every removed path is recoverable at the exact base commit. A source ZIP and
full deletion list are supplied as external review artifacts. Git history is not
rewritten or shrunk by this cleanup. No unique remote branches are deleted.

## What remains and what changed

One application named **DocLens**, one installation guide under `deploy/portable`,
README, architecture/testing documentation and meaningful regression tests.
Application processing/authentication/retrieval/publication logic, dependencies,
PDF limits, worker controls, frontend handlers and persistent-volume semantics
are unchanged. Browser metadata now says DocLens instead of Create Next App.

The real-Qdrant test now uses a small shared readiness helper instead of importing
an obsolete full deployment script. The gateway test's default synthetic-fixture
path now matches the retained fixture generator and no longer assumes a cloud
workspace path. Generated artifacts/backups/private env variants are ignored.

**Packaging defect corrected:** the earlier legal-UI integration changed the UI
but left `application-manifest.json` at old hashes. That would reject the build.
The manifest now covers the actual runtime/build inputs, including the legal UI
and DocLens metadata. A new test executes the real manifest/context checks with
Docker mocked; stale source hashes fail. Unused Docker/test/documentation files
are no longer trusted application build inputs. The frontend image no longer
copies a removed unused public directory. Image labels identify a release
candidate rather than falsely asserting every file matches an older commit.
New local image tags avoid silently reusing earlier application images.

The upstream branch advanced during cleanup: commit `2227034` independently fixed
the old UI hashes and added useful start/stop launchers. Those launchers, their
private-key handling and saved-image protections are retained. Only their default
new-project tags follow this candidate's build, and displayed naming is DocLens.
The cleanup is based on that newer commit, not a forced overwrite. The historical
manifest defect belongs to `3a07c4d`; it is not asserted against `2227034`.

## Verification

Executed on the cleaned candidate in the managed Linux amd64 environment:

- Packaging safety/context/manifest: 5 tests passed; retained launcher safety: 11 passed.
- PDF upload/recovery: 13 tests passed; comprehensive-document coverage: 5 passed.
- Real Docker Qdrant publication checks: 3 tests passed.
- Frontend lint and production build passed.
- Built UI checks passed: 15 screenshots, 638 contrast samples with zero failures,
  16 long-filename clipping checks and narrow-screen geometry; 20/20 separate
  keyboard cases passed, including controlled hydration.
- Actual gateway suite passed: 12 busy/error/cancel/deadline cases, malformed/
  oversized/broken responses, disconnect propagation and a real 120.023-second
  absolute deadline. A padded 28 MiB transport fixture was tested, not claimed as
  a dense-document processing benchmark.
- Both full linux/amd64 Docker images built successfully from verified source,
  with pinned models and non-root runtime users.
- A fresh synthetic Compose project reached healthy, rejected anonymous upload,
  logged in, embedded/indexed a real five-page PDF into five chunks, rejected
  malformed/301-page replacements without record changes, and preserved exact
  points/payloads/publication records across a full restart. No live provider
  request was made in this dummy-key package smoke.
- The retained upstream launcher also stopped and restarted that synthetic
  project without changing its saved runtime files.
- Only that newly created synthetic project was removed afterward. Before/after
  existing container and volume inventories matched exactly.
- Source preservation and base-to-head whitespace checks passed. No processing,
  retrieval, authentication or document data was rewritten.

The baseline manifest mismatch was recorded before correction; no failing test
was disabled or relabelled as a pass. All final suites and both builds passed.
Raw logs, screenshot measurements, image IDs, deletion inventory and the baseline
source archive are external review artifacts. The commands remain in
`docs/TESTING.md`; generated evidence is not recommitted here.

One observed launcher limitation is retained: when handed a synthetic saved
configuration with port 0, its printed local URL still shows :0. The smoke uses
the actual Docker-assigned port and passes; first-time interactive launcher setup
rejects port 0. This does not establish a valid browser link for a port-zero trial.

Physical Intel Mac, Safari, VoiceOver, public HTTPS/DNS/ACME, target-server
capacity and private/customer data migration are separate validation boundaries.
Previously reviewed live Gemini results do not certify a new server's provider
credentials or arbitrary answer completeness.

## Main is not overwritten

Main at `31eb3455cd5dc02c47f343d62328d41c8a2c3458` contains a different product
line: workspace APIs, durable jobs, PostgreSQL migrations and related UI/tests.
Those are functional work, not clutter. This candidate does not silently remove
or merge them. Before main consolidation, independently review the full product
diff and explicitly decide which platform features remain or are archived.
Preserve a rollback reference; file cleanup is not a database migration or
permission to delete documents, credentials, indexes or volumes.

After independent review, request approval for the exact merge. Branch retirement
comes afterward, only after accounting for unique work. Until then the original
Mac installation and all existing running services remain outside this task.
