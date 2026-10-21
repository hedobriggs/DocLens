# DockLens

Upload a PDF, ask questions, and receive Gemini answers with page citations.

## Start here

The portable Docker package in **[deploy/portable](deploy/portable/README.md)** is
this branch's supported deployment path. Docker Desktop/Engine must be running.
For first setup, create a private key file:

```sh
cp .env.example .env
chmod 600 .env
```

Edit `.env` privately and replace the placeholder with your Gemini API key.
Alternatively, supply `GEMINI_API_KEY` through your server's secret environment.
Do not put a real key in `.env.example` or commit it. Then run:

```sh
./start
```

First startup builds missing images and asks for email, password and password
confirmation. Later startups reuse the saved configuration without prompting.
Open the address printed when the app is ready (default http://127.0.0.1:3000).
If port 3000 is already occupied, use `./start --port 3001` on first setup.

To stop only this checkout's deployment, preserving documents and credentials:

```sh
./stop
```

Run these scripts from the repository root. They also work when invoked by
absolute path from another directory. An existing portable `.runtime` is reused;
the new scripts do not reset a forgotten password or migrate another installation.
For public servers with DNS/HTTPS, use the
**[advanced setup instructions](deploy/portable/README.md)**. No public ports or
TLS configuration are added by the simple local start command.

Python 3, Docker and Compose 2.30+ are required. Images target Linux amd64;
Apple Silicon and physical Mac validation remain outstanding. Images are not yet
published to Docker Hub.

This package contains application source with the latest branch UI, pinned to
`3a07c4d4fb1d4a395e4b483ae25ea09bf3e53c2d`, including recovery controls and bounded
complete-document answers. Upload limits remain **32 MiB and 300 pages**.
The package was tested with synthetic documents; see
[validation evidence and limitations](deploy/portable/VALIDATION.md).

## Other files

The root `docker-compose.yml` and backend/frontend Dockerfiles are earlier
Mac deployment definitions. Use the portable package above for this release.
The `recovery/`, `docs/` and `validation/` directories contain development tools
and historical evidence; they are not additional app versions to deploy.
They are excluded from the application build contexts.

This branch has not been merged into `main`. Main also contains a separate
platform implementation with workspaces, jobs and database migrations.
Replacing main with this tree would remove that implementation and requires an
explicit scope decision. See [the consolidation proposal](deploy/portable/CONSOLIDATION.md).

Keep existing Mac files and Docker volumes unchanged. Configure a fresh project
and retain backups before any migration. Do not commit credentials or customer data.
