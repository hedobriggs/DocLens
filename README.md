# DocLens

Ask questions about text-based PDFs and receive answers with document/page
citations. DocLens runs a Next.js frontend, a Python API and Qdrant using Docker.

**[Installation and operation](deploy/portable/README.md)** ·
[Architecture](docs/ARCHITECTURE.md) · [Testing](docs/TESTING.md)

## Repository

- `frontend/` — login, document upload and question workspace.
- `backend/` — bounded PDF processing, retrieval, Gemini answers and citations.
- `deploy/portable/` — the single supported Docker package and synthetic smoke test.
- `tests/` — upload/recovery, coverage, browser and publication regressions.
- `docs/` — architecture, test instructions and the current cleanup review.

The legal-workspace UI and reviewed complete-document answer path are included.
Uploads remain limited to **32 MiB / 300 pages**, with additional extracted-text,
chunk and processing-time bounds. Scanned PDFs require OCR, which is not provided.
Questions and retrieved text are sent to Google Gemini. Verify generated answers
against your original documents; keep source PDFs outside the vector index.

## Start and stop

In a clean checkout, copy `.env.example` to a private `.env` (mode 0600) without
overwriting an existing file. Set your Gemini key, administrator email and password.
Then:

```sh
docker compose up -d --wait
```

Docker builds the current images using cached layers and performs private first-time setup automatically.
**No host Python/Node installation or manual build/configuration commands.**

Stop with:

```sh
docker compose down
```

Documents and saved settings survive normal down/up. **Never add `-v`.** New
installs use separate project-scoped volumes; old Mac data is not migrated or
attached. See the installation guide for existing installations, resource bounds,
private settings and cloud HTTPS requirements.

## Release status

This is a **release candidate**, not approval to deploy or replace an existing
installation. Linux amd64 Docker is the packaging target. Physical Intel Mac,
Safari, VoiceOver and whole-stack resource limits on an 8 GB Mac remain unverified.
The default product is this PDF upload-and-question application. The earlier
workspace/job/migration implementation is preserved on
[`archive/platform-milestone-2`](https://github.com/hedobriggs/DocLens/tree/archive/platform-milestone-2).
Its retirement from the default tree was explicitly authorized; no databases,
original documents or running installations were migrated or deleted.
See [cleanup scope and verification](docs/CLEANUP.md).

Use a fresh Docker project for synthetic validation. Never copy original volumes
or credentials into test fixtures. Runtime secrets, indexes, screenshots, logs and
personal backups do not belong in Git. Historical review artifacts remain
recoverable from Git history rather than duplicated in the current tree.

RunPod Pods use a separate [single-container template](deploy/runpod/README.md)
(no nested Docker). The template candidate requires image publication and actual
RunPod validation before use. Macs and ordinary cloud VMs continue using Compose.

Optional [Prometheus and Grafana monitoring](deploy/monitoring/README.md) is
available through the DocLens login. Compose uses the monitoring overlay; the
RunPod candidate includes it in the single container. This candidate requires
independent review and the documented remaining deployment checks.
