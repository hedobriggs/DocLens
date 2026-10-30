# Focused harness correction — acceptance pending

Unchanged image: `sha256:4e3a0339cb5e1465701f757ca136039c369ab96fa672401a938e3efa0e5467d8`.
Application source: `299f3b48bbcd1058845ce14f528fba553d68a783`.

Original Mac failure archive is preserved verbatim as `focus.66Jlsq.zip`, SHA-256 `85dd9a97ef9558cdc0efc3f826d2add0c14353a91853ed2592d879e252dc4b26`.
It contains four failed assertions, one passed upload-clock scenario and passed Prometheus browser rendering. Question-clock recovery actually returned a correct live answer and citation, but the test incorrectly required Send enabled on an empty input. Grafana screenshot shows title and empty panels; no final rendering claim.

Only external harness changes:
- Replace ignored Cookie-header override with browserContext.addCookies on the same cookie, verify installation, and continue the held request without forbidden overrides. Require actual HTTP 401.
- After recovery answer require no busy button, empty question, disabled Send, visible answer and citation; fill a new draft and require enabled Send without dispatching another question.
- Wait up to 90 seconds for Grafana title, then actual service data, reload, and existing per-panel loading/content/canvas conditions plus successful nonempty datasource frames. This is a bounded condition wait, not a fixed sleep. Visual screenshots must still be inspected.
- Rerun only upload-401, question-401, question-clock and Grafana. Retain prior passed upload-clock and Prometheus evidence; do not represent them as newly run.
- Verify original archive before trial creation, include it unchanged in the new corrective evidence ZIP, use a new attempt directory, preserve failed reruns.

Executed here: Python/Node syntax checks; local Chromium + synthetic HTTP server reproduced ignored Cookie override (200) and verified supported browser cookie installation (401). Mocked wrapper checks passed failure retention, zero-exit/missing-evidence rejection, evidence completeness, redaction, unique naming, overwrite refusal and inventory preservation. These are harness checks, not execution of the Mac candidate image. Full commands and outputs: `focused-correction-checks.zip`.

Pending: Mac execution of corrected harness, final panel screenshot inspection and independent acceptance review. Exact image is on the Mac; this environment has no connection to that Docker engine. No application edits, rebuild, merge, publication or deployment. Security block and 137 open ledger entries remain unchanged. Actual RunPod HTTPS/storage and full Compose acceptance are separate gates.
