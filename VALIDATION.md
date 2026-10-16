# DocLens review evidence

Branch: `improve/uploads-monitoring` (local only; no GitHub PR or push).
Base: `e800f34018474c411ba609654c13ccf4d59cb05f`.
Implementation revision: `dcf5222fbecd25901abb50a454cd2ba6bba2d9a2`.
Subsequent evidence-only commits do not change the application. Use `git rev-parse
HEAD` for the complete review head including this report. The original e800f34
checkout does not contain the implementation.

## Implemented requirements

1. Upload proxy: explicit configurable 1–600000 ms processing deadline (600000
   default), Undici headers/body limits and overall abort. Timeout -> actionable
   504; upstream application error status/message preserved; invalid JSON/schema
   and unavailable service produce distinct 502 messages. The UI always clears
   its busy state and file input in finally, or resets early on file-size rejection.
2. Both originally missing Grafana files are committed. Five dashboards reference
   datasource UID `prometheus`. Dashboard directory and overview use non-overlapping
   read-only bind mounts. CPU/system, AI, application and storage link from overview.
3. Admin-only DocLens Monitoring route/link checks the signed session's admin role.
   Grafana uses independent credentials, no anonymous/self-signup access, an
   admin-only monitoring organization (no automatic user assignment), and folder
   permissions. Bootstrap removes legacy non-admin organization members. Both
   dashboard and datasource access are denied for a Viewer in live tests.
4. Backend operation duration/outcome instrumentation covers upload, indexing,
   embedding, reranking and Gemini; actual Qdrant counts/files provide storage
   metrics. node-exporter and cAdvisor provide host/container metrics. No sensitive
   content or unbounded document names are metric labels.
5. Provider usage/cost samples are created only when observed/configured, not
   synthesized. Isolated provider tests exercise reported tokens, configured cost,
   successful generation and provider failure. Live missing-key errors are measured.

## Clean-checkout commands and results

Clean clones were made locally, without a worktree or remote push:

```sh
umask 022
git clone --no-hardlinks --branch improve/uploads-monitoring /workspace/DocLens /tmp/doclens-review-public
```

An additional clean frontend clone at `/tmp/doclens-review-clean` was used for
locked installation, production build and browser checks. It was updated with
`git pull --ff-only` from the local source branch as fixes were committed.

Frontend, working directory `/tmp/doclens-review-clean/frontend`:

```sh
npm ci --cache /workspace/.cache/npm
npm run lint
npm run build
npm run test:e2e
```

Results: installation, lint, production build and TypeScript check passed.
**13 browser tests passed**, running Chromium against production Next.js and an
actual controlled HTTP upstream. Covers 400 ms slow success under a 1500 ms test
deadline; expiry before headers and during body; upstream 503; disconnection;
invalid JSON and invalid success schema; network failure, non-JSON ingress error,
401 and oversize UI recovery; admin allowed/viewer denied; authenticated 25 MiB
multipart forwarding and invalid-request status distinctions. Test timing is
scaled; no ten-minute wall-clock test was run. Fixture/model isolation is explicit.

Python, working directory `/tmp/doclens-review-clean`:

```sh
/workspace/DocLens/backend/.venv/bin/python -m unittest discover -s tests -v
```

Result: **8 tests passed**. Six HTTP checks include 25 MiB PDF transfer, >50 MiB
rejection, invalid PDF, auth, request counter/duration exposition and concurrent
health AND metrics response during blocked embedding. Two monitoring checks cover
all dashboard references/links and real instrumentation around isolated models /
provider with actual local Qdrant, including tokens/cost and success/error counts.
This does not rely on the assertion-free manual `backend/test_retrieval.py` script.

Manifest/config, working directory `/tmp/doclens-review-public`:

```sh
docker compose config --no-interpolate --no-env-resolution --quiet
docker run --rm --entrypoint promtool \
  -v /tmp/doclens-review-public/monitoring/prometheus.yml:/etc/prometheus/prometheus.yml:ro \
  prom/prometheus:v3.5.0 check config /etc/prometheus/prometheus.yml
```

Results: both passed. Compose validation deliberately does not resolve deployment
secret files or interpolate passwords. Standard umask 022 matters: the machine's
umask 077 initially made non-root monitoring containers unable to read config.

Native live acceptance, working directory `/tmp/doclens-review-public`:

```sh
HF_HOME=/workspace/.cache/huggingface /workspace/DocLens/backend/.venv/bin/python \
  tests/runtime_monitoring.py --python /workspace/DocLens/backend/.venv/bin/python
```

