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
