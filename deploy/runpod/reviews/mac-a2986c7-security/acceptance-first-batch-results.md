# Baked-image Mac acceptance: first batch artifact inspection

Exact image sha256:4e3a0339cb5e1465701f757ca136039c369ab96fa672401a938e3efa0e5467d8, linux/amd64. Application source 299f3b48bbcd1058845ce14f528fba553d68a783; host driver b68a50f8b738f338cfe7acf566f9b8a28c36482a. ZIP acceptance.vW5s1h.zip SHA-256 a611b5f31ac4857fa1fb4a1025c2391f1914d533a0202b2cbc0966a0a04d0719.

## Provenance and independently inspected checks

Mac-executed/user-supplied test run. Team Codex independently inspected ZIP integrity/checksum; embedded driver equals committed version; three test-module inputs equal exact source 299f3b4; command arrays target exact approved image; recorded exit files and result JSON agree; browser JSON/screenshots inspected; before/after inventories identical. Docker execution itself was NOT independently repeated on cloud host. Basic probable Gemini-key pattern check found no matches; driver portable ZIP redaction does not imply a comprehensive secret audit. ZIP remains unchanged, including original labels private-raw (these are the driver's portable copies).

Host: macOS 15.7.9 Intel x86_64, Docker 8 CPUs/4101181440 bytes memory (~3.82 GiB), host Python 3.9.6, Node 25.8.0, npm 11.11.0. This is not Safari/VoiceOver or actual RunPod coverage. Host browser adapter and full driver/commands are in ZIP. No image rebuild or runtime application/model/package bind substitutes. TLS test-only modules ran in tmpfs against baked dependencies.

## Executed outcomes

| Gate | Evidence/result |
|---|---|
| Native imports, embeddings, reranking | PASS, baked-native.exit 0. CPU torch 2.13.0+cpu; SQLite 3.46.1; expected Aster top rank; five finite 384D embeddings. Model revisions unchanged. |
| PDF parsing | PASS, real PyMuPDF synthetic PDF round trip plus actual five-page app upload. |
| TLS/config/framework regressions | PASS, 13 tests / 2.482s; default untrusted-CA rejection, explicit synthetic CA acceptance, wrong-host rejection, HTTP/2, lock/config and framework cases. |
| Startup validation/auth/access boundaries | PASS, missing storage/secrets refusals, wrong login/anonymous upload rejection, login/cookie flags, private API/Qdrant listeners and raw monitoring route denial. |
| Actual upload and failed replacements | PASS, real-model five-page indexing, malformed and 301-page replacements rejected while exact old records preserved. |
| Live Gemini and citations | PASS: --live-answers was requested; harness asserts all five employer names and citation page set 1..5, including post-restart response. Responses tested via API; answer UI rendering and verbatim response text are not independently established by screenshots. |
| Browser monitoring/auth/assets | PASS asserted for all three root links and independent form logins, reload sessions, host-only cookie boundary and Back to DocLens destination navigation/assets. Browser JSON has no failed assets. |
| Metrics/dashboard queries | PASS as defined by harness assertions: real app/Qdrant metrics, provisioned dashboard queries, spoof denial and settings write. Full final panel rendering is NOT established by supplied screenshots (see below). |
| Restart/recreation persistence | PASS, interrupted startup, forced/graceful restart and fresh container recreation preserve exact point/payload/publication/citation identities, configuration/session and historical metrics checks. |
| Failure isolation/shutdown | PASS, Grafana failure leaves upload/API usable and recovers after restart; Qdrant failure terminates container. |
| Existing-object preservation | Before/after 5 pre-existing stopped containers and 9 volumes identical; zero remaining test containers/volumes. Existing volume content hashes not collected; preservation evidence is isolation plus unchanged inventory, not a new audit of customer data. |

All five stage exits are zero (including host browser setup). No unexpected failed stage or corrective rerun in supplied batch. Expected negative responses and deliberate component kills are acceptance cases, not failures hidden from reporting. Logs retain Starlette/httpx TestClient deprecation and cryptography non-positive certificate serial warnings; these did not fail tests and no additional upgrade is initiated here.

Resource observations for this synthetic five-page run: PERSISTED_BYTES 345832226; MEMORY_PEAK_BYTES 3041173504; one observed resource sample 2.21 GiB /3.82 GiB, CPU 7.97%. These are harness measurements, not independent profiling or supported large-document limits. No limits increased or customer document tested.

## Screenshot/readiness limitation

Grafana screenshot shows panel containers with a Cancel/loading state and no rendered series. Browser source waits for qdrant before reload but after reload waits only for dashboard title before screenshot. Therefore the passed asset/auth/query checks do not prove the captured reload's final rendered panels; retain this screenshot unchanged and obtain a narrow data/render-condition-based capture (no arbitrary sleep, no rebuild). Prometheus screenshot shows query UI with no query executed in browser; API queries were exercised separately. DocLens screenshot shows home; live answers were exercised by API, not answer-render screenshot. These are explicit evidence scope limitations, not established application defects.

## Still pending

- Baked frontend expiry during upload/question, busy-state exit, actionable Sign in and successful recovery. Restart persistence does not certify expiry recovery.
- Narrow Grafana rendered-panel evidence after reload, and browser query rendering if claimed.
- Full Compose monitoring acceptance remains separate/unexecuted here.
- Actual RunPod HTTPS/browser/attached-storage; Safari/VoiceOver and customer document acceptance are not covered.

results.json correctly sets complete_acceptance=false. Independent review is required before closing functional gates. Original two scoped security dispositions stand; remaining 137 original entries stay OPEN and candidate 120 high scan occurrences still block broad security clearance. Grafana Go-source provenance limitation remains unchanged. No merge, publication, deployment, paid resource, migration, existing-data change or application fix/rebuild.
