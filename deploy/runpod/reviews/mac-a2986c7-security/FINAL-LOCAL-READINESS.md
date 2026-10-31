# DocLens consolidated local readiness — independent decision requested

## Decision requested

Accept the narrowly scoped local functional evidence, including the final Grafana rendering gate, if independent artifact review concurs. **Do not grant security release approval or execution authorization.** No merge, registry publication, deployment, data migration, existing-installation changes or RunPod launch is authorized. This report consolidates evidence; it does not issue Reviewer Codex's decision.

## Exact identities and transferable evidence

- Application/build source: `299f3b48bbcd1058845ce14f528fba553d68a783`.
- Unchanged local candidate image: `sha256:4e3a0339cb5e1465701f757ca136039c369ab96fa672401a938e3efa0e5467d8` (linux/amd64). This is a local Docker image identifier, not a published registry digest.
- Underlying previously recorded image config: `sha256:7beedeb9bd93ad148b09c79bb53db672134b7c4d73d37267f4d813616cb2c9ad`.
- Final external harness: `2e3cd6ab003f7decd0b2514cfe6bdd82eea44308`. Both supplied harness files match this Git commit byte-for-byte.
- Final archive: `focus.6LtEu2.zip`, 53,068,743 bytes.
- SHA-256: `47aac7dde925edff3a02235dc1e1152710036a7ede9271f1aa803fe99e424998`.
- Reassembled in aa/ab/ac order from three uploaded transport parts; expected SHA and ZIP CRC validation pass. Original ZIP bytes are unchanged. Transport splitting does not alter the archive.
- Adjacent `final-monitoring-verification.json` independently maps all 12 panels to matching successful executed PromQL responses, DOM/screenshot hashes, baseline/increment timestamps and preserved archive hashes.

All artifact paths below are inside that ZIP unless stated otherwise. Original commands/options are in `bootstrap.log`, `command.json`, `docker-commands.json` and the two exact harness scripts. Host command: `python3 /Users/nnamdihedo/DocLens-fixed-build.Xmet07/focus.6LtEu2/focused-acceptance.py`; child command: `node /Users/nnamdihedo/DocLens-fixed-build.Xmet07/focus.6LtEu2/focused-browser.cjs`. Exact image is run directly, without runtime-file bind overrides; its fresh synthetic volume is mounted at /workspace. Only own labelled resources are cleaned up. No tests or rebuild were repeated during transfer/inspection.

## Functional results and provenance

| Scope | Evidence/status | Interpretation |
|---|---|---|
| Native imports/inference, PDF processing, 13 TLS/config/framework checks, auth/access restrictions, real Gemini five-employer answers/citations, failed replacement preservation, restart/recreation persistence, monitoring/core failure behaviour | First batch accepted within scope at `fd817ae64a1a6a98e2c04d05c3f19067aa6d6e69`; archive `acceptance.vW5s1h.zip`, SHA `a611b5f31ac4857fa1fb4a1025c2391f1914d533a0202b2cbc0966a0a04d0719` in repository | Previously accepted, not rerun by final monitoring fixture |
| Upload clock expiry and Prometheus browser up-query rendering | `original-focus.66Jlsq.zip` | Previous passes retained, not claimed newly executed |
| Upload HTTP401/re-authentication | `original-focus.d0yA5Q.zip` | Previous pass retained |
| Question HTTP401 and deterministic clock-expiry recovery, live recovered answers/page1 citations | Accepted from evidence commit `53396fdd4dd22af78f68c6c68f11d1d2ffbb7155`; `original-focus.xMLqet.zip` | Accepted question recovery remains accepted; final fixture does not repeat these tests |
| All12 Grafana panels after actual reload, live DOM and visual rendering, corresponding nonempty numeric query data | Final `results.json` and `host-results.json`: PASS, exit0; Team Codex independently verified raw records and inspected all12 screenshots | Ready for independent review of final monitoring gate; no automatic release approval |

Mac executed the tests: Intel x86_64, macOS15.7.9, Docker8CPU/4,101,177,344 bytes RAM, Node25.8.0, Chromium156.0.8078.4. Team Codex verified supplied artifacts and source identity; it did not independently execute the image on a second host. Synthetic one-page fixtures establish these behaviours, not supported large-document throughput or latency limits.

## Final monitoring evidence

