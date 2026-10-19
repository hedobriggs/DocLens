# Separate Mac synthetic-data trial — candidate af5358f

This procedure is for a new disposable directory, not your original DocLens installation. It does not use your recovery helper, original `.env`, credentials, checkout, backups, originals, or Qdrant volumes. Do not run the original installation's Compose file or combine it with this one. Only generated synthetic PDFs are permitted in this trial.

Application candidate: **af5358f161d19fe6289316c5b4e224f9434bafa2**. Approved UI source: **02815cccb0371faa791d55bab0c09991e3aa6a44**. No merge, deployment, migration, or limit increase is authorized.

## Prerequisites and validation boundary

Required: Intel Mac, Docker Desktop running Linux containers, Docker Compose **2.30 or newer**, Git, Python **3.11**, Node **20.9 or newer** (Node 20 recommended), npm, sufficient free disk space, and a macOS version supported by the bundled Playwright Chromium. Stop if these prerequisites are unavailable; do not upgrade the original application to satisfy them.

**The backend dependency image is a prerequisite.** The cloud-only tag `doclens-mac-upload-freeze:review` does not establish that the image exists on your Mac. The commands below build a separate CPU-only dependency image from the candidate's pinned requirements. They also build a separate frontend and download the pinned public model into a new cache. No AWS, Hugging Face, or Gemini account credentials are needed. Answer generation against Gemini is excluded.

The application candidate and its isolated stack have passed cloud testing. **The fresh dependency build and the Mac-specific procedure below have not been executed on a physical Mac.** A successful build alone is not approval: retain the new image IDs, dependency inventory, logs and test results for independent review. Dependency/platform differences from the cloud image remain a validation boundary.

Do not stop existing services, prune Docker, raise Docker's memory allocation, or modify your original installation to make room. Check Activity Monitor → Memory and Docker Desktop resources first. Candidate backend has a 1.5 GiB cap, frontend a 512 MiB cap; Qdrant, browser, build processes and Docker need additional memory. Your original services also consume memory. A Docker VM limited to about 3.82 GiB may not have sufficient headroom for both stacks. **If memory pressure is yellow/red, swap is rising, disk space is low, or sufficient headroom is uncertain, stop before building/running and report it.** The trial is not proof of whole-stack peak memory safety on an 8 GB Mac.

## One update-free trial procedure

Use a new Terminal window. Run each block separately and stop at the first failure. Do not paste subsequent blocks after a failed command. These commands do not update your original installation.

### 1. Create a fresh workspace and verify the exact source

Download `DocLens-Mac-candidate.bundle` from Team Codex's handoff. Use its actual location below; do not use your original checkout as the source.

```bash
umask 077
TRIAL_ROOT="$(mktemp -d "$HOME/DocLens-synthetic-trial.XXXXXX")"
export TRIAL_ROOT
printf 'Keep this trial directory: %s\n' "$TRIAL_ROOT"
git clone "$HOME/Downloads/DocLens-Mac-candidate.bundle" "$TRIAL_ROOT/source"
cd "$TRIAL_ROOT/source"
git checkout --detach af5358f161d19fe6289316c5b4e224f9434bafa2
test "$(git rev-parse HEAD)" = af5358f161d19fe6289316c5b4e224f9434bafa2
test -z "$(git status --porcelain)"
git bundle verify "$HOME/Downloads/DocLens-Mac-candidate.bundle"
mkdir "$TRIAL_ROOT/evidence"
```

If the download has a different filename/location, change only that bundle path in both commands. A missing object, unexpected SHA, or dirty tracked source is a stop condition.

### 2. Check local Docker and prerequisites

```bash
python3.11 --version
node --version
npm --version
docker compose version
DOCKER_ENDPOINT="$(docker context inspect --format '{{.Endpoints.docker.Host}}')"
printf 'Local Docker endpoint: %s\n' "$DOCKER_ENDPOINT"
```

The existing runner intentionally uses `unix:///var/run/docker.sock`. Continue only when the selected Docker Desktop context reports that endpoint and the socket exists. If it reports `unix:///Users/.../.docker/run/docker.sock`, TCP, SSH, or anything else, **stop and report the endpoint**. Do not create a symlink, switch to another daemon, or modify the reviewed runner as an ad hoc workaround.

```bash
test "$DOCKER_ENDPOINT" = unix:///var/run/docker.sock
test -S /var/run/docker.sock
docker --host=unix:///var/run/docker.sock info --format 'Docker memory bytes: {{.MemTotal}}'
docker --host=unix:///var/run/docker.sock stats --no-stream --format '{{.Name}} {{.MemUsage}}'
df -h "$TRIAL_ROOT"
```

