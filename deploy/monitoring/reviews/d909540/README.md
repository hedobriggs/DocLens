# Direct acceptance: approved application d909540

**Application commit:** `d9095402cf393aa75f790c8e13b15ee215575412`.
**Execution:** Team Codex, 26 October 2026, existing Linux amd64 Docker host.
**Status:** requested runtime scenarios completed; independent acceptance/deployment approval remains pending. No image published, merge, paid resource launch, customer-data migration or Mac changes.

## Exact local image IDs

These are local image configuration IDs, not registry manifest digests. The new final image has not been published.

| Component | Image ID |
|---|---|
| runpod | `sha256:ce23cbb8278ab8ede485603d606340c065df280202788c959517a15079329f27` |
| frontend_setup | `sha256:60f8893a7727fa08a6457ad4b255b9d47a2da103270484651dd69e70611ac30e` |
| backend | `sha256:6630a9b44c22c047906d1aaba571f39e4e72d075921297dbc480ea98d01140b5` |
| qdrant | `sha256:0ad2e23181e5646b286253c04cea23f07040ca313cc377d9fa7b21db184b6406` |
| prometheus | `sha256:876ae6bcb0d6c9190d799e82c996fbe5faecdaaa0ec84f5e7dd272c0542ea63c` |
| grafana | `sha256:45900b2eda7da0cbda80b9025e446147d9085fee71675ba86a48a1cad34e4c8a` |

`frontend_setup` is the same image used by frontend and the one-shot setup service. Pinned upstream references, platform and sizes are in `image-ids.json`. Frontend/backend/RunPod images were built using an immutable archive of the exact approved commit, including the final EOF correction. `source-file-sha256.json` checks every archived source file against that Git commit before build. Runtime backend Python files and requirements were also SHA-256 compared with approved source. There is no earlier pre-normalization-image caveat in this acceptance run.

Backend reuses the pre-existing approved CPU dependency image `doclens-auto-backend:verification` with source copied at build time; no dependency changes. The dependency-reuse Dockerfile is included. Frontend uses the standard source-only Dockerfile; final RunPod assembly uses the standard `deploy/runpod/Dockerfile` and pinned Grafana/Prometheus/Qdrant inputs. No `.next`, Python source, supervisor or vendor binary was substituted through a runtime bind mount. The single image mounts only a fresh synthetic named volume and a public managed-proxy CA bundle. Compose retains its normal read-only monitoring configuration mounts and named configuration/data volumes.

## Results

| Required behavior | Exact single-container image | Complete Compose stack |
|---|---|---|
| Fresh startup | Healthy; missing volume and missing secrets rejected before admission | Setup completed, app/backend/Grafana/Prometheus healthy; Qdrant readiness checked by backend |
| Login | Real API login; real Chromium form login, Secure/HttpOnly cookie, no cookie injection | Same real form/API flow |
| Separate URLs | App `http://localhost:3000`; Grafana gateway `http://localhost:8080/monitoring/d/doclens`; Prometheus gateway `http://localhost:9090/prometheus/query` | Same fixed URLs |
| Anonymous/spoof rejection | Monitoring API 401; spoofed Grafana identity cannot bypass app session | Same |
| Raw services private | Host publishes only frontend target 3000 on loopback; API, Qdrant, Grafana and Prometheus internal listeners checked | Only frontend host ports; raw service PortBindings empty, internal monitoring/data networks |
| Real monitoring | Actual Grafana datasource POST 200 and rendered dashboard; Prometheus UI and live `up` data | Same, with all 12 panel queries tested |
| PDF ingestion | Real-model seven-page synthetic CV; real UI upload as well as API | Same; invalid PDF and 301-page failed replacement preserve records |
| Live Gemini counts | Five known fictional employers and total 5 for tested question forms; every required employer citation present | All three question forms repeated only where needed for restart or monitoring-failure states |
| Restart persistence | Forced interruption/stale-private-input recovery; graceful restart; full container removal/recreation with same volume. Exact records/publication/citation identities, saved config, existing session, Grafana preferences and Prometheus history retained | Actual `down`/`up` with changed container IDs, same named volumes. Same persistence checks. Forced Prometheus restart retains history |
| Monitoring failure | Stopped Grafana yields gateway 502 while API/live answers work; restart restores preferences | Stopped Grafana and stopped Prometheus tested separately; app API/live answers remain usable; monitoring recovers and history persists |
| Core failure | Qdrant exit shuts down the complete single container | API process killed; configured per-service restart policy starts it again, health/session/documents recover. Compose does not have whole-stack shutdown semantics |

