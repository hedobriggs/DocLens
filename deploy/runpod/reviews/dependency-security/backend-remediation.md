# Small backend remediation candidates

**Security release block remains in force.** These are source/pin candidates,
not rebuilt-image security clearance, native Mac acceptance or RunPod acceptance.
Web modes remain disabled. No application behavior, stored records, citation
identities, credentials, deployment or cleanup policy is changed.

Each section is a separate reviewable commit. The shared evidence.zip contains
versioned `backend-network/`, and subsequent patch directories. Audit CSVs retain
one row per original package/advisory ID, aliases and reported fixes. “Candidate
pin not reported” means absent from that dated requirements audit, not an image
vulnerability closed. **OPEN_NO_REPORTED_FIX** is never cleared solely by upgrading
another version. All six previously documented no-fix IDs remain open.

## Patch 1 — TLS and network clients

Base: `77e2186de4120dd1db7b8099e93d3b57c76a7688`.
Changed pins: anyio 4.12.1 → 4.14.2; certifi 2026.7.22 → 2026.10.19;
h2 4.3.0 → 4.4.1; hpack 4.1.0 → 4.2.0; requests 2.32.5 → 2.33.0;
urllib3 2.6.3 → 2.8.0. No major-version jump or TLS verification disablement.
Manifest requirements hash updated; all six original packaging guards pass.

Audit: **110 → 99 distinct package/advisory pairs**, 137 remaining raw records in
10 packages. The 11 absent pairs concern only these changed pins. See exact
IDs/aliases/status in `backend-network/advisory-status.csv`; no ignored findings.

Regressions: **5 new network checks + 48 existing application checks + 6 packaging
checks pass**. Requests and HTTPX reject an untrusted local certificate, accept
an explicit synthetic CA and reject a wrong hostname. HTTP/2/HPACK headers roundtrip.
Certifi no longer contains the compromised emSign ECC Root CA G3. AnyIO's noisy
process worker completes under a bounded deadline. Google GenAI 1.47.0 constructs
and closes with synthetic configuration; no live provider call. Isolated pip check
passes for the test subset.

Failures retained: baseline certifi test fails and corrected-harness baseline
AnyIO process stalls beyond the 10-second external deadline. The first worker test
also exposed unittest.__main__ replay failing relative imports. It was corrected
by running the process-pool exercise in a `python -c` child, not by changing app
code, suppressing the failure or adding a sleep. Upgraded run passes. Certificate
parsing deprecation warnings are retained.

Test environment: isolated Python **3.12.14**, exact pinned FastAPI 0.128.8,
Starlette 0.49.3, PyMuPDF 1.26.5 and other selected requirements (installed versions
and subset in evidence). Embeddings/reranker/provider calls are controlled as
specified by existing tests. ML dependencies are not installed here; this is not
a production requirements install or production Python 3.11 image test. TLS tests
use loopback only, synthetic temporary keys (not archived) and no external bypass.

Required next gate after independent code review: resolve/install the complete
CPU dependency graph under Python 3.11; pip check and whole-image scan of the new
digest; direct image/Compose synthetic upload, live answers/citations, all auth
and monitoring URLs, restart/recreation and failure-preservation acceptance on a
host with enough disk. Do not reuse the earlier accepted Mac image ID for these
new pins. Provider HTTPS and RunPod attached-storage gates remain separate.

## Patch 2 — PDF and multipart parsing

Base: `8a3320ea30975da975f63849d0478988bcd9053d` (network patch).
PyMuPDF **1.26.5 → 1.26.7** and python-multipart **0.0.20 → 0.0.31**.
The multipart upgrade introduces parser header bounds; no existing document-size,
page, processing or resource limit is raised. A narrow `MultipartParseError`
handler returns generic 400 and logs component/exception class without header
contents. This is required compatibility handling for Starlette 0.49.3, not a
major framework upgrade or an advisory exception.

