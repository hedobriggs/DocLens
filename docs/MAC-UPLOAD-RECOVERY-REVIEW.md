# Mac upload recovery: independent review handoff

The user reported `IndentationError: unexpected indent` at `backend/main.py:371`
in an uncommitted Mac checkout based on `e800f34018474c411ba609654c13ccf4d59cb05f`.
The uploaded file reproduces that exact error. Its retrieval timer assignment has
seven leading spaces, while this function body uses four. Python compiles the
whole module before starting FastAPI, so this also prevents unrelated PDF routes
from starting. Removing those three spaces is the only application-code change.

## Preservation and review boundaries

Branch: `fix/mac-upload-indentation`.
Input snapshot: `c0509bbd6c5648876c3699306b5f7ad1ae29a584`.
Review the fix commit supplied in the handoff relative to that snapshot.
The snapshot deliberately contains the original syntax error and the user's
existing local work; it is preservation evidence, not approval of that work.
Do not merge this branch wholesale into main, merge any commit, or deploy.

All eight supplied tracked modifications are preserved byte-for-byte in the input
snapshot. The ambiguous `route.ts` uploads were identified from their contents:
4,136 bytes is `frontend/app/api/documents/process/route.ts`; 1,599 bytes is
`frontend/app/api/auth/login/route.ts`. Hashes and sizes are recorded in
`recovery/mac-upload/original-sha256.json`. The final working files match those
hashes except for the single indentation correction in `main.py`. No other local
feature, endpoint, prompt, upload timeout, batching, or storage behavior was edited.

The Mac itself was not accessed. Its untracked `1`, backup files and
`fix_doclens_stop.py` were not supplied and have not been changed by this work.
This is preservation of the eight uploaded tracked files, not a complete backup
of every file on the Mac. The cloud's existing main and Milestone 2 work were
retained on their branches; the recovery branch starts from the stated Mac base.

`recovery/mac-upload/indentation-fix.patch` contains only the one-line correction.
Following independent approval, applying this patch with `git apply --check --unidiff-zero` and
`git apply --unidiff-zero` preserves the Mac's other changes. Do not replace the whole working
file or reset/checkout the Mac tree to install the fix.

## Validation and limits

Evidence: `validation/mac-upload/`. The original error was reproduced with the
uploaded bytes in native Python 3.12 and container Python 3.11. The corrected file
compiles, starts and handles synthetic PDF uploads in both environments.

The real smoke test uses a disposable digest-pinned Qdrant 1.15.5 server and cached
`sentence-transformers/all-MiniLM-L6-v2` model revision
`1110a243fdf4706b3f48f1d95db1a4f5529b4d41`. Each native/container request uploads a
synthetic two-page PDF, verifies two genuine 384-dimensional stored vectors and
page numbers, and checks extraction, metrics, anonymous upload rejection and
invalid-PDF rejection. The built Next routes are also exercised: real bcrypt login,
real signed session cookie, anonymous denial, and multipart PDF forwarding to the
rebuilt backend with real indexing. No extraction, inference, storage, login or
HTTP handler is mocked. No hosted Gemini request or customer data is used. A
synthetic non-provider key permits the unchanged generation module to initialize.

The production Next build passed. The HTTP gateway test explicitly sends the
actual Secure session cookie over isolated loopback HTTP; this is not a browser,
TLS, CORS or production-cookie deployment test. For native tests only, a temporary
routing adapter maps the uploaded hardcoded Compose service names to disposable
loopback ports. The backend container uses real Docker DNS `qdrant` on an isolated
network; no storage endpoint code was modified.

The rebuilt image is recorded in `validation/mac-upload/runtime.json` and was
built by copying the reconstructed, corrected backend into an existing verified
CPU dependency image. Its requirements input matches the Mac base byte-for-byte;
`pip check` passed. `recovery/mac-upload/Dockerfile.validation` records this cloud
build method. This validates a rebuilt application image with the same pinned
requirements, not a fresh install through the Mac's original Dockerfile. That
Dockerfile was preserved unchanged. The validation container runs as root to match
the original Mac Dockerfile, overriding the dependency image's non-root default.

These checks ran on Linux x86_64, not macOS/Apple Silicon: native Python 3.12,
container Python 3.11, CPU model inference, four-core cgroup quota and 32 GiB memory
limit. PDF fixtures are two pages (gateway: one page). This is functional evidence,
not a throughput, upload-size, concurrency, cancellation or latency benchmark.
Ask/hosted generation, monitoring containers and the complete Compose deployment
were not exercised. No production migration or cleanup was performed.

## Failures and subsequent passing checks

1. Original uploaded source and container compilation failed at line 371 as
   reported. Removing three spaces corrected module parsing.
2. Initial image build could not create Docker's default buildx config beneath
   the read-only home directory. Using the existing writable `BUILDX_CONFIG`
   allowed the same application image build to finish.
3. Initial native and container uploads received `403 Domain forbidden` from
   the cloud proxy when calling the local Qdrant service. The diagnostic probe
   showed service DNS resolved correctly, default HTTPX returned 403, and a direct
   local HTTPX request returned 200. The cloud injects proxy variables into Docker
   processes despite explicit environment-file settings. The final test launcher
   clears proxy variables inside the fixture process before importing the app;
   native fixture processes are similarly isolated. Only local test traffic is
   affected. Application files, TLS verification and external network policy were
   not changed.
4. Final native, rebuilt-container and built-Next gateway checks all passed.
   Successful results and the earlier failures are retained separately.

## Reproduction

Fetch the review branch and inspect the snapshot and fix commit separately. Use a
fresh review checkout rather than overwriting a user's dirty working tree.

With the existing verified CPU dependency image available:

```sh
BUILDX_CONFIG=/workspace/.cache/buildx docker build \
  -f recovery/mac-upload/Dockerfile.validation \
  -t doclens-mac-upload-review:fixed backend
cd frontend
npm ci
npm run build
cd ..
HF_HOME=/path/to/existing/huggingface/cache \
  DOCLENS_MAC_EVIDENCE=/tmp/doclens-mac-review-evidence \
  python tests/mac_upload_recovery_smoke.py
```

The Python environment needs the pinned backend requirements and requests. If the
cloud-specific dependency image is unavailable, build the supplied original
`backend/Dockerfile` under the same test image tag instead; cold installation via
that path has not been validated here. The test requires Docker and Node, uses
random synthetic credentials, and removes only the containers/network it creates.
Keep its generated runtime environment file private; it is not a repository input.

Reviewer focus: verify the original-file hashes, the single application-line diff,
module parsing, startup and actual stored vectors; distinguish the preserved user
changes from this fix. Return findings and an approve/request-changes decision for
the fix. Do not merge, deploy or treat this as Milestone 2 implementation.
