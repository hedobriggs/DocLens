# RunPod monitoring readiness — source versus image versus provider

**New candidate source:** `75ffb2f0c9d966ca31f6b4024461b9bd8f90b565`.
Includes the separate CPU dependency candidate `5b83917c044d8b648032a3930a3399ef5c26dfcf`
and subsequent UI/session changes. **No new final image built; no candidate registry
digest exists.** Security release block remains. Do not deploy an earlier digest
as though it contained these changes. This report changes no monitoring code.

## Confirmed source configuration

| External HTTP service | Purpose | Private destination / authentication |
| --- | --- | --- |
| 3000 | DocLens | Frontend authenticates dashboard and API requests |
| 3001 | Grafana gateway | DocLens authentication; upstream raw Grafana loopback13001 |
| 9090 | Prometheus gateway | DocLens authentication; upstream raw Prometheus loopback19090 |

Dockerfile EXPOSE and template HTTP-service ports match3000/3001/9090. Supervisor
starts the two authenticated gateway listeners, while raw monitoring services,
backend8000 and Qdrant6333/6334 remain private. Anonymous monitoring cannot proxy
raw routes or spoof identity. Each port hostname authenticates separately with
host-only Secure/HttpOnly/SameSite cookies; no parent-domain cookie or secret token
in cross-host links. Root URLs redirect to the appropriate UI after login.

The Grafana Back to DocLens absolute link is generated from trusted Pod metadata
(or validated operator origin) at startup, preserving configuration on recreation.
Lacking an origin, it is omitted rather than displaying a broken/invented link.
Monitoring failure is designed noncritical; core failure still stops the container.
These are source behavior and previously reviewed local design, not confirmation
that the current running Pod has the desired image/listeners.

## Exact image and earlier acceptance records

| Scope | Exact reference | What it establishes |
| --- | --- | --- |
| Current source candidate | 75ffb2f0c9d966ca31f6b4024461b9bd8f90b565 | Source configuration only; imageID/digest **not available** |
| Accepted Intel Mac direct-image run | Source32516c104e98c8bdba1f416dd9b3b80294872a2e; user-reported local imageID `sha256:6b46513130ae283ce1da9ac3de0068be3abfe0d8fd097966e2a912859c1c8b55` | Reviewer accepted documented local functional run; does not accept later UI/dependency changes or provider tests |
| Older published d909540 image | `hedobriggs/doclens@sha256:fcb248296c91f711615a983f0c3ed1ec1fcc2a4d7322681d0a85631a982609a4`; local configID `sha256:ce23cbb8278ab8ede485603d606340c065df280202788c959517a15079329f27` | Historical image only; predates dedicated one-click3001/9090 gateway correction and exposes3000 in its Dockerfile |

The Mac ZIP `DocLens-Mac-acceptance-32516c1.zip`, SHA256
`fd4fea7b744313bd97818aa1f51e0d1013a1b47ef33bec6f8f6acdb565edb2ef`,
was transferred by the user to the reviewer and accepted there. Its original
files are not present in this workspace and are not mislabelled as this report's
maintainer-generated ZIP. Retained earlier cloud navigation evidence lives in
this directory's evidence.zip; its README distinguishes fixture from final-image
acceptance. The older published image now also has a historical SBOM/scan in the
separate dependency-security CPU evidence, including unresolved findings.

## Executed now and not executed

10 RunPod contract checks and8 gateway checks pass. Full commands/results under
`readiness/` in evidence.zip. They verify template/source configuration, auth/root
routing/header handling, cookie attributes and dashboard-origin generation.
They do **not** start the new full image or demonstrate actual RunPod HTTPS.
Current UI session/visual evidence is in the separate session-ui review directory.
Current complete Python3.11 CPU graph evidence is in dependency-security.

Current Docker host uses VFS and has only5.5GiB free. No unsafe ENOSPC build
attempt, unrelated deletion or paid provisioning. Exact source must be built on
an authorized existing host with sufficient disk, then its actual ID/digest and
SBOM/scan recorded. Do not borrow either historical image ID for that result.
Full direct-image/Compose live monitoring, provider, persistence and failure
acceptance is still required for the latest candidate.

## Actual RunPod gate — pending, requires separate authorization

Use a fresh synthetic-data trial with approved immutable image digest, private
secrets, attached storage mounted at/workspace and displayed cost approved before
any paid launch. Do not attach the existing application/customer volumes or
reset saved configuration to get tests passing. No current Pod was changed here.

1. Use all three default HTTPS service links (3000,3001,9090), no manual suffix.
   Verify frontend password login, anonymous rejection, separate monitoring
   logins, protected Grafana/Prometheus APIs, dashboard JS/CSS/assets/query results,
   actual scrapes, host-only cookies and Back to DocLens navigation. Verify private
   raw services are not externally reachable; do not expose13001/19090/8000/6333.
2. Upload synthetic PDFs, ask live Gemini the known-five-employer counting question,
   and check answer/citation identities. Check invalid upload/replacement recovery
   and session expiry UI. No customer document/provider key in evidence.
3. Capture point/payload/publication/citation, session and monitoring-history
   snapshots. Prove preservation through actual Pod stop/start and forced restart
   with the same attached synthetic volume/secrets. No automatic reset, data
   migration or deletion. Verify actual volume quota/headroom, not shared physical
   filesystem capacity. Record failures and recoveries without overwriting evidence.
4. Monitoring failure must leave DocLens usable; core-service failure must retain
   expected shutdown. Measure whole-stack CPU/memory/disk and health responsiveness
   under existing limits. Record actual provider/Pod/image/config IDs and cost.

**Local acceptance is not actual RunPod acceptance.** Request independent review
of exact source/image/evidence before requesting execution approval. Security
release clearance, merge, publication and deployment are separate decisions.
