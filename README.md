# DockLens

Upload a PDF, ask questions, and receive Gemini answers with page citations.

## Start here

The portable Docker package in **[deploy/portable](deploy/portable/README.md)** is
this branch's supported deployment path. Follow **[the quickstart](deploy/portable/QUICKSTART.md)**.
Build the images from this checkout with:

```sh
python3 deploy/portable/build.py
```

Then follow the quickstart to configure private credentials and start the services.
Python 3, Docker and Compose 2.30+ are required. Images target Linux amd64;
Apple Silicon and physical Mac validation remain outstanding. Images are not yet
published to Docker Hub.

This package contains application source pinned to
`66db29f0b072fd9821869f4ffef008883ce0509b`, including recovery controls and bounded
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
