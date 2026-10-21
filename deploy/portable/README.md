# Portable DocLens deployment

This is a new deployment package for approved application commit
`66db29f0b072fd9821869f4ffef008883ce0509b`, matching the source installed on the
RunPod trial. It is built from source, not a capture of that Pod. No credentials,
CVs, uploaded documents, database contents or original Mac files are included.
Application source, requirements and lockfile are unchanged.

## What is packaged

- Frontend image: Node 22.23.3, locked Next.js/React dependencies, compiled app.
- Backend image: Python 3.11, CPU-only PyTorch 2.2.2, pinned dependencies, both
  pinned embedding/reranking models. Models operate offline at runtime.
- Official Qdrant 1.15.5, pinned by digest, with project-specific persistent
  `index` and `snapshots` named volumes.
- Standalone Compose configuration: no original fixed container names, no
  published database/backend ports, health checks, restart policies, non-root
  application containers and the reviewed per-service memory/CPU controls.
- Optional Caddy HTTPS proxy with persistent certificates.

This is a three-service application, not one monolithic container. Target:
Linux **amd64**, Docker Engine/Desktop and Compose **2.30+**. Intel Macs can use
Docker Desktop Linux containers; native Mac acceptance remains untested. ARM
servers/Apple Silicon would require emulation (untested) or a separately validated
ARM build because the CPU wheel/model stack is pinned. A Docker-capable VPS/VM is
supported; an ordinary RunPod Pod does **not** automatically support nested
Docker/Compose. Keep the working native RunPod trial separate.

Start with 4 vCPU, 16 GB RAM and at least 30 GB free disk for builds/images/data.
These are planning estimates, not measured whole-stack peak requirements. The
backend retains 2 CPUs / 1536 MiB, frontend 512 MiB. Qdrant, Docker and the host
need additional capacity. Test representative data before increasing limits.

## Quick start on a NEW deployment

Use a separate directory and a fresh project. Do not run the repository's old
`docker-compose.yml`, copy existing Mac volumes, or combine it with this file.
Do not deploy on top of your RunPod installation or existing Mac checkout.

From the unpacked repository root, build (requires Internet):

```sh
python3 deploy/portable/build.py
```

The builder checks every backend/frontend file against
`application-manifest.json`, rejects changed/symlink files, and copies only those
approved files into temporary contexts. Local secrets, untracked backups and
indexes cannot enter those contexts. Base image digests, npm lockfile, Python
requirements, PyTorch CPU version and model revisions are pinned. A fully
bit-for-bit reproducible image is not promised: package indexes, build tools and
TLS trust can evolve; record resulting image IDs and inventories.

Alternatively, load the supplied custom-image archive (verify its SHA256 first):

```sh
gzip -dc DocLens-portable-linux-amd64-images.tar.gz | docker image load
```

Pull official Qdrant and initialize private runtime files:

```sh
docker pull qdrant/qdrant:v1.15.5@sha256:0fb8897412abc81d1c0430a899b9a81eb8328aa634e7242d1bc804c1fe8fe863
cd deploy/portable
python3 configure.py --domain doclens.YOUR-DOMAIN.example
```

Replace the hostname with your real DNS name. The initializer asks privately for
an admin email, 12+ character password (max 72 UTF-8 bytes), and Gemini key. It
generates a shared session secret and bcrypt hash. Files under `.runtime` have
mode 0600 and their directory 0700; it refuses overwriting an existing deployment.
The Gemini key goes only to the backend; the frontend receives the session secret,
admin email and password hash. Nothing secret is a build argument or image layer.
Compose's `raw` env-file mode preserves bcrypt dollar signs. Docker administrators
can inspect container environment values; use a managed secret integration for
your organization's requirements. Never share `docker compose config` output,
runtime env files, full inspect data, cookies or credentials.

Start with HTTPS (DNS A record to this server; allow inbound TCP 80 and 443):

```sh
./doclens --https up -d --no-build --wait --wait-timeout 180
./doclens --https ps
```

Caddy obtains a public certificate automatically; open `https://YOUR-DOMAIN` and
log in. Use `--https` consistently for status/stop/down when Caddy is enabled.
Certificates and Qdrant data survive container replacement through named volumes.
External DNS/ACME/firewall configuration is site-specific and is not certified by
the local package test. Do not publish 6333, 6334 or 8000. Frontend 3000 binds
loopback by default; Caddy accesses it over the project network. Keep SSH and
Docker access restricted. No global firewall configuration is modified here.

For a local trial without a domain, omit `--domain` and `--https`:

```sh
python3 configure.py
./doclens up -d --no-build --wait --wait-timeout 180
```