Audit: **99 → 92 distinct pairs**, 123 raw records in eight packages. All seven
original PyMuPDF/multipart IDs are absent at candidate pins; image gate pending.
Raw/individual status ledger: `backend-parser/` in evidence.zip.

Tests: baseline python-multipart accepts excessive header size/count (200), so
both new failure scenarios fail as expected. First upgraded run rejects input but
exposes six propagated-parser errors (same inherited test in three classes).
After safe error handling, **51 application checks pass**, including rejection,
unchanged existing point IDs and successful valid retry after rejection. Existing
normal/dense synthetic PDF, malformed/scanned PDF, limits, timeout/cancellation,
publication/search races and complete-document citation checks are included.
**Six packaging checks pass**, manifest requirements/main.py hashes updated.
Isolated pip check passes. Full failure logs and passing reruns retained.

PyMuPDF's reported embedded-get CLI path is not invoked by DocLens; pin audit
absence and real document-API regressions are the evidence, not a claim to have
executed every upstream exploit. Complete CPU graph, Python3.11 image/native
regressions and actual runtime HTTP resource measurements remain release gates.
The parser handler does not resolve the still-open Starlette advisories.

## Patch 3 — local configuration and file locking

Base: `6398f53fb8d5a7fd2d7c4c2f08de6cff1d88657e` (parser patch).
filelock **3.19.1 → 3.20.3**, python-dotenv **1.2.1 → 1.2.2**. No application
configuration rewrite, actual credential read or change to saved settings.

Audit: **92 → 89 distinct pairs**, 117 raw records in six packages. Three original
IDs are absent at the candidate pins; per-ID status in `backend-config/`.
Baseline tests reproduce filelock truncating a symlink target and dotenv set/unset
cross-device fallback overwriting a symlink victim. All files are synthetic and
temporary. EXDEV is simulated at os.rename; no host filesystem mounts changed.
The upgraded tests require target preservation, ordinary reads/rewrites, literal
configuration values and mutual exclusion/reacquisition. No wall-clock sleeps.

**9 network/configuration + 51 application + 9 bootstrap + 6 packaging = 75 checks
pass** at the final pins. Isolated pip check passes. Baseline failure logs and
passing results retained. These are behavioral regressions, not a claim to cover
every possible lock race. Current generation code reads dotenv, not set/unset;
the dependency fix does not depend on claiming that narrower exposure is a waiver.

## Remaining review and security boundary

Latest snapshot still reports **fsspec, Pillow, sentence-transformers, Starlette,
torch and transformers**: 89 distinct pairs. All six no-reported-fix IDs remain
**OPEN_NO_REPORTED_FIX**, regardless of eventual version changes. They are not
waived by successful functional tests or absence of another finding.
The raw requirements audits skip additional unpinned transitives and do not scan
OS images, Node/runtime, Qdrant, Grafana, Prometheus or bundled models. Complete
CPU dependency resolution, pip check, immutable-image SBOM/security scans and
real model/resource/acceptance runs remain required on a sufficiently resourced
host. No image ID is assigned to these source-only candidates.

Next candidates require independent review of the three small patches first:
coordinate FastAPI/Starlette compatibility, then separately resolve and measure
ML/native upgrades (including fsspec/Pillow). Do not automatically substitute the
highest advisory-listed version, change the CPU wheel blindly, suppress no-fix
records or infer low exposure from filename/type alone. Verify vendor advisories
and affected operations and seek fix/removal or defensible independently reviewed
mitigation plus explicit risk approval; otherwise retain the block.

Previously accepted functional Mac evidence remains historical evidence for its
exact earlier image. These changed pins need rebuilt-image acceptance. Actual
RunPod HTTPS/attached-storage acceptance, merge, publication and deployment remain
separate approvals. No migrations, cleanup deletion, limit increases, Web-mode
enablement or modification of existing data are part of these patches.

