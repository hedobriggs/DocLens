# External selector correction; Mac acceptance pending

Image remains sha256:4e3a0339cb5e1465701f757ca136039c369ab96fa672401a938e3efa0e5467d8. No application/runtime changes.

Preserved archives:
- focus.66Jlsq.zip: 85dd9a97ef9558cdc0efc3f826d2add0c14353a91853ed2592d879e252dc4b26
- focus.d0yA5Q.zip: f44a1f1cfedd91268caca2c7a89c5849173a4e0f46f9aa57e11bfca5be0a6adc

Second archive independently checksum-verified. Both question failures are citation locator failures after successful real expiry, reauthentication, upload and live answers with page-1 citations visible in screenshots. Grafana screenshot shows populated top panels; six captured post-reload queries returned 200 without query errors. This does not establish all-panel rendering.

External changes only: locate citation summary, filter by filename and page across nested spans; discover Grafana panel from its unique exact title in the actual live DOM and unique descendant panel-content test identifier, refusing ambiguous matches. Capture selected panel DOM before assertions and whole-page DOM on failures; retain loading/data/canvas/query/screenshot assertions. Do not guess accessible name by appending "panel". Rerun only two question scenarios and Grafana; prior upload and Prometheus passes remain earlier evidence.

Local Chromium regression uses nested citation markup and a panel fixture without the guessed accessible name. It verifies old citation failure, corrected citation success, executes the exact live-DOM discovery function and verifies ambiguity rejection. Wrapper mock checks passed failures/zero-exit evidence validation/redaction/preservation/overwrite refusal. Python and Node syntax and git whitespace checks passed. Commands/source/output are in selector-correction-checks.zip. These are fixture/harness checks, not validation of the actual Mac rendered DOM. That validation must execute on the Mac and produce captured DOM plus screenshots. No remote Mac access is configured here. No baked-image execution claimed.

New Mac wrapper requires and checksum-verifies both prior archives before starting, copies both into a new evidence ZIP, refuses reuse of attempt directories, checks existing inventory and touches only its own synthetic trial resources. Keep acceptance/security blocked, including 137 open original ledger entries. No rebuild, merge, publication or deployment.
