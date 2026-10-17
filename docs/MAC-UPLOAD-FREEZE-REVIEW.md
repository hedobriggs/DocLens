# Preserved Mac application: upload freeze investigation and review

Review base: `497394bf03f00f73256e3e70cb7283e7ce33c342` (preserved Mac application
plus the approved indentation correction). Branch: `fix/mac-upload-freeze`.
The exact fix commit is supplied in the handoff. Review only the base-to-fix diff.
Do not merge this branch, deploy, admit customer documents or delete retained data.
This is a legacy Mac application fix, not Milestone 2 worker/Qdrant implementation.
The user's eight supplied files remain recoverable from preservation commit
`c0509bbd6c5648876c3699306b5f7ad1ae29a584` and its existing checksum manifest.

## Diagnosis

The old async upload handler synchronously extracted PDF text, encoded every chunk
and wrote Qdrant batches on the API event loop. The initial file size did not bound
page count, extracted characters, chunks or CPU work. `create_embeddings` batched
inference but did not move it off that loop. Dense uploads therefore prevented
health requests and disconnect handling while the CPU library continued work.
The gateway's ten-minute `ClientRequest.setTimeout` was socket inactivity, not a
processing deadline; it destroyed its upstream connection but the backend never
checked for disconnect. The browser fetch had no deadline. Finally, replacement
called `delete_document` before storing new points, risking total or partial loss
when a later batch failed.

User-reported Docker stats showed backend CPU 827.81%, backend container memory
993.6 MiB and an engine limit of 3.82 GiB. Those observations are consistent with
CPU-intensive encoding and thread oversubscription; they do not establish an OOM
or prove the precise stage for the user's undisclosed PDF. No customer file was
used. The matching failure mode was reproduced against the preserved source.

### Synthetic fixtures

| Fixture | Bytes | Pages | Extracted characters | Purpose |
| --- | ---: | ---: | ---: | --- |
| Padded 28 MiB PDF | 29,360,128 | 1 | 51 | Isolate byte transfer; explicitly not evidence of dense processing |
| Dense 40-page PDF | 24,614 | 40 | 217,800 | Actual text extraction, 280 chunks, real model inference and indexing |
| Dense approximately 29 MiB PDF | 30,437,728 | 650 | 14,722,500 | Real uncompressed text streams, not padding; baseline produced 18,200 chunks |

Fixtures are generated with PyMuPDF; hashes are in `validation/mac-upload-freeze/fixtures.json`.
The large dense baseline was intentionally stopped after approximately ten seconds
of observation, not processed to completion or timed as a successful upload. No
full ten-minute baseline run or inference-time extrapolation is claimed.

### Results

Controlled sequential native runs on the same cloud host, same cached model and
two inference threads (sampling health with a 350 ms request timeout):

| Case | Baseline | Fixed |
| --- | --- | --- |
| Padded 28 MiB | 200, 0.30 s, no health timeouts | 200, 0.34 s, no health timeouts |
| Dense 40 pages | 200, 11.75 s; 25 health timeouts | 200, 11.53 s; 111 health successes, zero timeouts; max successful probe 23.4 ms |
| Dense approximately 29 MiB | 22 health timeouts in approximately 10 s; still processing when forcibly stopped | 413 page-limit response in 0.22 s; no embedding or publication |

This is a responsiveness/resource fix, not a demonstrated inference speedup.
Native dense-40 peak sampled RSS was approximately 772 MiB baseline and 803 MiB
fixed: backend memory is not claimed to decrease in every case. The worker pool,
model locks, size/complexity budgets and container limits bound admitted work.

The rebuilt backend container requested two CPUs, 1,536 MiB memory and no extra
swap. With dense 40-page input it completed in 8.93 s, served 86 health probes
with no timeouts (maximum 15.6 ms), and measured these stage durations:

| Stage | Seconds |
| --- | ---: |
| Body transfer | 0.00065 |
| PDF extraction | 0.05635 |
| Chunking | 0.00067 |
| Embedding | 8.71054 |
| Index staging | 0.08435 |
| Publication | 0.00238 |

