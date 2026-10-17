# Mac local update — reviewed upload fix only

Apply application code from **76b81c1bf5a23fd62e344e893b1bff45e24e8cb4**.
Do this in your existing Mac checkout, while nobody is uploading and no editor
or other process is changing its files. This is one procedure with three gated
phases. Stop at the first failure. Do not retry your document until every phase,
including the browser check, passes.

This helper is operational tooling; it is separate from the approved application
commit. It applies an explicit list of ten files from that exact commit, with no
merge, cherry-pick, reset, stash, clean, or source commit. It leaves `main` alone
and creates a local `local/mac-reviewed-*` branch. Your modified generation/login
files, untracked files, backups, and credentials remain in place. New processing
modules remain untracked until you later choose how to commit your local work.

Prerequisites: Python 3.8+, Git, running Docker Desktop with Compose v2, the
existing `doclens-backend`, `doclens-frontend`, and `doclens-qdrant` containers,
and substantial free disk space on both the Mac backup disk and Docker Desktop.
The complete checkout (including `.git`, ignored files, dependencies, and secrets)
and a cold copy of Qdrant storage can be large. Qdrant WAL files may be sparse;
`docker cp` can require their full logical size. The helper checks that size
when Qdrant is running and requires an additional 2 GiB reserve; builds can need
more. Keep the backup private and do not upload it to GitHub or a review chat.

## 1. Back up, verify the starting files, and prepare the local branch

In Terminal, `cd` to your existing DocLens checkout. Run this block:

```sh
git fetch origin ops/mac-reviewed-update-76b81c1 &&
DOC_UPDATE_HELPER="$(mktemp "${TMPDIR:-/tmp}/doclens-safe-update.XXXXXX")" &&
git show FETCH_HEAD:recovery/mac-upload/safe_update.py > "$DOC_UPDATE_HELPER" &&
DOC_UPDATE_BACKUP="$(dirname "$PWD")/DocLens-backup-$(date +%Y%m%d-%H%M%S)" &&
python3 "$DOC_UPDATE_HELPER" prepare --backup "$DOC_UPDATE_BACKUP"
```

The first operation in `prepare` creates `checkout.tgz` in a new private backup
directory outside the checkout. It then requires `HEAD` to be the Mac baseline
`e800f34018474c411ba609654c13ccf4d59cb05f` and byte-checks **every tracked file**:

- The eight uploaded files must match your preserved Mac versions.
- `backend/main.py` may instead match the approved indentation-only patch.
- All other tracked files must match the original baseline.
- New processing-module paths must have no untracked collision or symlink.

If the check fails, it lists paths, applies nothing, and does not stop containers.
Keep the backup and report the filenames plus `git rev-parse HEAD` and
`git status --short`. Do not normalize or discard differences to make it pass.
The helper does not require untracked backups/scripts to be supplied or removed.

After that check, the helper checks Compose project/service labels and the exact
existing Qdrant volume, saves backend/frontend images under backup tags, stops
backend/frontend first and Qdrant second, and copies `/qdrant/storage` while it
is stopped. It hashes the copied files, rechecks the starting source, creates
the local branch, and applies only the reviewed application files. It never
creates, resets, deletes, or migrates a Qdrant volume. The backup includes:

- `checkout.tgz`: full original checkout, including credentials and local work;
- `root-env.private` / `backend-env.private`: resolved copies of the two Compose
  credential files, including targets if the originals are external symlinks;
- `qdrant-storage/` and `qdrant-backup-sha256.json`: cold storage copy and hashes;
- `state.json`: original image IDs/tags, volume/project identity, reviewed hashes;
- `update-helper.py`: a retained copy of the helper for the next phases.

Success ends with `PASS: selective reviewed files applied...`. Containers remain
stopped. Keep the displayed backup path; it is needed below. If you open a new
Terminal, set `DOC_UPDATE_BACKUP` to that same absolute path before continuing.

## 2. Rebuild and start only the application services

Only after phase 1 passes:

```sh
python3 "$DOC_UPDATE_BACKUP/update-helper.py" rebuild --backup "$DOC_UPDATE_BACKUP"
```

This verifies the reviewed source hashes, local branch, Compose project, and
volume again. It builds backend/frontend using your existing Dockerfiles and
credentials, starts the **existing** Qdrant container, then recreates only
backend/frontend using `--no-deps --no-build`. It does not pull/recreate Qdrant,
run `compose down`, or modify monitoring services. Build/start evidence stays
in private `build.log` and `startup.log` in the backup directory.

A failure stops the procedure. Keep existing volumes, images, and backups. Read
the private log locally and share only a redacted error; do not post `.env`,
`checkout.tgz`, `state.json`, or complete build logs without checking for secrets.
Do not restart the old application against newly published revisions as an
automatic rollback: old readers do not understand revision visibility filters.

