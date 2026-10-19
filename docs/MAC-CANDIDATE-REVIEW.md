# Separate Mac UI candidate — independent review

Repository/ref: `hedobriggs/DocLens`, `refs/heads/candidate/mac-reviewed-ui`.
Parent: previously reviewed Mac UI `d0980c6c5ea07032cc5c060ff726b8042c9bef51`, itself based on reviewed Mac application `76b81c1bf5a23fd62e344e893b1bff45e24e8cb4`.
UI improvements adapted from approved `02815cccb0371faa791d55bab0c09991e3aa6a44`. This does not merge platform main or its backend into the Mac recovery application. Main remains31eb3455cd5dc02c47f343d62328d41c8a2c3458; this candidate is unmerged and not deployed.

## What changes and what is preserved

Only two product files change from the Mac UI parent: dashboard page and CSS. Port long-filename wrapping, shrinkable toolbar/citations, non-clipping question placeholder, and public hydration readiness before enabling Upload. Retain the Mac UI's pending filename, honest status, secondary Cancel button, limits disclosure, improved contrast/focus, sidebar purpose, local file size, expandable source references and Gemini disclosure.

Do **not** import main's50MiB limit, unsupported-cancellation behavior, Monitoring navigation, platform API or migrations. Backend, frontend API/auth routes, package/lock files, original Dockerfiles/Compose, Next config and existing recovery files are byte-identical to the Mac UI parent: [26-file preservation manifest](../validation/mac-ui-candidate/preservation.json). The public model mount is narrowed to one model's cached files, excluding any wider cache/token files.

Preserved controls:32MiB PDF,300pages,1,000,000 extracted characters,100,000 characters/page,1,500chunks; transfer15s, processing90s, frontend gateway120s, browser135s. One upload worker, two inference threads/CPU quota2, backend1536MiB with equal memory+swap ceiling, frontend512MiB with equal memory+swap ceiling. Qdrant remains1.15.5. Publication, cancellation and search-revision fencing code are unchanged. No data migration or cleanup policy changes are introduced.

This is based on the preserved reviewed Mac application, **not a claim that the currently running Mac has already received it**. The paused frontend recovery helper is not imported or executed. Original Mac checkout, backups, credentials, images and volumes were not accessed or changed; the Mac is not connected to this cloud fixture.

## Container isolation

`recovery/mac-ui-candidate/compose.yml` is a standalone fixture, not an override for the original Compose file. The runner:

- Uses an unpredictable `doclens-ui-candidate-…` project and refuses existing project containers/networks before startup. No fixed original container names or original ports are used.
- Binds ephemeral ports to127.0.0.1 only. Docker changes them on restart, so the runner discovers them again. It never joins an original application's network.
- Creates new empty Qdrant storage/snapshot directories inside its private temporary directory, uses the invoking UID for their ownership, and never mounts any existing Docker data volume. The final directory locations use the managed executor's separate temporary filesystem because Docker's VFS root had insufficient WAL headroom.
- Uses synthetic credentials in mode0600 files under a mode0700 private directory. Explicit Compose `--env-file` avoids implicit original.env loading; raw service env-file mode preserves bcrypt dollar signs. No original credentials or full container inspection data are exported.
- Mounts only a curated backend source snapshot and a specific public model directory, both read-only. Frontend runs a separately built candidate image, with no original checkout mount. Context preparation copies tracked frontend files only, excludes.env files and untracked backups, and refuses symlinks.
- Tears down only its own project and generated private directories. Final before/after inventories confirm original local container IDs and Docker volume names are unchanged. No existing image/cache was pruned. Candidate-generated npm/Next build caches were moved to temporary storage to preserve Docker-root headroom.

This is project/storage isolation, not an egress firewall. The build fetches verified public dependencies/fonts. Runtime uses offline local embeddings and a dummy Gemini key; tests do not invoke hosted generation. Prometheus/Grafana/original monitoring volumes are not started or mounted by this three-service fixture.

## Reproduction prerequisites and commands

Cloud-tested on Linux x86_64, Docker28.4/VFS, Compose2.40.3, Node20.20.2/npm11.9 in the candidate frontend image; native browser harness uses Node24.19, Playwright1.64.1 and Chromium154. Compose raw env files require a recent compatible Compose version (2.30+).

Prerequisites: a compatible local Docker socket, locked frontend dependencies, Python with requests/PyMuPDF/test dependencies, a cached public all-MiniLM-L6-v2 model, and the separately available reviewed backend dependency image. The helper defaults to `doclens-mac-upload-freeze:review`; its tested immutable ID is in the report. That dependency image is not published by this task and may need to be built separately in another environment. Source is mounted read-only over it. Do not substitute a running Mac image or retag an original image without separate review.

Build from a fresh context, never an original checkout's untracked contents:

```sh
python recovery/mac-ui-candidate/prepare.py /tmp/doclens-candidate-context
BUILDX_CONFIG=/tmp/doclens-candidate-buildx docker build \
  --secret id=proxy_ca,src="$CODEX_PROXY_CERT" \
  --secret id=system_ca,src=/etc/ssl/certs/ca-certificates.crt \
  -t doclens-mac-ui-candidate:review /tmp/doclens-candidate-context
npm run build --prefix frontend
npm run lint --prefix frontend
node tests/mac_candidate_ui.cjs after /tmp/doclens-candidate-ui
node tests/mac_candidate_keyboard.cjs /tmp/doclens-candidate-keys-1
node tests/mac_candidate_keyboard.cjs /tmp/doclens-candidate-keys-2
backend/.venv/bin/python -m unittest discover -s tests -p test_mac_upload_limits.py
backend/.venv/bin/python -m unittest discover -s tests -p test_mac_publication_server.py
node tests/mac_upload_browser.cjs fixed frontend /tmp/doclens-candidate-gateway
DOCLENS_CANDIDATE_EVIDENCE=/tmp/doclens-candidate-stack \
  HF_HOME=/path/to/public/huggingface-cache \
  backend/.venv/bin/python tests/mac_candidate_stack.py
```