Embedding dominated. The dense 650-page input returned 413 in 0.23 s with zero
embedding/index/publication time. The padded 28 MiB input was accepted and indexed.
Process RSS high-water was 772.66 MiB; maximum quarter-second CPU sample was
approximately 203.7% (tick/quota-window sampling can briefly exceed two CPUs).
These are process metrics, not total container memory including page cache.
Docker stats returned unavailable accounting in this environment, so bounded
`/proc/1/status` and `/proc/1/stat` sampling inside the container was used instead.
Requested resource limits were verified with Docker inspect; Compose parsing also
verified the declared limits. This is not a deliberate OOM/quota-exhaustion test.

The gateway's 28 MiB transfer RSS peak fell from 307.1 MiB to 148.4 MiB, with
baseline-to-peak deltas approximately 199 MiB versus 40.5 MiB. It now streams the
original multipart bytes instead of parsing FormData, copying the PDF and building
another complete multipart buffer. These are one-run observations, not a memory
SLA. Baseline fixture frontend used webpack because its external dependency symlink
was rejected by Turbopack; fixed production build used the normal build command.

### Does processing continue after the frontend times out?

Yes on the baseline. A real dense 40-page replacement was submitted through the
original built gateway. For this controlled test only, its 600,000 ms inactivity
timer was scaled to 500 ms using a test launcher; neither PDF work nor application
source was changed. The gateway returned 504 with the exact message:
`PDF processing timed out after 10 minutes.` Backend processing nevertheless
continued, blocked 30 subsequent health probes, deleted the old point, briefly
exposed an empty index and then stored all 280 replacement points approximately
12.7 seconds after the request began. This establishes the disconnect behavior
without claiming to have waited ten real minutes. The actual user's ten-minute
observation and stats were reported by the user, not independently measured here.

With the fixed pipeline, a frontend client disconnected at 500 ms without changing
application deadlines. The API served 25 health probes with no timeouts, retained
the exact original point IDs, recorded cancellation during embedding, and accepted
a subsequent upload within the approximately three-second observation window.
Running native inference cannot be interrupted halfway through a batch; cancellation
is checked before/after batches and before storage/publication.

## Implementation and limits

- An ASGI upload gate authenticates and admits **one active upload per API process**
  before multipart parsing. Concurrent uploads receive 429 without consuming their
  bodies. Both `/documents/process` and `/documents/extract` use it.
- Maximum PDF: **32 MiB**; maximum multipart envelope: PDF limit plus 64 KiB.
  Both declared and streamed body sizes are checked. Transfer has a 15-second
  absolute budget. The raw body spools after 1 MiB; multipart parsing allows one
  file and no extra fields. Empty/invalid/encrypted/scanned PDFs reject clearly.
- A dedicated single-thread executor runs PDF extraction, chunking, inference and
  storage off the event loop. Limits: **300 pages, 100,000 extracted characters
  per page, 1,000,000 total characters, 1,500 chunks**. Limits are checked before
  inference/storage. No OCR is added.
- Processing has a **90-second cooperative deadline**. It is checked during page,
  embedding and vector batches and before publication. The async request notices
  disconnect or deadline; a cancelled/expired worker must stop at its next check.
  Admission is held until the actual worker exits, even after a 499/504 response,
  preventing repeated timeouts from multiplying queued jobs or model memory.
- PyTorch defaults to two intra-op threads and one inter-op thread. One shared
  inference lock serializes embedding/reranking calls; batches remain 32. Optional
  `DOCLENS_INFERENCE_THREADS` must be 1–4. Compose requests backend two CPUs,
  1,536 MiB memory/no additional swap, and frontend 512 MiB/no additional swap.
  Compose also explicitly selects one API worker.
  The existing Qdrant named volume and Qdrant resource settings are untouched.
- Gateway: backpressure-aware multipart streaming, bounded input and 64 KiB
  response, **120-second absolute deadline**, cancellation propagated to the
  upstream socket, and cleanup for malformed/aborted/oversized replies. The
  deadline includes transfer and cannot be reset by response trickle. Tested with
  real wall time: 504 at 120.009 seconds while the fixture sent bytes every 200 ms.
