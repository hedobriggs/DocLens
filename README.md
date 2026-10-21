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

After a separately approved installation, `./start` starts this checkout's saved
project and `./stop` stops it while preserving credentials and document volumes.
First setup requires a private Gemini key and interactive login configuration;
see the installation guide. These launchers do not migrate another installation.

## Release status

This is a **release candidate**, not approval to deploy or replace an existing
installation. Linux amd64 Docker is the packaging target. Physical Intel Mac,
Safari, VoiceOver and whole-stack resource limits on an 8 GB Mac remain unverified.
See [cleanup scope and review](docs/CLEANUP.md) before consolidating into `main`.
Main's separate workspace/job/migration implementation must not be overwritten by
this candidate without a reviewed product-scope decision.

Use a fresh Docker project for synthetic validation. Never copy original volumes
or credentials into test fixtures. Runtime secrets, indexes, screenshots, logs and
personal backups do not belong in Git. Historical review artifacts remain
recoverable from Git history rather than duplicated in the current tree.
