# Exact-candidate build gate and separate /api/ask investigation

**Approved application source tested:**
`a2986c786ed50d271fb99ad787218695e9fd4d82`.
This evidence commit changes no application source, dependencies or image inputs.
Security release block and disabled Web modes remain. No publication, deployment,
paid provisioning, migration, existing-data or Mac modification.

## Image build/inventory/SBOM/scan/acceptance status

**New candidate image ID: NONE. Registry digest: NONE.** Only the local Docker
context is connected. It has5 CPUs,35.7GB RAM, but only5.4GiB free on the Docker
filesystem and uses VFS. The separate tmpfs has free space but is not Docker's
backing filesystem. No adequate authorized host was identified; no unsafe build
or storage workaround attempted. Unrelated images/volumes remain untouched.

Consequently **no exact-candidate image inventory, SBOM, scan or direct-image/
Compose acceptance was executed**. The current candidate is NOT ready for an
isolated rebuilt-image retest. Complete Python3.11 CPU source resolution and
synthetic evidence remain in the separate dependency-security/cpu-resolution.md;
that accepted source evidence is not a built-image pass.

The previous image scan is explicitly historical:
`sha256:ce23cbb8278ab8ede485603d606340c065df280202788c959517a15079329f27`,
not this candidate. Its706 detection instances and2641-component SBOM remain
available in dependency-security/evidence.zip. No old image ID is reused.

### Prepared build/review sequence on an authorized existing Linux host

Preflight needs confirmed Docker disk capacity (conservative30GB free), sufficient
memory (16GB recommended), Linux amd64, Docker/Compose, Node/Chromium/Playwright,
Python and scanner access. Confirm actual daemon storage capacity, not client
filesystem or network-volume physical capacity. Do not provision paid resources,
use the Mac, remove images/volumes or reset data to satisfy this gate.

1. Create a new isolated checkout of the exact SHA above. Verify repository root,
   exact HEAD, clean tree and all portable packaging checks **before** building.
   Preserve every failed command and exit status; never continue after clone/cd/
   checkout/hash failure. No checkout/reset in an existing working directory.
2. Build backend/frontend with `deploy/portable/build.py`, supplying fresh unique
   BACKEND_IMAGE/FRONTEND_IMAGE tags and the authorized build CA if required.
   The source-integrity guard stays enabled. Build the repository-root RunPod
   Dockerfile with those exact dependency image IDs, no runtime file substitutions.
   Record source hashes, full build logs, tool/base-image versions and actual IID.
3. Read inventory from that exact image in an isolated network-disabled container,
   with no existing volume mounted. Verify Python3.11, CPU torch, fixed models,
   expected ports, pip removal and all package/native/service versions. Do not
   print environment/secret-bearing inspect output. Confirm external/interpreter/
   ensurepip artifacts and vendored libraries, not just top-level requirements.
4. Generate current CycloneDX/SPDX SBOM and full image scan with scanner version,
   DB timestamp and complete unsuppressed results. Map unresolved findings to
   exact image components; no-fix advisories remain open without defensible
   independently reviewed evidence. No automatic waiver on a zero package audit.
5. Run `tests/test_runpod.py --browser` using the exact image ID, fresh synthetic
   storage and no DOCLENS_MONITORING_RUNTIME override. Preserve commands, all
   container/browser logs/results/screenshots and resource measurements. Live
   synthetic Gemini checks require a securely configured real provider key; do
   not treat the non-live harness's controlled answer as a live model pass.
6. Separately execute the complete Compose monitoring stack and real browser
   dashboards/query tests with the same built application image IDs, fresh unique
   project/volumes and current profiles. `tests/test_compose_root.py` alone covers
   the core stack, **not** complete monitoring acceptance. Retain authentication,
   private ports, all links/assets, PDF/answer/citation, restart/down-up session/
   history/document identities and failure-handling evidence. Normal Compose
   configuration mounts are distinct from substituting files into the final Pod
   image. Preserve every failure and corrective rerun; remove only trial-owned
   resources under the reviewed harness policy.

