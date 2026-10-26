# DocLens monitoring

Prometheus collects application statistics; Grafana shows the charts. Monitoring
opens independently of the document dashboard. Sign into DocLens first, then
open the monitoring URLs in separate browser tabs. There is no dashboard control
or embedded monitoring view. No separate Grafana password is needed.

## Mac / ordinary Docker server

For a separately configured installation, enable the optional local URL overlay:

```sh
docker compose -f compose.yaml -f compose.monitoring.yaml -f compose.monitoring.local.yaml up -d --build --wait
```

- DocLens: `http://localhost:3000` (or the configured application port).
- Grafana: `http://localhost:8080/monitoring/d/doclens`.
- Prometheus: `http://localhost:9090/prometheus/query`.

Use `localhost` consistently so the signed-in session is shared across these
ports. `GRAFANA_PORT` and `PROMETHEUS_PORT` can change conflicting local ports.
These are loopback-only ports of the authenticated frontend gateway, not direct
access to raw Grafana or Prometheus. Anonymous API requests are rejected. Each
service remains on its private internal network. Without the local overlay,
use `/monitoring/d/doclens` and `/prometheus/query` at the normal app address.

A fresh single-container synthetic Mac trial can publish additional frontend
mappings `-p 127.0.0.1:8080:3000 -p 127.0.0.1:9090:3000` when it is created.
Do not replace or recreate an existing Mac installation to add these mappings;
use a separately reviewed trial procedure and new synthetic volume.

Stop an installation using the same Compose files with `down`, never `down -v`.
Application, Grafana and Prometheus data retain their separate named volumes.
Existing Mac installations and volumes are not migrated. No monitoring service
mounts the Docker socket. Keep HTTPS for real deployments; browser login on a
local HTTP address has browser-specific limitations.

## RunPod

The updated single-container Dockerfile includes Prometheus, Grafana and the
bundled Prometheus datasource plugin. Build dependencies/models into the image
on a Docker-capable server using `deploy/runpod/README.md`; nothing installs at
Pod startup. The RunPod Docker build context is now the **repository root**.
The template enables `DOCLENS_MONITORING=1`; the same three existing private
DocLens/Gemini secret bindings are used. There is no new customer-facing password.

On RunPod only frontend port 3000 is public; use the existing HTTPS address
with `/monitoring/d/doclens` or `/prometheus/query`, not new public ports. API, Qdrant, Grafana (3001) and Prometheus
(9090) bind to loopback. Monitoring uses the same `/workspace` attached volume,
under `/workspace/doclens/grafana` and `/workspace/doclens/prometheus`, with distinct
UIDs. Application index/configuration/citation identities are preserved. Use a
fresh synthetic volume until an installation/update is separately authorized.

Grafana authenticates only through the DocLens gateway: a valid existing admin
session is required for every request. Both monitoring routes use the same session checks. Prometheus is available at
`/prometheus/query` and uses a fixed internal destination as well. The gateway strips the DocLens cookie and
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

## Validation and review

The earlier monitoring baseline was directly tested as a final single-container
image and as a complete Compose stack using synthetic data. The managed test
host required a monitoring-only proxy override and backend CA trust; the initial
failure and passing rerun were retained. This does not prove compatibility with
arbitrary ambient proxy configurations.

The count/scroll/separate-URL correction is a new review candidate. Its exact
commit, image IDs, commands, failures and passing results are supplied in the
independent-review evidence, not inferred from the earlier baseline. Test-only
CA trust is not a source/binary substitution. No customer CV belongs in test
fixtures, logs, image contexts or review archives.

Actual RunPod HTTPS login/uploads, provider stop/start and forced-restart
attached-storage persistence remain separate gates. Native Mac, Safari and
VoiceOver coverage must be reported explicitly. No deployment or merge is
implied by successful local tests.