All browser monitoring calls used real services. The added real browser flow has **no API stubs or cookie injection**: form login, upload, live Gemini answer/citation controls, session shared across ports and live Grafana/Prometheus were exercised. Transport was HTTP localhost using Chromium's loopback secure-cookie exception, **not HTTPS**. Separately, the initial direct suite's already-passed three-viewport scrolling checks used synthetic UI response stubs; these are not passed off as live backend answer evidence and were not rerun after the citation assertion failed.

## Synthetic fixture and citation criteria

The CV has seven text pages: five fictional employers (Aster Research, Birch Analytics, Cobalt Systems, Delta Robotics, Elm Computing), explicit client/vendor exclusion evidence on page 3, and education on page 7. Positive employer evidence is on pages 1,2,4,5,6. The real customer CV was neither indexed nor sent to Gemini in these tests. Limits/authentication/recovery code remain unchanged.

The first direct run returned the correct count 5 and all five employer names, citing pages 1,2,3,4,5,6. It failed the external harness's **exact set** assertion because page 3 was extra. Page 3 explicitly states that the client/vendor are not employers; it is relevant negative evidence for the total, rather than an invented or education-only reference. That raw failed run is retained in `direct-initial-failure/`.

The corrected verifier requires every positive employer page, permits that explicit exclusion page, rejects education-only/nonexistent pages and verifies each citation against current published fixture metadata. No application code or response was altered/filtered to pass the test. Minimal five-page citation selection is not guaranteed; reviewers should assess this documented criterion. The continuation's three saved API answers, twelve saved full-Compose API answers, and both real-browser flows cited only the five positive pages. Model alias remains the application's `gemini-3.5-flash-lite`; provider responses can vary.

The failed suite had removed its fixture in `finally`, so fresh login/upload setup was necessary for continuation. Already-passed admission negatives, body limit, 12-query matrix and three-viewport UI regressions were not repeated in that continuation. It reran the failed/unexecuted count cases, new fixed-port checks, actual browser flow and unfinished persistence/failure tests. Earlier 59 deterministic code checks were not rerun or counted as newly executed acceptance.

## Failures and corrective runs

1. **Direct exact-page assertion, exit 1.** Correct answer plus negative-evidence citation described above. Failure, original executed harness, complete container log and command output retained. Corrected continuation exit 0.
2. **Compose lifecycle log capture gap.** The complete suite passed, but raw pre-down service logs had not been saved before old containers were removed. Complete test/command outputs and post-down component logs remain retained. A focused startup/down-up logging rerun saved all stopped-container logs before removal for both lifetimes and passed. It did not rerun the browser, multiple count variants or component-failure matrix. Its reused initialization log label mentions “all 12 panel queries”; the reduced harness actually polled required scrape samples and prepared preferences only. The full 12-query proof is in the original complete Compose run. This label is not counted as an additional matrix execution.

Exit statuses: frontend build 0, backend build 0, final RunPod image build 0; original direct suite 1; direct continuation 0; complete Compose suite 0; focused log-capture correction 0. Raw outputs are not rewritten to hide the failure or stale label.

## Commands, full logs and reproduction

The archive contains exact executed Python/JS harnesses, build Dockerfiles, full Docker command/results, full suite stdout/stderr, service logs and screenshots. Main entry points:

