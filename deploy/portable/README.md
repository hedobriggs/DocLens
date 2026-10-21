# Install and operate DocLens

This is the single supported installation path for this release candidate. It
includes reviewed complete-answer logic and the candidate legal-workspace UI. It is not
permission to replace an existing Mac installation, migrate data or deploy.

## Prerequisites

Docker-capable **Linux amd64** host (or Intel Docker Desktop), Docker Compose
**2.30+**, Python 3 and Git. Python here uses its standard library; backend
Python 3.11 is inside the image, not required on the host. Native Mac/Safari
acceptance remains unverified. ARM/emulation and ordinary RunPod containers
without a Docker daemon are not validated deployment targets.

Plan initially for 4 vCPU, 16 GB RAM and 30 GB free disk. These are estimates,
not measured limits. Check whole-stack memory, swap and disk pressure before
building. Stop if headroom is insufficient or uncertain. Do not stop original
services, prune volumes or raise controls to make a test fit.

## Build from this checkout

Use a new directory/project. Never extract over an existing installation or
attach its volumes. Run each command only after the preceding command succeeds.
From the repository root:

```sh
python3 deploy/portable/build.py
```

The builder verifies `application-manifest.json` and copies only its listed files
into fresh build contexts; credentials, untracked files, backups and indexes are
excluded. Requirements, npm lockfile, base digests and model revisions are pinned.
The application baseline and exact file hashes are recorded in the manifest.
Images are built locally, not published to Docker Hub. Record image IDs for the
release; do not substitute an old image archive after changing source.

For authorized build proxies only, set `BUILD_CA_BUNDLE` to an existing public PEM
trust bundle. It is mounted during build steps; TLS verification stays enabled.
Do not put credentials in build arguments or disable certificate verification.

## First run: synthetic acceptance only

In `deploy/portable`, use a fresh project and synthetic credentials:

```sh
python3 configure.py --synthetic-test --port 0
./doclens up -d --no-build --wait --wait-timeout 180
python3 smoke.py --restart
```

The initializer refuses an existing `.runtime` directory or project/volume name
collision. The smoke exercises login, real embeddings/indexing of a five-employer
PDF, failed-replacement preservation, page-limit rejection and restart identities.
It does not contact Gemini with a dummy key. Preserve failed and successful test
output outside the checkout. See [testing](../../docs/TESTING.md).

## Approved cloud installation

After acceptance and separate deployment approval, configure a **different fresh
project**, not the synthetic runtime. Point a DNS name at the server and allow
only the required host ports (80/443 and restricted administration). Then:

```sh
python3 configure.py --domain YOUR-REAL-DNS-HOSTNAME
./doclens --https up -d --no-build --wait --wait-timeout 180
./doclens --https ps
```

The initializer privately prompts for administrator email, a 12+ character
password (maximum 72 UTF-8 bytes), and Gemini API key. It creates a session secret
and mode-0600 files inside mode-0700 `.runtime`. No secret is committed or built
into images. Docker administrators can inspect runtime environment values.
Caddy obtains HTTPS certificates; DNS, firewall and public ACME must be validated
on the target host. Do not expose backend 8000 or Qdrant 6333/6334.

Production uses Secure session cookies. Use HTTPS; plain remote HTTP and ordinary
HTTP SSH tunnels are not a supported login procedure. A synthetic smoke that
supplies its own cookie is not proof of public HTTPS browser operation.

## Simple local launcher

The root `./start` / `./stop` wrappers use this same deployment package, not a
second application. For a separately approved fresh local setup, copy
`.env.example` to `.env`, set its permissions to 0600, and replace the placeholder
privately; alternatively provide `GEMINI_API_KEY` through a secret environment.
Run `./start` interactively for login setup. Later starts reuse saved credentials;
`./stop` preserves data. An occupied default port may be changed on first setup
with `./start --port 3001`. Never copy original credential files into a trial.

The launcher does not provide public HTTPS by itself. For public cloud servers,
use the approved DNS/HTTPS configuration above and a real browser acceptance
check. Local HTTP smoke cookies do not establish production login support.

## Operation and recovery

Use `./doclens --https` consistently for a TLS installation; omit `--https` only
for a project created without Caddy:

```sh
./doclens --https ps
./doclens --https logs --tail 50 backend frontend qdrant
./doclens --https stop
./doclens --https start
```

Qdrant data and snapshots use project-specific named volumes; TLS certificates
also persist. **Never run `down -v`, volume prune or delete the host disk** for a
live installation. Host destruction still loses attached volumes: use persistent
cloud disks and private off-host backups. Keep original PDFs separately; the
vector index is not an originals archive. Old revisions remain retained.

Before relying on a backup, stop that project's services, copy both Qdrant
`/qdrant/storage` and `/qdrant/snapshots` from its stopped container, archive and
validate them, then restart the same project. Preserve `.runtime` privately and
separately. Restore only into a fresh empty project using the same Qdrant version;
copy the trusted storage/snapshot directories to its stopped Qdrant container,
start it, and verify point/payload/publication identities. Never merge backup
files into an existing index or assume a readable archive proves restoration.
Retain/reissue TLS certificates subject to public ACME constraints.

Do not share `.runtime`, cookies, full container metadata or `docker compose
config` output. Redact logs before sharing. Session-secret rotation invalidates
existing sessions. No source-PDF migration or destructive cleanup is included.
