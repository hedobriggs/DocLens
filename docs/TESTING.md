# Test DocLens

Use synthetic documents only. Store logs/screenshots outside the repository, for
example under `/tmp/DocLens-tests`. Retain failures separately from passing retries.

## Packaging safety (host Python standard library)

```sh
python3 deploy/portable/test_packaging.py
python3 deploy/portable/test_launcher.py
```

Covers runtime overwrite/project-volume protection, source hash rejection,
credential exclusion and the real release manifest/context. The last check would
have caught the stale hashes after the legal UI integration. It mocks Docker
execution; it is not a container build or functional application test.

## Backend regressions

With Python 3.11 and dependencies from `backend/requirements.txt` in an isolated
environment (the prepared cloud checkout uses `backend/.venv/bin/python`):

```sh
backend/.venv/bin/python tests/test_mac_upload_limits.py
backend/.venv/bin/python tests/test_mac_document_coverage.py
backend/.venv/bin/python tests/test_mac_publication_server.py
```

The first two use real PDF parsing/local Qdrant with controlled inference/provider
responses. Publication-server checks launch isolated synthetic Docker Qdrant and
remove only their own container. The `mac_` names identify existing regression
history; they are not separate application versions or installation procedures.

## Frontend

Node 20.9+ is needed for local development. The shipping image pins Node 22.
Install with `npm ci` inside `frontend`, then from the root:

```sh
npm --prefix frontend run lint
npm --prefix frontend run build
DOCLENS_LEGAL_VIEWPORT_CHECK=1 node tests/mac_candidate_ui.cjs after /tmp/DocLens-ui
node tests/mac_candidate_keyboard.cjs /tmp/DocLens-keyboard
```

Install Playwright Chromium if needed and set `CHROMIUM_PATH` to its executable;
the Linux default is `/usr/bin/chromium`. Viewports are 1280×800, 1440×900, plus
375×812 when the legal viewport check is enabled. Routes are synthetic browser
fixtures. Tests cover busy/error/cancel states, file chooser, citations, long-name
clipping and contrast. They do not establish native Mac/Safari/VoiceOver coverage.
The retained `mac_upload_browser.cjs` and `mac_upload_fixtures.py` additionally
exercise gateway/body timeout failures and synthetic large uploads; see their
headers/environment options before running the slower wall-clock suite.

## Packaged end-to-end acceptance

Follow the installation guide's fresh synthetic project and run
`python3 smoke.py --restart`. This uses real embedding/indexing through the built
frontend/backend and persistent Qdrant. On a separately configured real-key test
project, `python3 smoke.py --live-answers --restart` submits synthetic context to
Gemini and checks all five employers and citations. Never run smoke on customer
indexes. A live-provider pass does not certify every future answer or latency.

Screenshots, raw logs, image inventories and approval bundles are external review
artifacts. Current test summaries belong in the review; previous committed
artifacts remain in Git history. Do not add generated evidence back to this tree.

## Automatic root Compose startup

Developer-only startup validation uses Node's built-in test runner:

```sh
node --test tests/test_bootstrap.cjs
python3 deploy/portable/test_packaging.py
```

These cover input validation, literal dollar/shell characters, duplicate keys,
password bounds, stable saved sessions, changed-credential refusal, existing-index
refusal, partial-setup recovery and symlink rejection. Packaging checks enforce
source-only Docker context allowlists. No host Node/Python is required by users
running the application through Docker.

After building the images, run:

```sh
python3 tests/test_compose_root.py
```

This developer acceptance script uses only Python's standard library to create a
fresh synthetic fixture. The application setup itself runs inside Docker: no
`build.py` or `configure.py` invocation is part of it. Tests verify credentials
and ports/resource separation, actual login and PDF embedding/indexing, app-role
file permissions, stable settings and exact document/citation identities across
normal down/up, and rejection/recovery of changed input credentials. Only the
fixture's generated volumes are removed; unrelated Docker inventories must match.
Optional `DOCLENS_TEST_BACKEND_IMAGE` / `DOCLENS_TEST_FRONTEND_IMAGE` select images
built through Compose for a fresh-build evaluation.

Raw logs remain external artifacts. The first automatic test reached healthy
application services but the reused smoke helper still called the old manual
configuration wrapper. That test-fixture failure is retained; the helper now
routes to the actual root Compose project without running manual setup. Public
HTTPS, target Mac/browser coverage and backup restoration are separate validations.

The fresh-image test exposed host-mode-dependent bind-mounted startup scripts.
They are now packaged into the images with explicit readable permissions instead;
no source-script host bind mounts are needed at runtime. That unhealthy-container
failure, the test-fixture wrapper failure, and a fixture-directory reuse error are
retained externally alongside the passing reruns. Strict Docker context allowlists
also excluded synthetic private `.env` and backup canaries during Compose builds.

Final automatic-startup validation passed: 9 bootstrap unit tests, 6 packaging
checks and 11 legacy-launcher checks; actual Compose image builds; plain `up`
without host setup scripts; synthetic login/indexing; role-based file denial;
normal down/up preserving exact data and settings; changed-password rejection and
recovery. Both newly built packaged images were used for the final full acceptance
run, and unrelated container/volume inventories matched afterward. Application
logic, dependencies, auth, upload limits and worker budgets were verified unchanged.
