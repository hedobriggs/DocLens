# Dependency security handoff — 28 October 2026

**Disposition: partial remediation; security release gate remains OPEN.**
Base: `170b3d9817c6892812c450ba71d0dab7129d2949`.
This candidate is the Git commit containing this document. Review the diff from
that base. No Pod, Mac, existing document, schema, limit or running service changed.
The previously accepted Mac functional run is separate evidence against the old
image; it is not acceptance of this dependency update.

## Applied frontend corrections

- Next.js and its ESLint configuration: **16.3.6 → 16.4.3**. The initial audit
  includes ten Next advisory entries, including critical image-optimization and
  `use cache` RCE findings; see exact IDs, affected ranges and URLs in the raw JSON.
  No configured image optimization or `use cache` use was found in application
  code. That narrows observed exposure but does not prove framework endpoints
  safe; the framework is updated rather than granting an exception.
- `source-map-js`: **1.2.1 → 1.2.2**, pinned through an override. Fixes
  GHSA-68fv-2mgg-jv7q (indexed source-map resource exhaustion).
- `zod`: **4.6.5 → 4.6.7**, pinned through an override. Fixes
  GHSA-mrhx-c7xc-m3w5 (oversized constrained-collection resource exhaustion).
  Both existing hook-linter consumers explicitly allow Zod 4; no forced major
  override. Zod is used by lint tooling, not identified in application handlers.
- Regenerated the npm lockfile. The frontend image currently copies the complete
  node_modules tree, including dev packages, so the full audit matters as well
  as the production-only view. No packages are hidden from the audit.
- The newer lint configuration reports five `require()` errors in the existing
  intentionally CommonJS bootstrap. A **bootstrap.cjs-only** rule exception makes
  lint pass; other lint rules and application checks remain enabled.

| Audit | Baseline | Candidate |
| --- | --- | --- |
| npm, full lockfile | 9 affected packages: 8 high, 1 critical | **0 findings**, exit 0 |
| npm, production subset | Not separately run before update | **0 findings**, exit 0 |
| Python pinned requirements | 153 raw records in 16 packages | **Unchanged/open**; no backend pins modified |

Python records contain duplicates. There are **110 distinct package/advisory-ID
pairs**, not 153 distinct CVEs. Full records and aliases are retained, with a
per-package/ID deduplicated CSV; no allowlist or ignored advisory was applied.
Audit results are a dated registry snapshot, not a guarantee of no vulnerabilities.

## Unresolved backend findings and remediation sequence

All rows below remain **OPEN**, not accepted exceptions. Listed target versions
are advisory-reported fix floors/candidates, **not tested compatible upgrade
instructions**. Some advisories list multiple fixes; raw JSON/CSV retains all of
them. Reaudit the selected final dependency graph before declaring remediation.

| Package / current pin | Distinct IDs | Reported target candidate | Exposure assessment and required action |
| --- | ---: | --- | --- |
| anyio 4.12.1 | 2 | 4.14.2 | Network TLS/process-pool paths; do not rely on ASCII destinations or assume subprocess exposure absent. Upgrade and exercise timeout/cancellation. |
| certifi 2026.7.22 | 1 | 2026.10.19 | Removed compromised-root trust is relevant to outbound TLS. Upgrade and test verified provider/model connections and custom CA without disabling verification. |
| filelock 3.19.1 | 2 | 3.20.3 | Model-cache local symlink/locking attacks. Private cache reduces exposure, not a fix. Upgrade and test cold/warm initialization and restart locking. |
| fsspec 2025.10.0 | 1 | 2026.6.0 | Dependency filesystem/reference operations; arbitrary user filesystem references are not an intended API. Upgrade and verify offline model loading. |
| h2 4.3.0 | 1 | 4.4.1 | HTTP/2 parsing through network clients; private inbound backend does not remove outbound exposure. Upgrade with client compatibility tests. |
| hpack 4.1.0 | 1 | 4.2.0 | Header decompression/resource exhaustion; update with h2 and test bounds. |
| pillow 11.3.0 | 56 | 13.0.0 | Native image parsing/codec advisories. DocLens accepts text PDFs, not a general image API, but no complete reachability proof exists. Major upgrade; validate dense PDFs, model imports, memory and image rejection. |
| PyMuPDF 1.26.5 | 1 | 1.26.7 | Reported `__main__.py` embedded-get CLI traversal; application uses the PDF API, not that CLI. Still upgrade and test malformed PDFs, resource bounds and originals/citation preservation. |
| python-dotenv 1.2.1 | 1 | 1.2.2 | Configuration parsing/security boundary. Upgrade; test literal credentials, saved configuration and failed/repeated initialization. |
| python-multipart 0.0.20 | 6 | 0.0.31 | Upload parsing/resource-exhaustion is relevant before application PDF checks. Filename-preservation and parse_form-specific issues have narrower prerequisites. Prioritize upgrade with malformed multipart/header/preamble tests and limit enforcement. |
| requests 2.32.5 | 1 | 2.33.0 | Outbound request handling. Upgrade and test redirects, TLS and provider/model failure handling. |
| sentence-transformers 5.1.2 | 1 | 5.6.0 | Model module-import security-control bypass. Pinned bundled model artifacts/offline runtime narrow the attack surface, not blanket protection. Upgrade with the complete ML graph and fixed synthetic retrieval expectations. |
| starlette 0.49.3 | 5 | 1.3.1 | Includes request-host/path and other framework findings. Backend is private but handles untrusted requests via frontend. Major upgrade **requires compatible FastAPI resolution**; do not override its dependency bounds. Test auth/path handling, multipart, disconnects and publication failures. |
| torch 2.2.2 | 20 | 2.13.0 | Checkpoint deserialization/native operations and other paths. Portable builds use fixed model revisions and safetensors-only downloads; no proof all affected operations are unreachable. Coordinate CPU-wheel pin in Dockerfile and requirements, Python/NumPy support, Intel CPU behavior, real inference and memory. |
| transformers 4.57.6 | 6 | 5.10.0 | Malicious model/config/import and trainer/conversion paths. Current inference is not training, but model-loading risk remains. Major upgrade with sentence-transformers/torch; verify offline safe artifacts, dense ingestion, complete retrieval, citations and live synthetic answers. |
| urllib3 2.6.3 | 5 | 2.8.0 | Outbound networking/redirect/resource paths; prioritize update with requests and verified TLS tests. |