```sh
python3 prepare_build.py
BUILDX_CONFIG=/tmp/DocLens-monitoring-buildx docker build --platform linux/amd64 --secret id=build_ca,src=/etc/ssl/certs/ca-certificates.crt -f deploy/portable/Dockerfile.frontend -t doclens-d909540-frontend:acceptance frontend
BUILDX_CONFIG=/tmp/DocLens-monitoring-buildx docker build --platform linux/amd64 -f /workspace/DocLens-d909540-acceptance/Dockerfile.backend-dependencies -t doclens-d909540-backend:acceptance .
BUILDX_CONFIG=/tmp/DocLens-monitoring-buildx docker build --platform linux/amd64 --build-arg FRONTEND_IMAGE=doclens-d909540-frontend:acceptance --build-arg BACKEND_IMAGE=doclens-d909540-backend:acceptance -f deploy/runpod/Dockerfile -t doclens-d909540-runpod:acceptance .
python3 direct-initial-failure/run_exact_image.py
python3 direct-continuation/run.py
python3 compose/run_compose.py
python3 compose-log-correction/run_compose.py
```

Build commands run from `source/`, the exact approved Git archive. The direct command log proves the run arguments use the final image **ID**, not a substituted image/tag. Compose commands, generated configuration, IDs before/after down-up, actual service image IDs and all outputs are in `compose/compose-commands-complete.log` and `compose/compose-result.json`. The focused corrected lifecycle's complete service output is in `compose-log-correction/compose-commands-complete.log`. The real browser's results and screenshots are in each `real-browser/` directory; API answers are in `live-answers.jsonl`.

Prerequisites for independent reruns: Linux amd64 Docker/Compose, sufficient VFS storage, the recorded CPU dependency image or a rebuild of the repository's pinned backend Dockerfile, a securely bound Gemini key, and host Node/Playwright/Chromium. Rebuilding may yield a different image ID (e.g. frontend build metadata); update only the external harness's expected image ID after independently checking your source/build. Do not change application files. No credential values are included. The temporary synthetic account password in test sources is a destroyed fixture, not a customer/admin credential.

## Test-host settings and capacity

Docker VFS host with approximately 35.7 GB RAM and 5 reported CPUs; single-container tests capped at 2 CPU / 4 GiB. Compose uses the reviewed individual service caps. Only previous-task own superseded local prototypes/build inputs and unused build cache were reclaimed; published baseline images, unrelated images/volumes and all Mac resources were preserved. Tests ran sequentially; no paid resource or capacity increase was requested.

The managed host automatically injects an outbound proxy. Compose test-only environment overrides clear proxy variables only for internal-only monitoring services (BusyBox loopback health checks otherwise use that proxy), and add the public combined CA trust to backend for managed-proxy HTTPS. The overlay is included. Backend/frontend outbound proxy routing and TLS verification remain intact. This is a documented host adaptation, not a stock arbitrary-proxy compatibility claim. The earlier baseline proxy failure was not reproduced unnecessarily; it is prior evidence, not a new application failure.

## Remaining gates and restrictions

- Actual RunPod HTTPS/browser/proxy behavior, registry pull, provider stop/start and forced-restart attached-storage durability remain **pending**.
- Native Mac/Safari/VoiceOver for the final image are not tested here. Your Mac was not accessed or changed.
- No customer-data migration/admission, production traffic, backup/restore validation or large-document capacity benchmark. The seven-page fixture does not establish 8 GB Mac performance limits.
- This is Team Codex execution, not independent Reviewer Codex approval. The application code is approved; acceptance/deployment approval remains pending review and separate user authorization. The citation criterion and original failures must be included in review.
- No image registry publication, merge, paid Pod/server, installation replacement or app source change occurred. Runtime/cleanup used only uniquely named synthetic namespaces created by these harnesses.

Next action: independently review the exact image/source provenance, documented citation criterion, test-only host overlay and complete evidence. Image publication, actual RunPod trial and deployment require separate authorization.

## Evidence download

[Complete command/results/log/screenshot archive](acceptance.zip)

Archive SHA-256: `2cd2abd07bdd5b1cad4667c46c1f04d9d274169c7eb8bde9ca7270cd421d185d`. Size: 1351936 bytes. Real-secret and customer-CV scans plus ZIP integrity passed. This is evidence only; no Docker image binary or credential values are included. Application inputs remain at the approved commit; keep this evidence commit separate from any eventual application merge.
