#!/usr/bin/env bash
# Execute, do not source. All failures preserve their status and stop this script.
if [[ "${BASH_SOURCE[0]}" != "$0" ]]; then
    printf '%s\n' 'Refusing to run when sourced.' >&2
    return 2
fi
set -Eeuo pipefail
trap 'status=$?; printf "Trial stopped with status %s at line %s; retain the trial directory and logs.\n" "$status" "$LINENO" >&2; exit "$status"' ERR
CANDIDATE_SHA=66db29f0b072fd9821869f4ffef008883ce0509b
verify_source() {
    test -n "${TRIAL_ROOT:-}"
    test -d "$TRIAL_ROOT/source/.git"
    test ! -L "$TRIAL_ROOT/source"
    actual_directory=$(pwd -P)
    expected_directory=$(cd "$TRIAL_ROOT/source" && pwd -P)
    test "$actual_directory" = "$expected_directory"
    repository_directory=$(git rev-parse --show-toplevel)
    test "$repository_directory" = "$actual_directory"
}
verify_commit() {
    resolved_commit=$(git rev-parse --verify "$CANDIDATE_SHA^{commit}")
    test "$resolved_commit" = "$CANDIDATE_SHA"
}
verify_candidate() {
    verify_source
    verify_commit
    actual_head=$(git rev-parse HEAD)
    test "$actual_head" = "$CANDIDATE_SHA"
    tracked_status=$(git status --porcelain --untracked-files=no)
    test -z "$tracked_status"
}
# Permission to run is limited to a separately reviewed synthetic trial.
# No original checkout, env files, volumes or images are used as input.
umask 077
TRIAL_ROOT="$(mktemp -d "$HOME/DocLens-synthetic-trial.XXXXXX")"
export TRIAL_ROOT
printf 'Keep this trial directory: %s\n' "$TRIAL_ROOT"
test -f "${1:?Usage: bash mac-synthetic-trial.sh /absolute/path/to/current.bundle}"
git bundle list-heads "$1"
git clone --no-checkout "$1" "$TRIAL_ROOT/source"
cd "$TRIAL_ROOT/source"
verify_source
verify_commit
git checkout --detach "$CANDIDATE_SHA"
verify_candidate
test "$(git rev-parse HEAD)" = 66db29f0b072fd9821869f4ffef008883ce0509b
initial_status=$(git status --porcelain)
test -z "$initial_status"
git bundle verify "$1"
mkdir "$TRIAL_ROOT/evidence"

python3.11 --version
node --version
npm --version
docker compose version
DOCKER_ENDPOINT="$(docker context inspect --format '{{.Endpoints.docker.Host}}')"
printf 'Local Docker endpoint: %s\n' "$DOCKER_ENDPOINT"

test "$DOCKER_ENDPOINT" = unix:///var/run/docker.sock
test -S /var/run/docker.sock
docker --host=unix:///var/run/docker.sock info --format 'Docker memory bytes: {{.MemTotal}}'
docker --host=unix:///var/run/docker.sock stats --no-stream --format '{{.Name}} {{.MemUsage}}'
df -h "$TRIAL_ROOT"

printf '%s\n' 'Confirm Activity Monitor/Docker/disk headroom before building; do not stop original services.'
read -r -p 'Type SYNTHETIC-HEADROOM-CHECKED to continue: ' capacity_confirmation
test "$capacity_confirmation" = SYNTHETIC-HEADROOM-CHECKED
verify_candidate
python3.11 -m venv "$TRIAL_ROOT/venv"
"$TRIAL_ROOT/venv/bin/python" -m pip install 'requests==2.32.5' 'PyMuPDF==1.26.5'
python3.11 recovery/mac-ui-candidate/prepare.py "$TRIAL_ROOT/frontend-context"
mkdir "$TRIAL_ROOT/backend-context"
cp backend/requirements.txt "$TRIAL_ROOT/backend-context/requirements.txt"
(cd frontend && npm ci)
export PLAYWRIGHT_BROWSERS_PATH="$TRIAL_ROOT/browsers"
(cd frontend && npx playwright install chromium)
CHROMIUM_PATH="$(cd frontend && node -e 'console.log(require("playwright").chromium.executablePath())')"
export CHROMIUM_PATH
test -x "$CHROMIUM_PATH"

