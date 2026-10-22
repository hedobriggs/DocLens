# DocLens on RunPod

Dedicated **single container**, CPU inference, no Docker-in-Docker, Compose,
terminal dependency installation, SSH or Jupyter. Macs and ordinary VMs continue
using the root Docker Compose installation unchanged.

## Release prerequisite

This candidate must be independently reviewed and its image published to an
accessible registry **before** a user can select it on RunPod. `template.json`
is a template specification, not an already deployed/published RunPod template.
Replace `imageName` with the reviewed `registry/image@sha256:...`, never an
unverified latest tag. Registry publication and a paid RunPod trial are not
performed automatically. No actual RunPod validation is implied by local tests.

Maintainer build (from a clean exact reviewed Git checkout; not on the Pod):

```sh
set -eu
docker build --platform linux/amd64 -f deploy/portable/Dockerfile.backend -t doclens-portable-backend:compose-auto backend
docker build --platform linux/amd64 -f deploy/portable/Dockerfile.frontend -t doclens-portable-frontend:compose-auto frontend
docker build --platform linux/amd64 -f deploy/runpod/Dockerfile -t doclens-runpod:candidate deploy/runpod
```

Existing pinned dependencies and both pinned embedding/reranker models are
baked into these images. No source, private `.env`, PDF or credentials belong in
the RunPod build context. Publish only after review; record resulting digest.

## Private template settings

Create three private RunPod secrets (not public template literal values):
`doclens_admin_email`, `doclens_admin_password` (12+ characters, at most 72 UTF-8
bytes), `doclens_gemini_key`. Bind them as specified in `template.json`.
Never put values in Git, screenshots, support logs or a shared template.
RunPod injects these as environment variables: account administrators/root can
access them. This is not protection against a compromised Pod or account.
Plaintext password is removed from child environments and transient setup file;
only bcrypt hash, session secret and Gemini key persist with restricted UIDs.
Each child has separate UID; frontend cannot read backend configuration.

Use an amd64 Pod with **at least 2 CPU / 4 GB RAM initially**, 15 GB container
disk and a **20 GB attached persistent volume mounted at `/workspace`**. This
is a trial starting allocation, not a measured capacity guarantee. No GPU is
required. Expose **only `3000/http`** through RunPod's HTTPS proxy. Do not expose
8000, 6333, 6334, SSH or Jupyter. Do not override the image entrypoint/start
command. The API and Qdrant bind to loopback. TLS terminates at the RunPod proxy;
Secure session cookies require its HTTPS URL. RunPod proxy behavior and browser
login must be tested on the actual provider before production use.

## Persistence and safety

The entrypoint refuses to start without a mount at `/workspace`. It locks the
installation against simultaneous writers and stores Qdrant storage, snapshots,
and matching private configuration under `/workspace/doclens`. It refuses an
existing index with no matching configuration or changed credentials; it never
resets/adopts/migrates it. Use a **new empty volume** for synthetic trials, never
attach the Mac's data. Keep the same three secrets for restart; rotation requires
a separate procedure. API/frontend/Qdrant failure stops the whole container.
Allow at least 30 seconds for graceful shutdown; forced interruption of an
in-flight upload is not durable job processing.

Pod stop/start with the same disk and Pod deletion are different operations.
A Pod volume may be deleted with the Pod; use a retained/network volume only
where Qdrant's filesystem/locking/durability requirements are satisfied. Actual
RunPod network-volume durability, fsync, locking and crash recovery remain a
provider test gate. Do not claim backups from snapshots that were never taken.
Back up matched configuration plus Qdrant using a separately tested backup
procedure; never copy live database files as a consistency guarantee. Never run
two Pods against the same storage. Original PDFs remain external: retain them.

The existing 32 MiB/300-page/text/chunk limits, bounded inference and upload
cancellation behavior remain unchanged. This image does not add durable jobs,
raise limits, migrate data or provide automatic backups. RunPod enforces the
whole-Pod CPU/RAM allocation, not Compose per-service cgroups; CPU inference
remains two threads. Measure actual whole-stack RAM/disk before larger trials.

## Required validation before release

Run synthetic-only login, anonymous denial, real PDF upload, invalid replacement,
limit rejection, live Gemini five-employer/citation test, restart with the same
volume and session cookie, exact Qdrant point/publication identity comparison,
missing-volume/secret refusal, child failure shutdown and frontend-only network
exposure tests. Preserve failures and retries. Verify HTTPS browser login on
RunPod, volume stop/start, forced restart recovery and disk/resource use there.
Local Docker tests exercise this single container directly, not nested Docker;
they do not establish RunPod proxy or storage compatibility.

