# Run DocLens with Docker Compose

Fresh installations need **Docker Desktop/Engine with Compose 2.30+** and a clean
checkout. Target: Linux amd64, including Intel Docker Desktop. Host Python, Node
and manual build/configuration scripts are **not required** for this workflow.
Physical Mac, Safari/VoiceOver and whole-stack operation on an 8 GB Mac remain
unverified; stop if memory/swap/disk headroom is insufficient or uncertain.

## One-time private settings

In the new DocLens checkout, create the private file without overwriting one:

```sh
(
  set -eu
  test ! -e .env
  test ! -L .env
  umask 077
  cp .env.example .env
  chmod 600 .env
)
```

If `.env` already exists, keep it; do not replace it. Edit it privately to provide
`GEMINI_API_KEY`, `DOCLENS_ADMIN_EMAIL` and `DOCLENS_ADMIN_PASSWORD`. Passwords need
12+ characters and at most 72 UTF-8 bytes. Single-quote passwords containing dollar
signs. The file is parsed as data, never sourced as shell code. Keep
`COMPOSE_PARALLEL_LIMIT=1` to avoid parallel first-time builds on small hosts.
Do not share or commit `.env`. Placeholder values are rejected.

## Start and stop

From the repository root:

```sh
docker compose up -d --wait
```

Compose builds the current images automatically, reusing cached layers on later
starts. The first build downloads pinned
Python/npm dependencies and both pinned public models; allow sufficient disk,
memory and time. Runtime models are offline afterward; Gemini still needs network
access. TLS verification stays enabled. Builds use source-only allowlists so local
secrets, untracked backups and documents cannot enter their contexts.

A short-lived, network-disabled `setup` container validates the private settings,
generates a session secret and password hash, and saves them in a project-scoped
configuration volume. It exits successfully before the database/API/frontend start.
An exited setup container with code 0 is expected, not an application failure.
Passwords/keys are never printed. If setup fails, inspect `docker compose logs setup`;
do not delete volumes or old settings to force a reset. Application containers are non-root and can
read only their own settings; the frontend cannot read the Gemini key.

To stop and remove the containers while retaining configuration and documents:

```sh
docker compose down
```

The same `up` command starts them again using the saved configuration and index.
**Never add `-v`, prune volumes, or delete the Docker host disk.** These actions
can destroy both indexed documents and saved credentials. Keep `.env` intact and
matching the saved settings; changed credentials cause a safe startup rejection,
not a silent reset. Credential rotation and data migration are separate actions.

## Data and deployment boundaries

Fresh installs use Docker project `doclens-app` and new `index`, `snapshots` and
`app_config` volumes. They do not attach the old Mac `doclens` volumes. A different
project name is a different installation. Automatic setup refuses an existing
index without matching generated configuration; no ownership is inferred from
filenames and no data or credentials are adopted or overwritten.

Existing installations using `deploy/portable/.runtime` must retain their saved
configuration and `./start` / `./stop` or scoped `doclens` wrapper. Root automatic
setup is **not** an in-place migration of those installations. Do not delete old
settings to force startup or attach their original volumes to a new project.

Backend remains two CPUs / 1,536 MiB; frontend 512 MiB. Setup has a temporary
one-CPU / 128 MiB ceiling. Qdrant, Docker, builds and the host need additional
capacity. The earlier 4-vCPU/16-GB/30-GB planning estimates are not measured limits.
Limits stay 32 MiB / 300 pages with existing text/chunk/processing budgets.

Only the frontend binds loopback, normally port 3000; backend and Qdrant ports are
private. A public cloud deployment requires separately configured and tested
HTTPS/reverse proxy, DNS and firewall rules. Production session cookies are Secure;
a synthetic HTTP smoke that supplies its cookie is not proof of browser HTTPS
operation. The existing Caddy overlay remains for the legacy configured package;
root automatic HTTPS integration is not validated by this change. Do not publish
backend 8000 or Qdrant 6333/6334 to the Internet.

Keep original PDFs separately: the vector index is not an originals archive.
Stop services before database backups and preserve a matching private set of
`app_config`, `index`, `snapshots` and `.env`. Configuration backups contain
credentials and must not be shared as test artifacts. Test restoration into a new
empty project before relying on backups. Volumes survive containers, not host
loss; use persistent disks and private off-host backups for a cloud installation.
No automatic orphan deletion or original-data migration is introduced.

## Developers and existing installations

`build.py` and `configure.py` remain for hash-verified development builds and the
previous manually configured deployment format. They are not steps in normal
root Compose startup. Backend/frontend Docker definitions are shared; the root
Compose file adds only automatic private initialization.

See [testing](../../docs/TESTING.md) for startup validation and real synthetic
`down`/`up` persistence checks. Images are built locally, not registry-published.
This workflow does not authorize replacing an existing installation, admitting
customer data, deploying publicly or increasing resource/document limits.