cat > "$TRIAL_ROOT/backend-context/Dockerfile" <<'DOCKERFILE'
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt /tmp/requirements.txt
RUN python -m pip install --no-cache-dir 'torch==2.2.2+cpu' --index-url https://download.pytorch.org/whl/cpu && \
    python -m pip install --no-cache-dir -r /tmp/requirements.txt && \
    python -m pip check
DOCKERFILE
DOCLENS_CANDIDATE_BACKEND_IMAGE="doclens-synthetic-backend:$(basename "$TRIAL_ROOT" | tr '[:upper:]' '[:lower:]')"
export DOCLENS_CANDIDATE_BACKEND_IMAGE
docker --host=unix:///var/run/docker.sock build --platform linux/amd64 --progress=plain \
  -t "$DOCLENS_CANDIDATE_BACKEND_IMAGE" "$TRIAL_ROOT/backend-context" \
  > "$TRIAL_ROOT/evidence/backend-build.log" 2>&1

export HF_HOME="$TRIAL_ROOT/model-cache"
mkdir "$HF_HOME"
docker --host=unix:///var/run/docker.sock run --rm --platform linux/amd64 \
  -v "$HF_HOME:/model-cache" -e HF_HOME=/model-cache \
  "$DOCLENS_CANDIDATE_BACKEND_IMAGE" python -c \
  'from huggingface_hub import snapshot_download; from pathlib import Path; revision="1110a243fdf4706b3f48f1d95db1a4f5529b4d41"; snapshot_download("sentence-transformers/all-MiniLM-L6-v2", revision=revision); p=Path("/model-cache/hub/models--sentence-transformers--all-MiniLM-L6-v2/refs"); p.mkdir(exist_ok=True); (p/"main").write_text(revision)' \
  > "$TRIAL_ROOT/evidence/model-download.log" 2>&1

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
DOCLENS_CANDIDATE_FRONTEND_IMAGE="doclens-synthetic-frontend:$(basename "$TRIAL_ROOT" | tr '[:upper:]' '[:lower:]')"
export DOCLENS_CANDIDATE_FRONTEND_IMAGE
docker --host=unix:///var/run/docker.sock build --platform linux/amd64 --progress=plain \
  -t "$DOCLENS_CANDIDATE_FRONTEND_IMAGE" "$TRIAL_ROOT/frontend-context" \
  > "$TRIAL_ROOT/evidence/frontend-build.log" 2>&1
docker --host=unix:///var/run/docker.sock pull \
  qdrant/qdrant:v1.15.5@sha256:0fb8897412abc81d1c0430a899b9a81eb8328aa634e7242d1bc804c1fe8fe863

docker --host=unix:///var/run/docker.sock image inspect \
  "$DOCLENS_CANDIDATE_BACKEND_IMAGE" "$DOCLENS_CANDIDATE_FRONTEND_IMAGE" \
  --format '{{.Id}} {{json .RepoTags}}' > "$TRIAL_ROOT/evidence/image-ids.txt"
docker --host=unix:///var/run/docker.sock run --rm "$DOCLENS_CANDIDATE_BACKEND_IMAGE" \
  python -m pip freeze > "$TRIAL_ROOT/evidence/backend-dependencies.txt"
export DOCLENS_CANDIDATE_EVIDENCE="$TRIAL_ROOT/evidence/stack"
verify_candidate
"$TRIAL_ROOT/venv/bin/python" tests/mac_candidate_stack.py \
  > "$TRIAL_ROOT/evidence/trial.log" 2>&1

"$TRIAL_ROOT/venv/bin/python" - <<'PY'
import json, os
from pathlib import Path
r=json.loads((Path(os.environ['DOCLENS_CANDIDATE_EVIDENCE'])/'stack-results.json').read_text())
assert r['original_local_containers_unchanged'] is True
assert r['original_local_volume_names_unchanged'] is True
assert 'restart' in r['tests']
print(json.dumps(r, indent=2))
PY
final_status=$(git status --porcelain --untracked-files=no)
test -z "$final_status"