Access via a local HTTPS reverse proxy. The app uses Secure session cookies in
production. Do not assume remote plain HTTP or an HTTP SSH tunnel will support a
browser session; prefer HTTPS. The local synthetic smoke explicitly supplies its
test cookie to exercise the gateway and is not a public HTTP deployment pattern.

### Credential-free synthetic test

For a fresh synthetic project only, substitute this initializer (dummy Gemini
key; no live answers):

```sh
python3 configure.py --synthetic-test --port 0
./doclens up -d --no-build --wait --wait-timeout 180
python3 smoke.py --restart
```

The smoke tests anonymous denial, signed login, a real five-page PDF with five
employers, actual embedding/indexing, invalid/page-limit replacement preservation,
and restart persistence of points/payloads/publication metadata. It writes only
`portable-synthetic.pdf`; repeat runs retain old revisions as the app normally
does. It does not send a request to Gemini. For a separately configured real-key
project, `python3 smoke.py --live-answers --restart` sends only synthetic context
to Gemini and checks all five names and page citations. Provider latency,
availability and completeness vary. Never use customer data for acceptance tests.

## Stop, restart, logs and persistence

```sh
./doclens ps
./doclens logs --tail 50 backend frontend qdrant
./doclens stop
./doclens start
```

For TLS deployments use `./doclens --https` instead. Stopping/recreating
containers is safe for the named data volumes. **Do not use `down -v`, volume
prune, or delete the Docker host disk** if you want the index retained. Volumes
survive containers, not host destruction; host-attached persistent disks and
off-host backups are required for durable cloud operation. Model files are in
the backend image, so no first-boot downloads are necessary. Never commit
`.runtime`; session-secret rotation invalidates active sessions.

The app preserves 32 MiB / 300-page uploads and text/chunk/time budgets. More
server RAM does not remove these enforcement limits. Comprehensive answers are
bounded to 120,000 context characters / 1,500 chunks. Originals are not a managed
document archive; keep source PDFs outside the index. Retired vector revisions
remain stored; no garbage collection or data migration is introduced.

## Offline backup and fresh-project restore

Keep configuration/secrets separately and privately; database backup alone cannot
restore login credentials. Never include credentials in a shared evidence ZIP.
Example while in this package directory; each command must succeed:

```sh
set -eu
backup=$(mktemp -d "$HOME/doclens-backup.XXXXXX")
./doclens stop
cid=$(./doclens ps -aq qdrant)
test -n "$cid"
docker cp "$cid:/qdrant/storage" "$backup/storage"
docker cp "$cid:/qdrant/snapshots" "$backup/snapshots"
tar -czf "$backup/index.tar.gz" -C "$backup" storage snapshots
tar -tzf "$backup/index.tar.gz" >/dev/null
./doclens start
```

For TLS use the `--https` wrapper; also preserve that project's certificate data
or let Caddy obtain fresh certificates subject to ACME limits. A readable archive
is not proof of restore: test on a **new empty project** before relying on it.
In a separately unpacked copy, configure a new project, `./doclens create --no-build qdrant`, then
copy the trusted backup's `storage/.` and `snapshots/.` to the stopped Qdrant
container at `/qdrant/storage` and `/qdrant/snapshots`, and start with
`./doclens up -d --no-build --wait --wait-timeout 180`. Do not merge files into
an existing index, mount original Mac volumes, or extract an untrusted archive.

## Enterprise proxy trust

Normal builds use system public CAs. If an authorized HTTPS proxy requires a
custom trust bundle, pass its absolute PEM path via `BUILD_CA_BUNDLE` to
`build.py`. BuildKit mounts it only for networked build steps; verification stays
enabled and the bundle is not copied into the runtime image. Runtime proxy CA
configuration, when required, must be mounted read-only separately with
`SSL_CERT_FILE`/`REQUESTS_CA_BUNDLE` on the backend. Never disable TLS checks.

## Distribution and rollout

Custom images are built locally, not published to a registry by this task. Save
or push them to your own authorized registry, pin deployment image references to
the resulting digests, and use `configure.py --backend-image ... --frontend-image
...` on each new server. Pull the official Qdrant/Caddy digests separately.
Keep Python 3, Docker/Compose, DNS/HTTPS and persistent disk configuration with
the release. For Kubernetes/ECS/etc., preserve the private DNS names `backend`
and `qdrant`, volume semantics and secret separation; those platforms are not
automatically configured by this Compose bundle.

Read `VALIDATION.md` for actual checks and limitations. A package smoke pass does
not authorize replacing the user's original Mac installation or migrating its
data. The running native RunPod environment was not accessed or modified.