- `scraped-baseline.json`: actual upload counter1 and duration histogram count1 observed in Prometheus at raw sample timestamp1793404111.808.
- `scraped-increases.json`: both increased to2 at1793404126.819. Retrieval/Gemini counts also1→2; tokens254→512; successful logins1→2; failed logins2→3. Actual warm-up and measured traffic records are preserved.
- `panel-readiness-*.json`: exact baked expressions return finite values before Grafana assertions. Names/labels/queries were not changed; no fake series or fixed sleeps. Bounded condition waits replace assumptions about scrape readiness.
- `grafana-initial-query-responses.json`: six initial-epoch responses; `grafana-post-reload-query-responses.json`: twelve post-reload responses. All HTTP200, complete, no body-read/request/query errors. Request identity/URL/status/timing and body remain tied to original request epochs.
- `grafana-panel-query-map.json`: panel1→query7 through panel12→query18, independently cross-checked using each executed expression against dashboard model, not inferred from ordering alone.
- `grafana-panel-N-dom.html` and `grafana-panel-N.png`, N=1..12: all present. All screenshots visually inspected; service jobs are up=1, all other panels contain plotted values, including the previously empty upload panels. Very short/sparse graphs are expected from bounded synthetic traffic; p95 interpolation/coarse buckets are not proof of accurate production latency targets.
- `grafana-dashboard-model.json`, `fixture-baked-dashboard.json`, fixture/scrape probes and logs are preserved. Application image and dashboard queries are unchanged.
- Before/after inventories: same five preexisting stopped containers and nine volumes; no leftover trial resources. They were not attached to the candidate. Inventory equality is not a content hash of preexisting volumes.

## Failure history retained, not rewritten

The final ZIP contains all six prior archives byte-for-byte; see hashes in `final-monitoring-verification.json`:

1. `original-focus.66Jlsq.zip`: forbidden Cookie override, empty-input Send assertion, premature Grafana title wait; some scoped passes retained.
2. `original-focus.d0yA5Q.zip`: nested citation and Grafana panel locator failures.
3. `original-focus.xMLqet.zip`: accepted question cases and12 panel captures, but two unattributed response-body read errors across navigation; original FAIL remains.
4. `original-focus.JBlwqI.zip`: external browser-fetch status() error before monitoring.
5. `original-focus.0YI2RZ.zip`: collector succeeded; upload rate/percentile panels empty from lack of observed metric increase.
6. `original-focus.DDYfOA.zip`: diagnostic collection successful, readiness not achieved; raw constant counter/bucket samples prove why additional waiting alone was insufficient.

The correction was entirely external fixture sequencing: observe scraped warm-up baselines, generate subsequent events, verify actual increases and finite exact queries. No application-code or dashboard change was needed. Prior unsuccessful attempts are not relabelled PASS by the final successful run.

## Unresolved security release blockers

**137 original critical/high ledger occurrences remain OPEN.** Scoped approvals at `63e6049fd0ef713e3e6d94a31228dc6c4112dcb7` remain exactly two: system SQLite CVE-2025-7458 addressed in this candidate; CVE-2023-45853 not affected only for the exact assessed original Debian core-libz copy, excluding bundled/unidentified copies. Original139-row ledger/decision history remains preserved. Functional success does not close advisories.

Accepted scan evidence `8d8f0ec7f95b871e1e009978a24e82e40e6680b4` reported0 critical and120 high occurrences in the rebuilt candidate (44OS,7Grafana core,69plugins), plus remaining medium/low/unknown findings. These scan occurrences are a different population from137 open original-ledger entries; do not equate them or treat scan absence as closure. No new scan or remediation executed in this evidence transfer. See `fresh-scan-results.md`, `original-ledger-current.csv`, `review-decision-history.jsonl`, `review-followup-20261030.md` and `unreported-18-advisory-assessment.csv` in this repository directory. No-fix advisories and the Grafana embedded-SQLite provenance limitation remain open within their recorded scope. Security clearance is blocked pending advisory-specific independently reviewed dispositions/remediation and required rebuilt-image evidence where appropriate.

## Remaining validation and execution boundaries

Actual RunPod HTTPS/browser authentication, proxy behaviour and attached-storage stop/start/forced-restart acceptance remain pending. Complete Compose monitoring-stack acceptance is not established by this baked-image batch. Safari/VoiceOver were not tested. Clock-expiry is deterministic browser-clock simulation using server-verified signed sessions; intercepted busy requests were held before backend admission, so these tests do not prove cancellation of already admitted work. The historical /api/ask HTML/JSON incident has not been independently diagnosed by these successful synthetic JSON responses and is not claimed resolved. Larger PDF limits/performance are not approved by this batch. Web modes remain disabled; PDF-only scope remains.

Recommended consolidated decision: accept final local synthetic monitoring evidence within the stated image/harness/host limits if independent review concurs, retain previously scoped functional approvals, keep security clearance and all pending platform/release gates blocked. No further functional retest is proposed absent a specific artifact defect or relevant change. Nothing here authorizes merge, publication or deployment.