The Docker build uses secret-mounted configured CA trust with strict TLS checks. Pinning npm11 avoids the stalled npm10 lockfile-install path observed here; the application package/lock files remain unchanged. Combined CA trust allows Turbopack to fetch fonts. No CA secret file is copied into image layers. These are managed-Linux reproduction commands, **not instructions to install on the original Mac**. Do not combine the candidate fixture with the original Compose file.

## Passing evidence

[All evidence](../validation/mac-ui-candidate/), including failed/interrupted runs and subsequent passes:

- Locked native dependency install, build and lint passed. The built image's dashboard/CSS hashes match the candidate source, and the context-preparation helper reproduced the actual build context byte-for-byte.
- Native dashboard:14 screenshots,16 geometry checks at1280×800 and1440×900 including spaced and unbroken long names;491 contrast samples, zero failures. No fake progress/stages or original-page viewer is added.
- Two keyboard runs:20 fresh contexts each,40/40 passed, including four controlled hydration cases. Early chooser observation and public enabled/focus conditions are used; no private React fields or arbitrary action delays.
-13 bounded-upload/search/publication local regressions and3 actual Qdrant-server publication/reconciliation regressions passed. These cover existing-view retention, legacy citations, cancellation/worker admission and search races; inference is controlled in these tests.
- All12 existing gateway recovery cases passed, including cancellation and virtual135s browser deadline. The actual absolute gateway deadline returned504 after120.012s despite response trickle, and disconnect closed upstream.28MiB synthetic transfer also passed. This is distinct from the actual-model container test.
- Actual Node20 frontend, backend and Qdrant containers passed synthetic login, anonymous-upload denial, PDF upload, dense ingestion, actual browser keyboard picker/upload, and full-service restart checks. Final [stack report](../validation/mac-ui-candidate/stack-final/stack-results.json) records exact image IDs, configured caps, loopback endpoints/mount types and results.
- Final dense PDF:32pages,12,680,928bytes,174,240 searchable characters plus unique seeded images,224chunks. No padding. Actual-model upload through the frontend took8.304s;80 health probes succeeded, zero timeouts, maximum17.7ms. Dataset SHA, method, cloud hardware and model revision are recorded. This measures this fixture on cloud AMD EPYC, **not the Intel Mac**.
- Invalid replacement400 and page-limit413 preserved preexisting synthetic point IDs. Restarting all three services preserved all point IDs, original citation identity and publication catalog. Only completed indexed revisions were checked across restart; this does not introduce durable in-flight jobs.

The frontend image is `sha256:cf241ebaede03f9bc43feb4c686834baf139833b70e1842dbc55627378c9cffb`. Backend dependency image is `sha256:240bdd1bc9ca5ade1cbaea15823e39ad2f6d08ee41f19a4f52f4f1d2b2004153`. Public embedding model revision is1110a243fdf4706b3f48f1d95db1a4f5529b4d41. Resource evidence asserts Docker's configured caps; no whole-stack peak-memory or physical-Mac thermal/latency certification is claimed.

## Failures and corrective reruns

- Temporary `/tmp` test interpreter was gone: initial unit command did not run. Persistent backend venv rerun passed13 tests; server suite passed3.
- Three npm10 container installs were manually interrupted while optional-dependency reification stalled. They are not counted as passes, nor asserted to prove a general npm10 defect. Pinned npm11 install completed.
- Initial npm11 container build failed Google-font fetching. Secret-mounted combined system trust/Turbopack system-TLS retry passed; verification was never disabled.
- Initial isolated `internal` Docker network did not publish host ports. A minimal probe reproduced absent port mappings. Separate ordinary project bridge plus loopback-only publication corrected the fixture.
- First writable named-volume run reached indexing but Qdrant refused the WAL due to Docker-root free space, returning500/backend503. No application fix or limit change was made: fresh synthetic data was moved to the separate temporary filesystem.
- A later full upload/browser run passed but restart readiness waited on stale ephemeral ports. It was interrupted and cleaned up. The runner now rediscovers ports after restart; two complete later runs passed, the final one with the narrowed public-model mount.

No failed run is omitted or reclassified as an application pass. Generated private env files and raw credential-bearing inspection data are excluded from the package.

## Approval and coverage boundaries

**Physical MacBook Air, native macOS Docker Desktop, Safari and VoiceOver: not tested.** Browser viewports are representative CSS sizes, scale1, not confirmation of actual Mac display scaling. No customer PDF/data, original dataset import, migration, deletion, main merge or deployment is authorized/performed. The actual32-page PDF/page-count discrepancy remains a separate investigation; synthetic success does not resolve it.

This candidate is for independent review. It does not authorize replacing the original Mac checkout, running the paused recovery helper, or attaching candidate services to original volumes. Any later Mac trial needs its own source/backup checks and separate candidate location/storage; no such Mac action has been performed here.