Review headroom before continuing. Do not share complete `docker inspect` output or `.env` files; they can expose credentials.

### 3. Prepare clean build contexts and isolated test dependencies

```bash
python3.11 -m venv "$TRIAL_ROOT/venv"
"$TRIAL_ROOT/venv/bin/python" -m pip install 'requests==2.32.5' 'PyMuPDF==1.26.5'
python3.11 recovery/mac-ui-candidate/prepare.py "$TRIAL_ROOT/frontend-context"
mkdir "$TRIAL_ROOT/backend-context"
cp backend/requirements.txt "$TRIAL_ROOT/backend-context/requirements.txt"
(cd frontend && npm ci)
export PLAYWRIGHT_BROWSERS_PATH="$TRIAL_ROOT/browsers"
(cd frontend && npx playwright install chromium)
export CHROMIUM_PATH="$(cd frontend && node -e 'console.log(require("playwright").chromium.executablePath())')"
test -x "$CHROMIUM_PATH"
```

Only tracked frontend files and the requirements file enter image build contexts. No original `.env`, backups, Docker metadata, or filesystem capture is copied. Host dependencies are installed only in the new checkout/venv/browser directory.

### 4. Build the prerequisite backend dependency image

```bash
cat > "$TRIAL_ROOT/backend-context/Dockerfile" <<'DOCKERFILE'
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt /tmp/requirements.txt
RUN python -m pip install --no-cache-dir 'torch==2.2.2+cpu' --index-url https://download.pytorch.org/whl/cpu && \
    python -m pip install --no-cache-dir -r /tmp/requirements.txt && \
    python -m pip check
DOCKERFILE
export DOCLENS_CANDIDATE_BACKEND_IMAGE="doclens-synthetic-backend:$(basename "$TRIAL_ROOT" | tr '[:upper:]' '[:lower:]')"
docker --host=unix:///var/run/docker.sock build --platform linux/amd64 --progress=plain \
  -t "$DOCLENS_CANDIDATE_BACKEND_IMAGE" "$TRIAL_ROOT/backend-context" \
  > "$TRIAL_ROOT/evidence/backend-build.log" 2>&1
```

If the build fails, keep the log and stop. Do not fall back to an arbitrary existing image. TLS verification stays enabled. If your network requires an additional trusted CA, request a reviewed trust configuration rather than disabling verification. The base image tag can resolve to a newer digest than the cloud dependency image; record its provenance and treat this as a fresh dependency build requiring trial evidence.

### 5. Download the public model into a fresh candidate-only cache

```bash
export HF_HOME="$TRIAL_ROOT/model-cache"
mkdir "$HF_HOME"
docker --host=unix:///var/run/docker.sock run --rm --platform linux/amd64 \
  -v "$HF_HOME:/model-cache" -e HF_HOME=/model-cache \
  "$DOCLENS_CANDIDATE_BACKEND_IMAGE" python -c \
  'from huggingface_hub import snapshot_download; from pathlib import Path; revision="1110a243fdf4706b3f48f1d95db1a4f5529b4d41"; snapshot_download("sentence-transformers/all-MiniLM-L6-v2", revision=revision); p=Path("/model-cache/hub/models--sentence-transformers--all-MiniLM-L6-v2/refs"); p.mkdir(exist_ok=True); (p/"main").write_text(revision)' \
  > "$TRIAL_ROOT/evidence/model-download.log" 2>&1
```

No token or existing cache is mounted. Trial runtime mounts only this model's directory read-only and operates offline. Do not mount your whole Hugging Face cache or home directory.

### 6. Build a separate frontend with normal public CA trust

The reviewed cloud Dockerfile requires cloud-specific CA secrets. This disposable build context uses ordinary container CA trust instead; application files and package lock remain unchanged. It is a Mac trial build adaptation, not a change to the candidate application commit.