## 3. Verify backend startup, dense synthetic upload, and the browser

Only after phase 2 passes:

```sh
python3 "$DOC_UPDATE_BACKUP/update-helper.py" verify --backup "$DOC_UPDATE_BACKUP"
```

This uses the existing internal credential **inside the container**, without
printing or writing it to a request file. It checks readiness, generates a real
40-page PDF with over 200,000 extracted characters, uploads it, samples API health
and backend RSS, checks the total point count increased only by its new chunks,
and rejects an invalid replacement without changing the synthetic document's
visible point IDs. The synthetic document intentionally remains indexed; no
cleanup or deletion runs. It does not call hosted generation.

Require a `PASS` result and `health_failures: 0`.
`synthetic-verification.json` records measurements; the PDF is copied into the
backup directory with a unique `doclens-synthetic-*.pdf` name. This verifies a
synthetic ingestion, not a byte-for-byte comparison of the whole original index.
The cold backup protects the original data; prior regression tests cover exact
point-ID retention on failed replacements.

Then complete these browser checks **before your document**:

1. Open `http://localhost:3000` and sign in using your existing credentials.
2. Upload that `doclens-synthetic-*.pdf` from the backup directory. Require
   **Ready**, no timeout, and an enabled upload control afterward. Replacing this
   synthetic document is intentional; do not select an existing customer PDF.
3. Upload `doclens-invalid-synthetic.pdf` from the same directory. Require a clear
   error, the synthetic document still Ready, and the busy state cleared. Upload
   the valid synthetic PDF again to confirm recovery.
4. During processing, inspect `docker stats --no-stream`; after completion run
   `curl --fail http://localhost:8000/` and require the running-API JSON response.

Report the verification JSON, the three browser outcomes, and any redacted
component error. Once those pass, retry your document. The enforced limits are
32 MiB, 300 pages, 100,000 characters/page, 1,000,000 characters total, and 1,500
chunks. A document that exceeds them should produce a clear rejection, not remain
busy. The processing budget is 90 seconds with cooperative cancellation; native
work can finish its current batch after cancellation while admission stays held.
The frontend gateway has a 120-second absolute deadline and the UI a 135-second
deadline. None of these limits were extended to hide the original freeze.

## Remaining validation blockers and scope

The cloud has no access to your Mac. Its current file hashes, cold backup, native
ARM image build, model download, Docker Desktop limits, startup, actual browser
login/gateway behavior, and original PDF remain **unverified until this procedure
runs there**. In particular, earlier cloud image validation reused cached CPU
packages; it did not prove a fresh build from your Mac Dockerfiles. Build/network
or platform failures must be resolved rather than counted as passed. Python/Git/
Docker access and disk space are prerequisites; the helper stops rather than
rewriting configuration to work around them.

The reviewed app's cloud validation limits still apply: single API process,
cooperative cancellation, retained historical/staged points, and no global
storage quota or destructive cleanup. This procedure adds no migrations, cleanup,
production deployment, customer-data admission service, or merge into `main`.
Testing your own document locally is deferred until the synthetic checks pass.

## Preparation evidence (cloud; does not replace the Mac checks)

`validation/mac-safe-update/` records seven passing helper tests using real Git
checkouts and controlled Docker lifecycle calls, plus a passing real-container
cold-backup/apply/startup/upload check. The latter used reviewed source mounted
read-only in the previously validated CPU dependency image, a cached model,
2 CPUs and 1.5 GiB backend memory. It indexed 217,800 characters/280 chunks in
9.16 seconds, with 89 successful health probes, zero probe failures, and
787,720 KiB peak backend RSS. An existing synthetic original point survived and
an invalid replacement preserved the synthetic publication. This was not a new
Dockerfile build or a Mac browser check. All fixtures were synthetic and removed
from the test runtime after evidence collection; no existing volume was touched.

The first real-container attempt ran out of cloud disk space because Docker's
`vfs` driver copies full root filesystems for each container. A second attempt
was interrupted while waiting on a stale random published port after Qdrant
restart. The passing run used small dummy application containers for the backup
phase, a smaller synthetic-only WAL configuration, and re-read the random port
after restart. Those fixture changes are not applied to your Qdrant. An initial
helper-test fixture also tried to switch commits over modified files; its Git
ref setup was corrected, and all seven tests then passed.

Reproduce helper checks in a development/test environment:

```sh
python tests/test_mac_safe_update.py
HF_HOME=/path/to/verified/model-cache python tests/mac_safe_update_smoke.py
```

The smoke refuses existing application container names and is for an isolated
cloud test machine only, not for running in your live Mac checkout. Use the three
phases above on the Mac. The rebuild command selection and its failure gate are
regression-tested with controlled Docker calls; the actual fresh Mac build is
still pending. The helper invokes the explicit reviewed Compose file, preserving
the detected project name and refusing a different data volume.