## Patch 4 — compatible FastAPI / Starlette / metrics integration

Base: `cb5c7f7ef370938efa3e5eefa04ed54de8c73913` (three approved source/pin patches).
Candidate pins: **FastAPI 0.128.8 → 0.135.0**, **Starlette 0.49.3 → 1.3.1**,
**prometheus-fastapi-instrumentator 7.1.0 → 8.1.0**. Only those three pins and the
requirements manifest hash change production inputs; no runtime app code changed.

The old FastAPI requires Starlette <1 and instrumentator7 also requires <1.
Retained dry-run resolution rejects the old metrics pin with Starlette1.3.1.
FastAPI0.135.0 allows Starlette>=0.46, and instrumentator8.1.0 requires >=1,<2;
metadata, successful install report and isolated pip check are retained. This
chooses a compatible framework version rather than bypassing resolver bounds or
upgrading every package to latest. Starlette1.3.1 meets the reported fix floors
for all five original Starlette IDs. No claim that this is the minimum possible
FastAPI/instrumentator version across every historical release.

Audit: **89 → 84 distinct package/advisory pairs**, **107 raw records in five
packages**. All five original Starlette IDs below are absent from the candidate
requirements audit, with status **candidate pin not reported; image gate pending**:

| ID | Reported fix floor | Regression / limitation |
| --- | --- | --- |
| PYSEC-2026-161 | 1.0.1 | Malformed Host cannot prepend a path to reconstructed URL |
| PYSEC-2026-248 | 1.3.0 | Nonabsolute request path cannot replace URL authority |
| PYSEC-2026-2280 | 1.1.0 | Nonstandard method cannot dispatch an internal HTTPEndpoint helper |
| PYSEC-2026-249 | 1.3.1 | URLencoded max_fields/max_part_size enforced; valid retry succeeds |
| PYSEC-2026-2281 | 1.1.0 | Windows StaticFiles UNC/SMB path: audit pin evidence only; no native Windows exploit test performed |

The entire per-advisory ledger, aliases and raw findings are preserved under
`backend-framework/` in evidence.zip. **All six no-reported-fix IDs remain open**,
including if some future package audit stops listing them. No suppressions.
Five packages remain: fsspec, Pillow, sentence-transformers, torch, transformers.

Failure/recovery evidence: four new framework methods produce five baseline
failures (two form-limit subtests), then pass on the candidate. Initial installer
ResolutionImpossible is retained, followed by compatible install/pip-check success.
No application-runtime failure occurred on upgrade: the existing 51 checks passed.
Two new application methods expand the inherited suite to **57 passing checks**,
covering wrong-key 401, schema 422, unchanged indexed IDs/valid upload retry, and
actual `http_requests_total` GET/handler/status samples increasing after a request.
The existing suite retains bounded parser rejection, timeout/cancellation, health/
metrics responsiveness, publication failures, search races and citation identity.

Final total: **13 dependency + 57 application + 6 packaging + 5 monitoring = 81
checks pass**. Expanded rerun was justified by the new app auth/metrics coverage;
no arbitrary delays, skipped checks or altered resource/document limits. Web modes
are unchanged and disabled. Test syntax and source-integrity guard are retained.

Scope: Linux Python3.12.14 isolated non-ML subset (exact package inventory in ZIP),
real PDF and isolated Qdrant semantics, controlled inference/provider responses.
Not the complete production graph, Python3.11 runtime, native Mac/Safari/VoiceOver,
full Grafana/Prometheus stack, live Gemini or rebuilt final image. No new image ID.
The Windows advisory is not waived for lack of a Windows test. Complete Python3.11
CPU resolution, image SBOM/scanning and direct rebuilt-image/Compose acceptance
remain mandatory, followed by separately approved actual RunPod HTTPS/storage
acceptance. Security release block, data-preservation and no-deployment constraints
remain intact. ML/native planning is separate; no such pins are changed here.
