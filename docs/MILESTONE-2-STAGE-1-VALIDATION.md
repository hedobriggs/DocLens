# Milestone 2 stage 1 validation

Implementation base: `474a50d5b8df21fab90df39e832d0163afda2ce2`.
Synthetic fixtures only; no production migration, merge or deployment.

## Environment and method

Cloud x86_64 Linux/KVM, AMD EPYC 9V74 host CPU, five visible logical CPUs;
cgroup CPU quota 400000/100000 (four cores), 32 GiB memory limit.
Native Python 3.12.14; container smoke uses Python 3.11, non-root UID 10001,
read-only root filesystem and temporary /tmp. PostgreSQL 17 and MinIO fixtures
are pinned by digest in the acceptance runner. Frontend Next.js 16.3.6 and
Chromium are used through Playwright.

Dataset: generated synthetic one-page PDFs and existing synthetic regression
fixtures. Shared admission capacity is exercised across concurrent submitters,
restricted workspaces and five organisations, up to the configured global cap
of 32. These are functional checks, not a representative production corpus.
Admission performs no embedding inference. Synchronous regression fixtures use
deterministic 384-dimensional embeddings. The production manifest pins
`sentence-transformers/all-MiniLM-L6-v2@1110a243fdf4706b3f48f1d95db1a4f5529b4d41`;
manifest pinning is tested, not model quality or inference performance.

Times below are runner wall times for functional suites, including fixture/setup
work where the runner includes it. There is no ingestion/search percentile,
large-corpus, 8 GiB deployment or independently measured performance evidence.
All proposed Milestone 2 latency targets remain unverified.

## Original stage checks (before independent review)

| Check | Result |
| --- | --- |
| Migration and durable admission stage | 26 passed, 45.641 s |
| Milestone 1 regression | 23 passed, 25.702 s |
| Storage portability | 6 passed, 0.175 s |
| Legacy Python regression | 31 passed, 36.172 s |
| Platform browser regression + durable gateway | 7 passed, 15.5 s |
| Legacy browser regression | 13 passed, 14.2 s |
| Final-source non-root container smoke | Passed: durable admission + existing identity/storage checks |
| Frontend lint and production build | Passed |
| Python compile and dependency check | Passed |
| Whitespace validation | Incomplete: working-tree check missed untracked build-log whitespace |

Stage coverage includes legacy row/citation/original preservation, atomic
migration rollback and concurrent runners; retained originals and crash recovery;
atomic job/submission/event acceptance; idempotency and manifest stability;
current membership checks, stale tokens, private-column grants and shared quotas.

## Environment failure and rerun

A final native Milestone 1 run failed during MinIO fixture administration before
running tests. A diagnostic rerun passed 22 of 23 tests, then a MinIO ClientError
caused the last upload to return 503. A final-source Docker image built successfully
(`sha256:a89a522f20ec793a0c488d47e6740ef32ea01bac63aef2ffad97f37d19318554`),
but its smoke run failed to start the API container (Docker exit 125).
Subsequent shell startup reported no space left on device; the 32 GiB root
filesystem was confirmed full. With separate user approval, six superseded
untagged test images and unused Docker build cache were removed. Cache removal
recovered 19 GiB; the repository, originals and tagged images were preserved.
The final native Milestone 1 regression then passed all 23 tests. Disk exhaustion
is consistent with the earlier fixture/storage failures, but their exact error
causes were not reconstructed. The final-source container smoke then passed as well.
No implementation change was needed between these failed and passing runs.

Raw successful-run evidence is in `validation/milestone2-stage1-*.txt`.
Reproduction commands are in `docs/MILESTONE-2-STAGE-1-REVIEW.md`.

## Limits

No worker claim/heartbeat, extraction, retries, Qdrant, publication CAS,
cleanup inventory executor or deletion is implemented here. Attempts/state
columns are preparatory schema only. The default-off queue fills to its cap
because it has no consumer. Unsupported scanned PDFs must be rejected without
publication by the later worker stage. No OCR or production readiness is claimed.

## Independent re-review: NULL handling and evidence correction

The original report overstated whitespace validation: `git diff --check` did not
include the then-untracked build log. Reproducing the full base-to-1201fca check
returned exit 2 and identified three trailing-whitespace lines (14–16) in
`validation/milestone2-stage1-frontend-build.txt`. The committed log now has line
endings normalized and trailing whitespace removed; test outcomes are unchanged.

Two new restricted-runtime tests against the original 002 functions ran and failed
with seven subtest failures: missing NULL rejection for receiving/accepted request
fingerprints, the new-request NOT NULL error using a different SQLSTATE, and NULL
accept/release tokens before/after acceptance. This was a deliberate failing
reproduction, not a passing validation. Migration 003 adds explicit guards and
NULL-safe comparisons, preserving existing migration checksums and job records.
An additional upgrade test verifies already-applied v2 job/history preservation.

The first post-fix stage run executed 28 tests: 26 passed and two migration tests
failed because their assertions still expected two history rows rather than three.
Those assertions were updated; no admission-function change was required. The
runner had loaded the old assertions before the displayed source lines were edited.
The full rerun includes 29 tests with the additional existing-v2 upgrade check.

A subsequent 29-test run passed 28 tests but failed while administering the
legacy-upgrade MinIO fixture, before application assertions in that test. The
captured subprocess exception did not retain stderr. Investigation reproduced a
concrete fixture hazard: generated URL-safe passwords can begin with a hyphen,
which the pinned MinIO mc CLI interprets as a flag even inside quoted arguments.
Test-only passwords now have a `fixture-` prefix while retaining their random
suffix. This removes that hazard; the exact earlier CLI error is not proven.
The failure and isolated CLI reproduction are retained as evidence, followed by
the complete suite rerun. No production credential or storage behavior changed.

Re-review evidence is in `validation/milestone2-stage1-rereview-*.txt`, including
both intentionally failing reproduction and the first post-fix test failure.
Captured logs have trailing whitespace removed for repository storage; outcomes
and diagnostics are retained. The older stage results above are historical and
are not being presented as reruns of this correction.

| Re-review check | Result |
| --- | --- |
| Stage acceptance | 29 passed, 52.938 s |
| Milestone 1 regression | 23 passed, 20.137 s |
| Storage portability | 6 passed, 0.326 s |
| Platform browser regression | 7 passed, 22.4s |
| Rebuilt container smoke | Passed: durable admission, identity/RLS, retained ranges, revocation |
| Python test compilation | Passed |
| Full base-to-head whitespace | Passed for complete staged tree against 474a50d; repeated after commit |

The rebuilt image is
`sha256:b9995d3551339dcb176d0eb95f9e5dee3980aad02a0622a56221b6890c620183`.
Hardware, synthetic dataset, model manifest and functional measurement method
remain as described above. No new performance claim or worker/publication/cleanup
capability is introduced by this correction.
