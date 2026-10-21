# Portable package validation

Application source: `66db29f0b072fd9821869f4ffef008883ce0509b`.
Packaging is additive under `deploy/portable`; application files, dependencies,
limits, authentication, publication catalog and recovery logic are unchanged.

## Independently executed in this packaging task

- Built both linux/amd64 images with pinned base image digests, original locked
  requirements/npm dependencies, CPU PyTorch and both pinned model snapshots.
- Executed the distributed `build.py` with its verified, curated contexts. Both
  builds completed; local secrets/data were not context inputs.
- Backend embedding and cross-encoder inference succeeded with `--network none`,
  two CPUs, 1536 MiB memory and equal memory/swap ceiling. Actual 384-dimensional
  embedding and a reranking score were produced; no download was possible.
- Fresh Compose project reached backend/frontend healthy states; database and
  backend had no published ports and frontend bound only loopback.
- `python3 smoke.py --restart` passed twice. Each run verified anonymous upload
  401; synthetic login 200; real five-page PDF to five embedded/indexed chunks;
  malformed replacement 400 and 301-page replacement 413 preserved all existing
  point/payload/publication records; full-project restart preserved those records.
- A stopped-database backup was copied, archived and restored into a **second
  fresh project**. Exact stored points, payloads and publication catalog matched
  the original test project. Only synthetic indexes were used.
- Caddy reverse proxy successfully served HTTPS with explicit trust in a local
  test CA (certificate verification enabled), issued a Secure session cookie on
  login, and served the authenticated dashboard using a normal cookie jar.
- Ambient `COMPOSE_PROJECT_NAME`/port values could not redirect the wrapper to
  another project or port. The initializer refused an existing `.runtime` folder.
- Four failure/context-isolation tests passed: existing runtime cannot be
  overwritten, an unlabelled existing data volume is not adopted, changed
  application source stops before building, and untracked credentials are
  excluded from build contexts.
- Image metadata verified amd64, non-root application users, source revision
  labels and no application credential variables in the images.
- Docker archive export completed after capacity correction. See release
  SHA256SUMS and image manifest. Archive contents were read to completion and
  Docker successfully loaded both exported images with matching image IDs.

Environment: managed Linux x86_64, Docker 28.4 (VFS), Compose 2.40.3. Build TLS
used an authorized public/system CA bundle mounted as a BuildKit secret; TLS
verification stayed enabled. No application credentials were supplied at build.

## Initial failures and corrective actions

1. Docker Buildx tried a read-only home cache path. Build commands were rerun
   with a writable task-specific `BUILDX_CONFIG`, preserving Docker credentials.
2. First backend startup failed because source files inherited mode 0600 and
   the runtime user is non-root. Backend application COPY now explicitly sets
   mode 0444. Rebuilt image reached healthy and passed functional tests.
3. Two dependency rebuild attempts were intentionally cancelled when changed
   context metadata invalidated valid layers. The curated builder preserves
   file modes; the final clean-context build reused the valid dependency layers
   and completed. These cancellations are not successful builds.
4. First HTTPS test returned proxy 403 because internal frontend traffic used
   this environment's outbound proxy. Caddy now sets NO_PROXY/no_proxy for its
   internal service; verified HTTPS login then passed.
5. First combined image export ran out of Docker scratch space while a second
   test project was also running. Only that completed synthetic restore project
   was removed; no global prune was run. Retried export completed with space
   available. The incomplete first export was replaced and is not distributed.

Docker's heuristic secret-name warning for `HF_HUB_DISABLE_IMPLICIT_TOKEN=1`
refers to a Boolean disabling implicit token use, not an embedded token.

## Not established

- No live Gemini request was made by this package test (dummy synthetic key).
  Earlier reviewed application live-provider results do not certify a new cloud
  environment's key, network, latency or answer quality.
- Public DNS, ACME issuance, an Internet deployment, physical Intel Mac, Safari,
  VoiceOver, ARM-native compatibility and whole-stack peak resource requirements
  were not tested. Local-CA HTTPS is not public-certificate issuance evidence.
- No existing Mac index or RunPod data/configuration was accessed or migrated.
- No registry image publication, main merge, production release or change to the
  running RunPod was performed. The pre-existing original checkout stays intact.

The portable package is a tested deployment candidate, not a claim of production
security certification or guaranteed compatibility with every cloud platform.
# Simple start/stop launcher follow-up

The root `start` and `stop` scripts delegate to a stdlib Python launcher and the
existing scoped portable Compose wrapper. Application source and image contents
are unchanged. The initializer now optionally reads the provider key from its
environment; its original manual key prompt remains available.

On Linux amd64, a fresh isolated checkout was configured through a real terminal:
email, hidden password and hidden confirmation were requested; the synthetic
provider key came from a private mode-0600 root `.env`. Existing tested image
tags were reused. All services became healthy; anonymous upload was rejected,
login returned 200, a synthetic five-page PDF indexed five chunks, invalid and
301-page replacements preserved records, and the existing restart check passed.
Then `./stop` and `./start </dev/null` succeeded. Exact points, payloads and
publication records matched the pre-stop snapshot, and login still returned 200.
No live Gemini calls or customer data were used. Only the trial's own containers
and volumes were removed after testing.

All 14 launcher/packaging tests passed: missing and placeholder keys, private-file
permissions/literal parsing, symlink-runtime refusal, saved-port preservation,
unconfigured stop, prompt-free restart, scoped stop, propagated build/Compose
failure, and the original four packaging safety checks. Bash syntax and Git
whitespace checks passed. See `evidence/launcher-tests.txt` and
`evidence/launcher-result.json`. The automatic missing-image build path was
tested with mocked failures; full image builds were validated previously below.
This follow-up did not repeat a full image build or physical Mac/Apple Silicon
acceptance. It does not reset an existing installation's password.