These steps are prepared requirements, not executed results. Retest only after
adequate host access/capacity is verified. Actual RunPod HTTPS and attached-storage
acceptance remains separate, as do merge/publication/deployment approvals.
The generic monitoring README still describes older RunPod single-port behavior;
use the reviewed one-click/readiness.md source-specific record (3000/3001/9090),
not that stale paragraph, when preparing the new trial. No docs discrepancy is
used to claim an unbuilt image works.

## /api/ask HTML investigation — separate and still unresolved

No fix proposed or implemented. In particular **session-expiry UI handling does
not resolve or establish the cause of the reported HTML response**. The actual
affected URL/environment, time/timezone and sanitized matching deployed logs were
requested and have not been received. No direct RunPod access was available.

A controlled diagnostic used the unmodified production Next16.4.3 build at the
approved source. Diagnostic-only DNS mapping sends its `backend:8000` request to
a synthetic loopback HTTP fixture; safe HTTP access instrumentation correlates
frontend and fixture logs. This is not a Docker/final-image/RunPod acceptance test
and not real Gemini or the deployed backend. No customer text or token is logged.

| Controlled case | Frontend result | Redirect observation |
| --- | --- | --- |
| Anonymous POST /api/ask | 401 application/json | None |
| Expired signed JWT POST /api/ask | 401 application/json | None |
| Valid JWT, synthetic backend JSON | 200 application/json | None |
| Backend500 text/html | 502 application/json | Backend HTML is not passed through |
| Backend302 to login HTML | 502 application/json | Backend302/login200 chain recorded; no frontend redirect |
| POST /api/ask/ | 308 then200 application/json | Location /api/ask; POST preserved |
| Wrong frontend POST /ask | 404 text/html | Reproduces HTML on a different route, not the reported incident |
| GET /api/ask | 405, no Content-Type/empty body | Wrong method; not an HTML response |

`results.json` records exact status/content type/Location, each redirect hop,
UTC time, time-to-first-byte, total duration and bounded synthetic body prefix.
All8 cases correlate to frontend access IDs; the4 upstream cases also correlate
to backend fixture logs. These IDs/timings are test-only and do not identify the
user's reported request. Ordinary production Next logs emitted no failure detail
for the backend HTML catch path; diagnostic instrumentation supplies access logs,
not a claim that deployed logging already has this observability.

Initial fixture logging used getHeader after writeHead(headers), which yielded
nulls for its header metadata. That incomplete instrumentation and all first-run
outputs are retained under initial/. Corrected fixture setHeader calls record
actual content types and redirects. No application runtime correction occurred.
The final eight-case matrix and matching-log validation pass.

### Evidence needed before proposing a fix

Obtain the actual browser Network record for the failed request: method, sanitized
full path/host/port, status, response Content-Type, Location/redirect chain, timing
and a safe body/error excerpt. Correlate UTC attempt time with frontend, backend
and edge/RunPod proxy logs and deployed source/image ID. Do not share cookies,
Authorization headers, unredacted HAR/Copy-as-cURL, Gemini keys, document text or
private filenames. A sanitized network screenshot/summary is sufficient to start.

Then distinguish a response from this API handler versus wrong route/service,
redirect or edge-generated HTML and reproduce that observed condition. No timeout
increase, session-expiry claim or speculative application fix is justified yet.

## Remaining security findings

Six original no-reported-fix IDs remain **OPEN** despite no longer being listed
at candidate versions: torch PYSEC-2025-189, PYSEC-2025-190, PYSEC-2025-192,
PYSEC-2026-139; transformers PYSEC-2025-217, PYSEC-2026-4174.
The pip-vendored removals were demonstrated only in the CPU environment; final
image removal/security remain unverified. OS/native/interpreter/Node/Qdrant and
monitoring components need exact-image inventory/scan and per-advisory review.
Historical-image detections must not be relabelled as resolved or as current
candidate detections. No risk acceptance is issued by these diagnostics.

[evidence.zip](evidence.zip) contains full diagnostic commands/scripts/results,
first-run and corrected logs, source hashes, capacity/status records. Request
independent review of this evidence; image acceptance and the actual HTML cause
are still pending. No execution/merge/publication/deployment approval requested.