- Browser: explicit **135-second deadline**, Cancel upload control, 32 MiB client
  validation, response-shape checking, and `finally` cleanup of controller, timer,
  busy state and file input. A failed replacement never overwrites the existing
  Ready document in UI state. Twelve recovery cases passed, including HTTP
  401/413/429/503/504, network error, non-JSON and invalid success response, cancel,
  deadline, oversized file and synchronous FormData construction failure. Browser
  deadline testing used Playwright virtual time; gateway testing used real time.
- Upload duration histograms and failure counters expose bounded stage labels.
  Failure logs identify stage and exception class, not raw exception messages.

### Preserve existing indexed documents

Replacement writes fresh point IDs with a fresh `_doclens_revision`, in batches of
100. No old points are removed. Only after all batches succeed does one atomic,
wait-acknowledged pointer upsert in `doclens_document_publications` make the complete
revision visible. The pointer collection lives in the same persistent Qdrant server
volume, not an ephemeral API-container file. Dense search, BM25 and listing all
apply the visibility filter; partial/unpublished revisions never become results.
Legacy untagged points remain readable until their document is successfully replaced.
Existing point IDs, page/chunk metadata and text are not rewritten.

Regression tests fail the second real Qdrant-local staging batch and the pointer
write before commit, verify old point IDs remain searchable/listed, and verify
retired/unpublished points are hidden. They also reopen storage to check persistence.
Two additional real-server regression tests verify partial-batch failure, pointer
failure, complete publication after acknowledgement loss and a reconnected reader.
An initial reconnect harness used an unsupported QdrantClient context manager; it
was corrected to explicit close and both tests passed. A real-server smoke also
validates successful new-revision publication. The tests
isolate inference/provider calls only where deterministic failure control is needed;
real-model benchmarks and container tests do not mock extraction, inference or storage.

There is an unavoidable acknowledgement boundary: a pointer write can commit even
if its response or the final HTTP response is lost. The outcome is then uncertain;
readers see an old complete revision or a new complete revision, never partial
batches. Old data remains physically retained. No compensating deletion/rollback
can safely promise the old visibility in that case. No automatic retry is added.
Cancellation also cannot undo publication that already committed.

### Review risks and scope limits

- The thresholds are conservative policy ceilings, not a guarantee that every
  PDF below them completes in 90 seconds. Accepted real-model dense testing used
  280 chunks; the 1,500-chunk/1,000,000-character extremes were not capacity-certified.
- Deadlines are cooperative, not a forced thread kill. A stuck native-library call
  or in-flight storage call may finish after the HTTP response. Its admission slot
  stays occupied; it cannot start another pipeline or publish after observing
  cancellation. Storage calls use a ten-second socket timeout; container CPU and
  memory caps provide additional isolation. This is not a native-PDF sandbox or
  proof against decompression bombs. No hard per-native-call deadline is claimed.
- Use one API worker/container for this supported resource budget. Admission is
  process-local, not a distributed quota/durable job service. Restart does not
  resume unfinished uploads. Existing documents and catalogue pointers persist.
- Staged and retired vectors are retained and consume disk. No destructive cleanup,
  retention grace policy, global storage quota or automatic orphan deletion is
  implemented. Those require separate approval; future cleanup remains inventory/
  dry-run only until then.
- All readers must deploy together. Reverting only to the old reader code would
  ignore revision visibility and could return retained/staged points. This branch
  must not be merged wholesale into main/Milestone 2 or treated as an approved
  rollout/migration plan. Existing main uses a different legacy storage path.
- Linux x86_64/cloud validation is not macOS/Apple Silicon validation. No user's
  actual document, existing Qdrant volume, customer data, hosted generation or full
  production Compose stack was accessed. Browser tests use controlled failure
  responses; the separate real-model/server tests establish PDF processing.

## Evidence, setup failures and reproduction

Evidence is committed under `validation/mac-upload-freeze/`: original/fixed backend
and browser measurements, stage/resource samples, real timeout/cancellation probes,
container build/smoke, Compose configuration, and regression results.

