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

## Standard repository-root Compose entry point

After building the two application images, run:

```sh
python3 tests/test_compose_root.py
```

Uses Python's standard library and an isolated synthetic Docker project. It
validates the included service definitions, resource limits, private ports and
credential separation, then exercises actual PDF ingestion. It executes normal
`docker compose down` and `up`, checking that all stored points, payloads and
publication/citation identities survive. Fixture teardown removes only the
fixture's own generated volumes and verifies unrelated Docker inventories match.
Never use `down -v` on an installation whose documents you want to retain.

The first execution exposed a test assertion expecting numeric JSON values where
Compose returns memory strings; that failure was retained externally and the
assertion now converts the value explicitly. This did not require changing
application resource controls. The root workflow still needs one-time private
configuration and built images; daily start/stop requires no launcher script.

The corrected full run passed on Linux amd64 / Compose 2.40.3: actual login,
five-page PDF embedding/indexing, failed-replacement preservation, normal down/up
persistence, and unchanged unrelated container/volume inventories. Physical Mac
and browser HTTPS acceptance remain outside this result.