```bash
cat > "$TRIAL_ROOT/frontend-context/Dockerfile" <<'DOCKERFILE'
FROM node:20-alpine@sha256:fb4cd12c85ee03686f6af5362a0b0d56d50c58a04632e6c0fb8363f609372293
WORKDIR /app
COPY . .
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
RUN npm install --global npm@11.9.0 --strict-ssl=true --no-audit --no-fund && \
    npm ci --strict-ssl=true --fetch-retries=0 --fetch-timeout=30000 --no-audit --no-fund && \
    NEXT_TURBOPACK_EXPERIMENTAL_USE_SYSTEM_TLS_CERTS=1 NEXT_TELEMETRY_DISABLED=1 npm run build && \
    rm -rf .next/cache
EXPOSE 3000
CMD ["npm", "start"]
DOCKERFILE
export DOCLENS_CANDIDATE_FRONTEND_IMAGE="doclens-synthetic-frontend:$(basename "$TRIAL_ROOT" | tr '[:upper:]' '[:lower:]')"
docker --host=unix:///var/run/docker.sock build --platform linux/amd64 --progress=plain \
  -t "$DOCLENS_CANDIDATE_FRONTEND_IMAGE" "$TRIAL_ROOT/frontend-context" \
  > "$TRIAL_ROOT/evidence/frontend-build.log" 2>&1
docker --host=unix:///var/run/docker.sock pull \
  qdrant/qdrant:v1.15.5@sha256:0fb8897412abc81d1c0430a899b9a81eb8328aa634e7242d1bc804c1fe8fe863
```

### 7. Record dependencies and run the synthetic trial

```bash
docker --host=unix:///var/run/docker.sock image inspect \
  "$DOCLENS_CANDIDATE_BACKEND_IMAGE" "$DOCLENS_CANDIDATE_FRONTEND_IMAGE" \
  --format '{{.Id}} {{json .RepoTags}}' > "$TRIAL_ROOT/evidence/image-ids.txt"
docker --host=unix:///var/run/docker.sock run --rm "$DOCLENS_CANDIDATE_BACKEND_IMAGE" \
  python -m pip freeze > "$TRIAL_ROOT/evidence/backend-dependencies.txt"
export DOCLENS_CANDIDATE_EVIDENCE="$TRIAL_ROOT/evidence/stack"
"$TRIAL_ROOT/venv/bin/python" tests/mac_candidate_stack.py \
  > "$TRIAL_ROOT/evidence/trial.log" 2>&1
```

This is an automated, headless Chromium trial, not a permanently running preview. It starts a random candidate Compose project with loopback-only random ports, fresh private synthetic Qdrant directories, synthetic credentials and read-only candidate source/model mounts. It never mounts original volumes. It exercises real login/upload/indexing, a two-page PDF, a genuinely dense 32-page ~12.7 MB PDF, health responsiveness during indexing, failed-replacement preservation, page-limit rejection, a real browser keyboard/upload interaction, and restart preservation of synthetic point IDs/citations/publication metadata.

The runner tears down only its own random project and removes its generated private synthetic storage at the end. Existing container/volume-name inventories must remain unchanged. Do not interrupt by closing Terminal or stopping Docker; if interrupted, retain the log and report the candidate project name for scoped cleanup. Do not use global prune or the original Compose project.

### 8. Verify and hand back the evidence

```bash
"$TRIAL_ROOT/venv/bin/python" - <<'PY'
import json, os
from pathlib import Path
r=json.loads((Path(os.environ['DOCLENS_CANDIDATE_EVIDENCE'])/'stack-results.json').read_text())
assert r['original_local_containers_unchanged'] is True
assert r['original_local_volume_names_unchanged'] is True
assert 'restart' in r['tests']
print(json.dumps(r, indent=2))
PY
test -z "$(git status --porcelain --untracked-files=no)"
```

Success requires the trial command itself to exit zero, the final assertions to pass, and no unexplained errors/OOM/restarts. Preserve **failed attempts as well as subsequent passes** in separate evidence directories; do not overwrite the first failure with a retry. The runner's JSON is not a complete measurement of whole-stack peak memory/disk use.

Send Team/Reviewer Codex: exact source SHA, image IDs, dependency inventory, build/model/trial logs, `stack-results.json`, `container-browser.log`, and `container-browser.png`. Review logs for private host paths before sharing; do not include runtime env files, cookies, credentials, full container metadata, your original documents, or captured filesystems. Keep the original installation running and untouched. Do not retry your private document against this synthetic trial.

## Remaining limitations, separate from trial success

- Physical Intel Mac execution, Safari and VoiceOver remain unverified until tested; Chromium evidence is not Safari/VoiceOver evidence.
- The new CPU dependency image must build successfully and pass the trial on your Mac. Its image ID cannot match a separately built cloud image, and the base image is not digest-pinned here.
- macOS/Docker Desktop socket compatibility is an explicit stop condition; the runner currently requires `/var/run/docker.sock`.
- Concurrent whole-stack resource safety on 8 GB RAM has not been established. Do not infer it from the cloud's ~8.3-second dense-PDF result or from service memory caps.
- Existing limits/timeouts/resource controls are unchanged. No original-page viewer, durable background jobs, real Gemini answer validation, original-data migration or recovery-helper approval is included.
- Passing this trial does not authorize replacing the original installation. A later update needs a separately approved preservation/recovery procedure.