Twelve backend tests passed (0.867 s), including exact byte-boundary handling,
acknowledgement-loss semantics and preserved OpenAPI file/auth contracts. Initial tests incorrectly expected BM25 to
return every old point, including chunks not matching the query, or a positive
score for a one-chunk corpus. The multi-chunk fixture/assertion was corrected to
require the matching original point; application scoring was not changed. Failed
runs are retained. Other harness/setup failures are retained too: an old blocked
process could not stop gracefully (bounded forced cleanup added); the baseline
external node_modules symlink needed webpack; Chromium's executable path needed
configuration; Docker stats could not provide samples/stop promptly (replaced by a
finite process sampler); and an npm command was initially run in the wrong directory.
The actual fixed frontend production build, browser test, model/container tests and
corrected regression suite subsequently passed. No failing run is counted as passed.

The reusable scripts are:

```sh
export DOCLENS_FREEZE_FIXTURES=/tmp/doclens-freeze-fixtures
export HF_HOME=/path/to/cached/huggingface
python tests/mac_upload_fixtures.py
python tests/test_mac_upload_limits.py
python tests/test_mac_publication_server.py
npm --prefix frontend ci
# Use CHROMIUM_PATH for an installed Chromium, or install the Playwright browser:
# node frontend/node_modules/playwright/cli.js install chromium
npm --prefix frontend run build
node tests/mac_upload_browser.cjs fixed ./frontend /tmp/doclens-browser-evidence
# A preserved baseline can be exported with git archive 497394b into a separate
# temporary directory; never reset a user's dirty Mac checkout for comparison.
python tests/mac_upload_benchmark.py fixed ./backend padded-28mib.pdf text-heavy-40pages.pdf text-heavy-28mib.pdf
HF_HOME=/path/to/cached/huggingface python tests/mac_upload_timeout_probe.py fixed . /tmp/doclens-cancel-evidence
```

Playwright 1.64.1 is now an exact declared dev dependency; prior locked dependency
versions and platform selectors are retained. A frozen npm-ci dry run validated
the updated lock, and the installed version matches the version used in these tests.
The offline lock update initially lacked an optional package cache entry; a retry
with verified TLS succeeded. No artifact checksum or TLS verification was bypassed.

The scripts require the pinned backend dependencies, Node, Playwright/Chromium,
Docker, cached model weights and the digest-pinned Qdrant fixture. Native fixture
launchers map only `qdrant` to a disposable local service and clear cloud proxy
injection for local traffic. Gateway fixtures map `backend` to their disposable
server. No handler/storage/model result is substituted in the real-model tests.

`recovery/mac-upload/Dockerfile.freeze-validation` builds the application image
from the prior validated CPU dependency image; pinned requirements are unchanged.
The tested image is `sha256:240bdd1bc9ca5ade1cbaea15823e39ad2f6d08ee41f19a4f52f4f1d2b2004153`.
This reuses verified dependencies; it is not a claimed cold build of the Mac's
original Dockerfile. With that image available:

```sh
BUILDX_CONFIG=/workspace/.cache/buildx docker build -f recovery/mac-upload/Dockerfile.freeze-validation -t doclens-mac-upload-freeze:review backend
HF_HOME=/path/to/cached/huggingface DOCLENS_MAC_REVIEW_IMAGE=doclens-mac-upload-freeze:review DOCLENS_MAC_EVIDENCE=/tmp/doclens-container-evidence python tests/mac_upload_freeze_smoke.py
```

Tests use generated synthetic credentials and disposable resources. Environment
files containing those test credentials stay outside the committed evidence.
Hardware: AMD EPYC 9V74/KVM x86_64, five visible logical CPUs, four-core cgroup quota,
32 GiB host memory quota; container tests requested the tighter limits above.
Node 24.19.0, Python native 3.12.14/container 3.11; PyMuPDF 1.26.5, Next.js 16.3.6, Chromium 154,
Qdrant 1.15.5; embedding model cached revision
`1110a243fdf4706b3f48f1d95db1a4f5529b4d41`. Elapsed times use monotonic clocks,
probe samples use explicit request deadlines, native memory uses `/proc`, and
container stages use Prometheus histogram deltas. These are reproducible functional
measurements, not independently certified p95/SLA or Mac performance claims.

Reviewer priorities: off-loop work/admission lifetime, limits before mutation,
deadline/disconnect behavior, backpressure/socket cleanup, old-data visibility on
all read paths, pointer uncertainty, persistent catalogue/restart behavior, and
busy-state cleanup. Return findings and an approve/request-changes recommendation.
Do not merge or deploy.