Recommended next reviewable patches: (1) resolve compatible HTTP/TLS/upload/PDF
patches and regression-test parsing/admission/failure preservation; (2) upgrade
FastAPI/Starlette together; (3) upgrade and measure the ML/native stack together.
Do not mix major ML changes into this already-reviewed monitoring navigation fix.
For every patch retain failure/rerun logs, exact dependency versions and commit,
and require independent review. No authority to waive remaining findings is
implied. No customer-data admission or release recommendation is made here.

## Executed validation for this candidate

Complete commands, outputs, initial failures and corrective reruns are in
[evidence.zip](evidence.zip), with `COMMANDS.txt`, raw audit JSON and browser code.

| Check | Result |
| --- | --- |
| npm lock regeneration and clean npm ci | Pass; ESLint 9 deprecation warning retained |
| Production Next 16.4.3 build and TypeScript | Pass |
| Lint | Initial 5 CommonJS errors; pass after narrow config correction |
| Bootstrap recovery/configuration | 9 pass |
| PDF upload/publication/complete-document regressions | 48 pass |
| RunPod packaging/CA-on-off option contract | 10 pass |
| Monitoring gateway | 8 pass |
| Monitoring configuration | 5 pass |
| Real production Next browser authentication | Pass: bad login 401, valid login 200, both anonymous monitoring APIs 401, host-only Secure/HttpOnly/Lax cookie, logout |
| Real built dashboard / synthetic browser API fixtures | Pass: 14 screenshots; both 1440×900 and 1280×800; 529 contrast samples with zero failures; keyboard/upload/citation checks |
| Base-to-candidate whitespace | Pass |

**80 Python/Node checks pass**, plus the two browser exercises. Browser UI fixtures
control API responses and use a fixture session; the separate auth exercise uses
real browser form logins and no injected cookie. Neither is final-container
monitoring-service acceptance or live Gemini validation.

Environment: Linux x86_64, Node 24.19.0, npm 11.9.0; pip-audit 2.10.1 in a temporary
Python 3.12 auditor environment. Backend regression environment versions are
included; they are not claimed to match every production requirement pin.
Dockerfile runtime Node 22, native Mac/Safari/VoiceOver, rebuilt final image,
Grafana/Prometheus full-stack browser navigation and live Gemini have **not been
rerun for these changed dependencies**. No new image ID exists for this candidate.
The accepted Intel Mac image `sha256:6b46513130ae283ce1da9ac3de0068be3abfe0d8fd097966e2a912859c1c8b55`
is earlier evidence and must not be relabelled as this security candidate.

## Audit scope, remaining gates and recovery

The Python command uses `--no-deps --disable-pip`: it audits the explicit pinned
requirements without installing the very large ML graph. Additional resolved
transitives, CPU-wheel provenance, model files, operating-system packages, Node
runtime/base images, Qdrant, Grafana and Prometheus binaries are **not security
cleared by these audits**. Image SBOM/scanning of the eventual digest is still
required, followed by compatible-runtime tests. Do not turn a zero npm report
into a zero whole-image report.

First pip-audit attempt failed on the unwritable default cache; rerun using a
writable temporary cache completed with findings (exit 1). Initial npm version
queries similarly required a temporary cache. These infrastructure failures are
recorded and not interpreted as clean audits. No certificate verification bypass.

Review boundary: independently assess this exact source diff, audit snapshot,
open-backend triage and updated frontend regressions. After code review, rebuild
the actual final image and test real authentication, all monitoring links/assets,
synthetic upload/answers/citations, failure preservation and restart/recreation.
Actual RunPod HTTPS/browser and attached-storage stop/start/forced-restart tests
remain a **separate pending gate**. Merge, image publication and deployment need
separate approval. Local functional acceptance is not cancelled, but its old image
must not be presented as dependency-security acceptance.

Rollback is a source/image selection decision only: never reset volumes, replace
saved credentials, delete originals, alter citations or run cleanup to roll back.
Returning to an old image reintroduces its known vulnerabilities and needs an
explicit risk decision; it is not a security remediation. No migrations or new
storage formats were introduced by this candidate.