Result: passed with real embedding/reranking models and Qdrant; generated 25 MiB
PDF indexing before AND after first scrape; Prometheus `backend:8000` UP; five
provisioned Grafana dashboards; anonymous/Viewer dashboard denial and Viewer
Prometheus-datasource denial. Finite samples returned through Grafana for upload
and AI p95 latency, API rate, embedding/reranking observations, Gemini errors,
document/chunk counts, Qdrant file bytes, host CPU/memory/disk and named-container
freshness/CPU/memory. Missing provider token/cost series were absent as expected.

Container build, working directory `/tmp/doclens-review-public`:

```sh
python tests/build_backend_cloud.py
```

Result: passed with package/TLS verification enabled, using the existing proxy and
system CA bundle through a temporary BuildKit secret. CPU image:
`sha256:49fe905a05c4c0fa28efa512aa455accf023ee47b01361f656ae576a54773024`
(1.53 GB). Backend build source was
`faa03dfac36f18530c9af6a8b4fa700ccc93ae16`; subsequent implementation changes only
added runtime evidence logging. The previous default CUDA image built but two
concurrent container copies exhausted disk; its artifacts/cache were removed.
The default CPU-wheel build and sequential acceptance corrected that resource issue.

Final container live acceptance, clean checkout `/tmp/doclens-review-public`:

```sh
set -o pipefail
HF_HOME=/workspace/.cache/huggingface /workspace/DocLens/backend/.venv/bin/python \
  tests/runtime_monitoring.py --python /workspace/DocLens/backend/.venv/bin/python \
  --backend-image doclens-review-backend | tee /tmp/doclens-runtime-evidence.txt
```

Result: passed. The backend ran inside the built Python 3.11 image; Prometheus,
Grafana and both exporters ran as real containers. See
`validation/runtime-monitoring.txt` for stdout and returned sample values.
Examples: documents=1, chunks=1, Qdrant bytes=12816, embedding observations=4,
reranking observations=2, Gemini missing-key errors=2, and finite upload/AI latency
and named-container CPU/memory/freshness samples. Ephemeral credentials were
randomly generated, never logged, and discarded with the test environment.

Final dependency and regression check inside the image:

```sh
set -o pipefail
docker run --rm --entrypoint sh \
  -v /tmp/doclens-review-public:/src:ro -w /src doclens-review-backend \
  -c 'python -m pip check && python -m unittest discover -s tests -v' \
  2>&1 | tee /tmp/doclens-container-tests.txt
```

Result: **No broken requirements; 8 tests passed**. Raw output is saved in
`validation/container-tests.txt`. All acceptance containers/processes were removed.

The final browser check ran against
`c2a6cfa1cea954abba8e8dafcc20c1c92fcf8d00`; frontend application/test files are
unchanged in the final implementation revision. Native live checks additionally
passed before the container run. Build/runtime infrastructure corrections were
committed and validated before this report.

## Independent reviewer transfer

No remote branch/PR was published. A Git bundle is supplied separately as
`/workspace/DocLens-review.bundle`, containing the exact branch commits after the
base above. In the reviewer's existing repository, attach/download the bundle and:

```sh
git bundle verify /path/to/DocLens-review.bundle
git fetch /path/to/DocLens-review.bundle improve/uploads-monitoring:review/doclens-monitoring
git switch review/doclens-monitoring
git rev-parse HEAD
git diff e800f34018474c411ba609654c13ccf4d59cb05f..HEAD
```

The final HEAD is returned in the client handoff; this evidence report is itself
committed on top of the implementation SHA. Do not review e800f34 alone.

## Remaining release validation

- The user's exact dense 25 MB PDF and deployed reverse proxy/platform are not
  available. Generated 25 MiB fixtures verify transport size; one-page text does
  not reproduce the inference cost of a large manual. Test the original document
  and target deployment timeouts before declaring that production incident fixed.
- No configured Gemini key was used for live successful hosted generation. Live
  token billing/cost accuracy is unverified; provider mocks prove instrumentation,
  not real provider behavior. Cost is only an estimate using configured token
  prices and excludes unsupported billing dimensions.
- Live acceptance uses host networking and aliases configured service hostnames
  to loopback. Full Compose deployment, external TLS/routing, actual deployment
  credentials and remote-browser access still require deployment validation.
- Keep Grafana loopback-only until `grafana-permissions` exits successfully; keep
  monitoring's org admin-only. Existing Grafana volumes retain their passwords.
- A frontend timeout does not stop backend work. Ingestion is synchronous, its
  replacement writes are not transactional, and multipart parsing precedes the
  application's size check. External ingress limits and durable background jobs
  remain architectural/deployment considerations.

No push, merge or main-branch change has been made. This is review evidence, not a
request to approve a production release with the above checks outstanding.
