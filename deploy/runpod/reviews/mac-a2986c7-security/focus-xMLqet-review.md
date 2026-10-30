# Mac focused acceptance: transferable evidence and panel map

Original ZIP preserved byte-for-byte. SHA-256: `66bc705a5d6390d3e591473bd8bb018aa673569c31a07d631abf5719b8bdc804`.

Application image: `sha256:4e3a0339cb5e1465701f757ca136039c369ab96fa672401a938e3efa0e5467d8`. Harness: `b78a23a45510ed5628da4ca0f8f603511d70435d`. **Overall FAIL retained. Acceptance/security approval pending.**

## Both collection errors

In `grafana-post-reload-query-responses.json`, zero-based entries `[0].error` and `[1].error` each record:

```text
response.json: Protocol error (Network.getResponseBody): No resource with given identifier found
Response body is not available for a response that was navigated away from. Read response.body() before triggering any navigation.
```

These are Playwright response-body retrieval errors, not recorded HTTP/query error responses. The harness used shared response/read arrays across navigation; late callbacks can contaminate the post-reload array. Original error entries contain no URL, request ID, HTTP status, query expression or timestamp, so the exact two requests/panels and their navigation epoch cannot be attributed. Do not invent that attribution or discard these failures. Twelve other entries have HTTP 200 and no recorded query errors; both question recovery cases PASS.

## Required panel mapping

All filenames below are relative to the unchanged ZIP. `R` means `grafana-post-reload-query-responses.json`; pointers are zero-based. Mapping uses executed PromQL, not response order. Machine-readable map includes exact expressions and DOM/screenshot hashes.

| Panel | DOM capture | Screenshot | Query response in R |
|---|---|---|---|
| 1: Service scrape status | `grafana-panel-1-dom.html` | `grafana-panel-1.png` | `/2/body/results/A` |
| 2: Backend HTTP requests / second | `grafana-panel-2-dom.html` | `grafana-panel-2.png` | `/3/body/results/A` |
| 3: Upload responses by status / second | `grafana-panel-3-dom.html` | `grafana-panel-3.png` | `/4/body/results/A` |
| 4: Upload request duration p95 | `grafana-panel-4-dom.html` | `grafana-panel-4.png` | `/5/body/results/A` |
| 5: Successful logins / second | `grafana-panel-5-dom.html` | `grafana-panel-5.png` | `/6/body/results/A` |
| 6: Failed logins / second | `grafana-panel-6-dom.html` | `grafana-panel-6.png` | `/7/body/results/A` |
| 7: Retrieval duration p95 | `grafana-panel-7-dom.html` | `grafana-panel-7.png` | `/8/body/results/A` |
| 8: Gemini requests by outcome / second | `grafana-panel-8-dom.html` | `grafana-panel-8.png` | `/11/body/results/A` |
| 9: Gemini duration p95 | `grafana-panel-9-dom.html` | `grafana-panel-9.png` | `/9/body/results/A` |
| 10: Gemini reported tokens / second | `grafana-panel-10-dom.html` | `grafana-panel-10.png` | `/10/body/results/A` |
| 11: Backend process memory | `grafana-panel-11-dom.html` | `grafana-panel-11.png` | `/12/body/results/A` |
| 12: Backend process CPU | `grafana-panel-12-dom.html` | `grafana-panel-12.png` | `/13/body/results/A` |

All 12 screenshots were visually inspected: service status shows both jobs at 1; remaining panels contain plotted values/series. Some percentile panels have only short recent samples; this establishes synthetic rendering, not performance targets or production monitoring reliability. Each panel also has live DOM evidence. Original failed result remains authoritative pending reviewer disposition.

## Preserved history and limitations

The ZIP includes `original-focus.66Jlsq.zip` (SHA-256 `85dd9a97ef9558cdc0efc3f826d2add0c14353a91853ed2592d879e252dc4b26`) and `original-focus.d0yA5Q.zip` (SHA-256 `f44a1f1cfedd91268caca2c7a89c5849173a4e0f46f9aa57e11bfca5be0a6adc`); both nested hashes independently verified. `command.json`, `bootstrap.log`, scripts, browser/container logs, results, before/after inventories, live answer responses, DOM and screenshots are retained. Existing inventories matched, no synthetic objects remained. Inventory equality does not hash preexisting volume contents.

Mac executed the tests; Team Codex independently inspected supplied artifacts, not re-executed the image. Prometheus/upload passes are retained from earlier attempts and not claimed rerun. Actual RunPod HTTPS/storage, full Compose and security clearance remain separate. Remaining 137 original security ledger entries remain open. No rebuild, merge, registry publication, deployment or existing-data change.