## Candidate validation — 22 October 2026

Application/Compose baseline: `aeeccd4304bbac10087b937b02f8581d48fabb5b`.
No changes under `backend`, `frontend`, `deploy/portable`, or root `compose.yaml`.
Local image ID (not a published registry digest):
`sha256:8ef2816e6ff79065cc5450ffa3c3d3614da87f1c02b916d6ef7351424ed380cc`.
The running supervisor matched source SHA-256
`adc00771e6056b94fdd957e964bd02b8698363f67015272a6f8746b5d58c5702`.

Maintainer verification commands and final outcomes:

| Command | Outcome |
| --- | --- |
| `python3 tests/test_runpod_contract.py` | 6 passed, including real launch-function secret filtering, UIDs, bind-mount detection and private template/build context |
| `node --test tests/test_bootstrap.cjs` | 9 passed |
| `python3 deploy/portable/test_packaging.py` | 6 passed |
| `python3 deploy/portable/test_launcher.py` | 11 passed |
| `python3 tests/test_runpod.py --live-answers` | Exit 0; all scenarios below passed |
| `git diff --check` and unchanged-application/Compose comparison against baseline | Passed |

For this managed cloud runner only, the last command used
`DOCLENS_TEST_CA=/etc/ssl/certs/ca-certificates.crt` to mount the runner's combined
public CA bundle read-only. TLS verification remained enabled. Ordinary hosts
using standard public CA trust do not need that test option. Build used existing
verified portable image IDs `8305b859527a366c210dde946d6daf5567597c709b5133388df44d0b8502a17b`
(backend) and `40bf1b1c5cc9276de85de9c880c0c98e24774252c01d4f2f90397017963e9778`
(frontend), supplied using the Dockerfile's two build arguments.

Passed integration scenarios: refusal without volume/secrets; anonymous upload
and incorrect login denied; valid login with Secure/HttpOnly cookie; five-page
synthetic PDF indexed with real embedding model; malformed/301-page replacements
rejected without changing records; live Gemini returned all five known employers
and correct five page citations; API 8000 and Qdrant 6333/6334 listened only on
loopback; only frontend 3000 published; frontend UID denied backend settings;
second writer denied the lock. After a graceful container restart, both Qdrant
collections retained exact point IDs, payloads and publication/citation identities;
the previous cookie and a second live Gemini answer worked. Terminating Qdrant
stopped the whole container. All test containers and synthetic volumes were removed.

Linux amd64 Docker trial, **2 CPU / 4 GiB cgroup allocation**: reported memory
peak **491,872,256 bytes**, later snapshot **420.4 MiB**, persisted synthetic
storage **344,172,227 bytes**. These are whole-container observations for the
small five-page/comprehensive-question fixture, not dense-document capacity,
normal reranking-path performance, Mac measurements or a supported-limit increase.

Failures and corrections retained in the external evidence archive:

- An acceptance attempt started before the image build completed and failed;
  subsequent runs waited for a successful build.
- Builds exhausted this runner's VFS-backed disk. Removed unused rebuildable
  cache and this task's superseded image/stopped synthetic container; consolidated
  final image assembly. Subsequent image builds passed. No original installation
  or unrelated volume was removed.
- Inspection identified Debian 13 Qdrant versus Debian 12 Python/Node runtime
  coupling; Qdrant now uses its own matching loader/libraries, isolated from the
  system runtime. The resulting container passed real startup and persistence.
- A mounted-volume startup attempt failed validation: `os.path.ismount` misses
  same-device bind mounts. Replaced it with `/proc/self/mountinfo` validation and
  added positive/negative regressions. Missing-volume refusal still passed.
- Two process-environment inspection probes returned non-zero. Those iterations'
  harness discarded command stderr, so their exact cause was not retained.
  Removed that unreliable probe and tested the actual production launch function
  with captured child environments instead. Direct runtime `/proc/environ`
  verification remains unestablished; filesystem separation passed in-container.
  The final harness preserves Docker command stderr and the complete suite passed.

Qdrant logs warnings about absent optional default config/static dashboard and
its unwritable optional initialization marker; these did not prevent readiness,
indexing or restart persistence. Its container-filesystem warning also does not
prove a RunPod volume is suitable. **Still blocked/unverified:** image registry
publication, an actual RunPod template/Pod, HTTPS browser login/proxy upload
behavior, provider volume durability/locking/forced crash recovery, backup restore,
and larger/dense-document resource measurements. No RunPod/registry access is
attached to this session. Do not treat this candidate as a deployed release.
