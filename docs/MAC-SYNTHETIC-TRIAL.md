# Separate Mac synthetic trial: corrected procedure, pending independent review

**Do not use the nine pasted shell blocks from commit `2eadf4ad8b2cb0c851be68739afc9725b0ef27e6`.** They were unsafe: failed cloning or directory changes did not automatically stop later commands, including checkout in the original directory. Shell syntax checks passed but did not establish execution safety.

Application approvals are unchanged. The comprehensive-answer application commit is `66db29f0b072fd9821869f4ffef008883ce0509b`; UI source is `02815cccb0371faa791d55bab0c09991e3aa6a44`. The corrected trial procedure requires its own independent review before execution. It is not a Mac update procedure and does not authorize replacing the original installation.

## Corrected execution boundary

The procedure is now one executable script: `recovery/mac-ui-candidate/mac-synthetic-trial.sh`. Run it with Bash; never source it or paste its contents into an interactive shell. It uses `set -Eeuo pipefail` and an error trap that preserves the failing status. No later stage runs after a failed prerequisite, clone, directory change, assertion, build, trial or evidence check. A failed clone does not perform checkout.

Before checkout, the script verifies that it is in the freshly created source repository and that the exact approved commit object exists. Before dependency installation and trial execution, it verifies that directory, HEAD SHA and tracked-file cleanliness again. It refuses execution when sourced. Command substitutions that matter are checked rather than hidden behind successful `export` commands. The final evidence assertion retains a failing exit status.

The script accepts one local Git bundle path. The bundle must contain commit `66db29f0b072fd9821869f4ffef008883ce0509b`; **the older af535-only bundle does not satisfy this prerequisite**. Team Codex must provide the updated bundle alongside the reviewed procedure. The bundle is checked, cloned with `--no-checkout` into a new private `~/DocLens-synthetic-trial.XXXXXX/source` directory, then the exact application commit is selected. Neither original files nor original volumes are input.

## Prerequisites, dependency image and resource stop conditions

Intel Mac; Docker Desktop Linux containers; Compose 2.30+; Python 3.11; Node 20.9+ (20 recommended); npm; Git; a macOS version supported by bundled Playwright Chromium. The runner requires local `unix:///var/run/docker.sock`. If Docker Desktop uses a different socket or a remote daemon, stop; do not switch daemons or create symlinks as a workaround.

The cloud-only backend image `doclens-mac-upload-freeze:review` is not presumed available. The script builds a fresh CPU-only Python dependency image from the exact candidate requirements (`torch==2.2.2+cpu`, then pinned requirements and `pip check`). It records the resulting image ID and dependency inventory. The Python base tag is not digest pinned, so this remains a fresh dependency build requiring its own passing evidence. It builds a separately tagged frontend with locked npm dependencies and normal verified public CA trust, not the cloud-specific CA secrets. Do not disable TLS verification to resolve build failures.

It downloads only public `sentence-transformers/all-MiniLM-L6-v2` revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41` into a new trial cache. No original Hugging Face cache or token is mounted. Trial runtime is offline for models, uses synthetic credentials and does not exercise Gemini. No AWS, Gemini or Hugging Face account credentials are needed for this trial.

Before confirming the resource prompt, check Activity Monitor and Docker Desktop. Backend retains 1.5 GiB memory / two CPU caps, frontend 512 MiB; Qdrant, browser, Docker, builds and original services need additional memory. On an 8 GB Mac / ~3.82 GiB Docker VM, concurrent execution may be unsuitable. Stop if pressure is yellow/red, swap is growing, free disk/headroom is insufficient or uncertain. Do not stop original services, change Docker allocation, prune images, raise upload limits or modify resource controls to make the trial fit. The resource confirmation is a human checkpoint, not automated proof of capacity.

## Run only after the corrected procedure is independently approved

Obtain the reviewed script and updated bundle as separate downloads outside your original checkout. Verify the script's SHA-256 against the exact review handoff before execution; on macOS use `shasum -a 256 /absolute/path/to/mac-synthetic-trial.sh`. Execute the downloaded script directly with its bundle argument using `bash /absolute/path/to/mac-synthetic-trial.sh /absolute/path/to/current-candidate.bundle`. These commands never need you to enter or modify the original checkout. Do not resume a failed partial script by pasting later lines; keep its directory/logs and report the failure.

The script starts a random isolated Compose project, loopback-only random ports and fresh private synthetic Qdrant storage. No original named volumes or original image tags are attached. It runs real synthetic PDF ingestion/indexing, authentication, failed-replacement preservation, page-limit rejection, a dense 32-page ~12.7 MB PDF, API responsiveness, headless Chromium keyboard/upload and restart identity checks. It tears down only its own project and synthetic private storage; it is not a persistent preview. Do not supply private/customer PDFs.

Success requires the script itself to exit zero, final evidence assertions to pass and no unexplained errors/OOM/restarts. Preserve all failed attempts and later passes separately. Share only reviewed build/model/trial logs, image IDs, dependency inventory, stack-results JSON, container-browser log and screenshot. Do not share env files, cookies, credentials, full container metadata, original documents or captured filesystems.

If interrupted, keep the logs and random project name and request scoped cleanup; never run global prune or original Compose commands. Failure teardown limitations in the existing runner still apply. Passing does not authorize installing the candidate over your original application.

## Safety tests and remaining limits

Run `backend/.venv/bin/python tests/test_mac_trial_safety.py`. Six passing execution tests cover missing bundle, failed clone (preserves status 73), successful clone command with missing destination (failed `cd`), wrong commit assertion before checkout, failed commit lookup (preserves status 74), and failing final evidence verification. They execute the actual shell script with mocked Git in an original-directory stand-in and assert no checkout or changes to that directory on prerequisite failures. These are behavioral checks, not syntax-only checks. Evidence: `validation/mac-trial-safety/failure-path-tests.log`.

The corrected script has not completed a full physical Intel Mac trial. Native Safari, VoiceOver, whole-stack peak memory/disk and real-provider CV verification remain separate validation boundaries. The frontend recovery helper remains separately reviewed. No original-data migration, original-page viewer, durable job system, deployment or customer-data admission is authorized.
