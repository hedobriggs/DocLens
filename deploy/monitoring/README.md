# DocLens monitoring

Prometheus collects application statistics; Grafana shows the charts. Sign into
DocLens and choose **Monitoring** in the header. No separate Grafana password or
public monitoring port is needed. **Back to DocLens** returns to the application;
use DocLens's Log out button to end access.

## Mac / ordinary Docker server

Use the existing private `.env` and root Compose setup, then:

```sh
docker compose -f compose.yaml -f compose.monitoring.yaml up -d --build --wait
```

Stop this installation, keeping its documents and monitoring history:

```sh
docker compose -f compose.yaml -f compose.monitoring.yaml down
```

Do not add `-v`. Original Mac installations/volumes are not migrated. The root
Compose file still runs the application without monitoring if the overlay is
omitted. Metrics and Grafana use separate named volumes; neither mounts the
Docker socket. Keep the existing HTTPS setup for real browser sign-in.

## RunPod

The updated single-container Dockerfile includes Prometheus, Grafana and the
bundled Prometheus datasource plugin. Build dependencies/models into the image
on a Docker-capable server using `deploy/runpod/README.md`; nothing installs at
Pod startup. The RunPod Docker build context is now the **repository root**.
The template enables `DOCLENS_MONITORING=1`; the same three existing private
DocLens/Gemini secret bindings are used. There is no new customer-facing password.

Only frontend port 3000 is public. API, Qdrant, Grafana (3001) and Prometheus
(9090) bind to loopback. Monitoring uses the same `/workspace` attached volume,
under `/workspace/doclens/grafana` and `/workspace/doclens/prometheus`, with distinct
UIDs. Application index/configuration/citation identities are preserved. Use a
fresh synthetic volume until an installation/update is separately authorized.

Grafana authenticates only through the DocLens gateway: a valid existing admin
session is required for every request. The gateway strips the DocLens cookie and
internal API key, overrides incoming identity headers, limits request bodies to
2 MiB, and bounds transfer/upstream time. Anonymous API requests return 401;
anonymous browser navigation returns to DocLens login. Basic/anonymous Grafana
login and signup are disabled. Grafana Live/WebSockets are disabled; charts poll.
Raw monitoring services must never be exposed or attached to untrusted networks.

RunPod derives a separate stable Grafana encryption key from the saved app secret;
Grafana does not receive that app secret or the Gemini key. Compose keeps its
random encryption key with its Grafana database and refuses a database lacking
its matching key. Preserve matched application configuration plus Grafana/Prometheus
data in any separately tested backup/restore procedure. No automatic migration,
credential reset or backup claim is made.

A monitoring process failure leaves DocLens available; monitoring health reports
degraded. Restart after correcting the cause. Core API/frontend/Qdrant failures
retain their existing stop/recovery behavior. An actual RunPod provider's response
to degraded container health is still unverified.

## Charts and bounds

Twelve panels cover scrape status, HTTP requests/uploads, successful/failed
logins, retrieval time, Gemini outcomes/duration/tokens and backend process memory
and CPU. Backend process usage is **not** whole-Pod or host usage. Upload duration
is HTTP timing, not durable-job progress. Routed HTTP metrics can omit rejection
before routing. Provider total tokens overlap prompt/completion; no billing cost
is inferred. A new or unused service may show No data; rates need multiple scrapes.

Images are pinned to immutable upstream digests: Prometheus 3.15.1 and Grafana
13.2.4. Automatic plugin downloads, update checks and analytics are disabled.
Prometheus keeps up to two days / a 256 MB block retention target, with bounded
query concurrency/sample count. WAL/head files add space beyond that target: it
is not a hard disk quota. Grafana database size and provider logs also need disk
headroom. Compose adds 256 MiB Prometheus and 512 MiB Grafana memory caps; RunPod
uses Go memory targets under the whole-Pod allocation. Upload/page/text/chunk
limits and application authentication remain unchanged. Cleanup never deletes
originals, document revisions or citations.

## Candidate validation and remaining gates

39 contract/bootstrap/packaging/launcher checks pass. The frontend builds and
lints. An isolated Linux amd64, 2 CPU / 4 GiB, synthetic single-container runtime
passed login/denial, five-page real-model PDF ingestion, failed/over-limit
replacement preservation, live Gemini answers/citations, authenticated Grafana
and twelve valid PromQL queries, API body-size protection, identity spoof denial,
CSRF-aware preference writes, forced/graceful restart history/config/data/session
preservation, monitoring-failure isolation/recovery and core-failure shutdown.
Chromium checked the desktop/mobile navigation (1280x800 and 375x812), an anonymous
redirect, actual browser datasource response and visible service data. HTTP-only
fixture cookie injection was used: this is **not** real HTTPS browser-login evidence.

Failures retained in external evidence: fixture/config permissions; missing bundled
Prometheus plugin; a preferences test using POST instead of PUT; and a contract
test needing numeric conversion of Compose memory values. Corrected reruns passed.
New-image build inputs include exact upstream runtime files and the compiled
frontend used by these tests; the image builds successfully. Runtime checks use
read-only packaged files in the approved core container because this VFS workspace
lacks disk headroom for a direct full-image container boot. That direct boot and
the complete Compose overlay startup are **not verified here**.

No physical Mac/Safari/VoiceOver, dense-document capacity, whole-8-GB-Mac resource,
actual RunPod HTTPS/upload/provider stop-start/forced-storage persistence or backup
restore claims. No limits increased, image published, paid Pod launched, main
merged, customer data admitted or Mac modified. Independent review and the missing
full-image/provider checks are required before declaring this ready.
