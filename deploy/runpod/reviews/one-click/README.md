# RunPod “Back to DocLens” correction — independent re-review requested

Repository: `hedobriggs/DocLens`; branch: `fix/runpod-monitoring-links`.
Application review baseline: `f8577fa6237852db48bb4b8450484b7e3b8688ec`.
Git parent: evidence-only `218781e4508e5ca80b35cb07a0297dfe482b8c6d`.
The exact follow-up SHA is the commit containing this report, supplied in the
maintainer handoff. No merge, publication or deployment is authorized/performed.

## Problem and correction

The shared Grafana dashboard links to `/dashboard`. On its dedicated RunPod
hostname, Grafana interprets that as `/monitoring/dashboard`; it cannot open the
DocLens workspace. A server redirect alone is insufficient because Grafana's
SPA can intercept a relative link before the gateway handles it.

At startup, RunPod now generates a dashboard copy under
`/run/doclens-monitoring/dashboards`, pointing **Back to DocLens** directly to
`https://<RUNPOD_POD_ID>-3000.proxy.runpod.net/dashboard`. An optional trusted
`DOCLENS_PUBLIC_ORIGIN` supports custom domains or local trials. Its validation
rejects credentials, paths, query strings, fragments, invalid ports and external
plain HTTP. HTTP is allowed only for loopback hostnames. Request Host/forwarded
headers do not choose the destination. With no provider ID or configured origin,
the link is omitted rather than advertising a guessed/broken address.

The generated file is atomically replaced and read-only, with explicit directory
permissions so Grafana's separate UID can read it even with restrictive umask.
The RunPod-only provider path/default-home path use that generated copy. The
shared Compose dashboard, dashboard UID/panels and its relative link remain
unchanged. Generation repeats at every startup/recreation; it does not write
application volumes or migrate/reset any data.

The browser navigates to DocLens without forwarding tokens or changing cookie
scope. DocLens enforces its own host-only session and asks for login when none
exists. Monitoring proxy/authentication logic and private service ports are
unchanged. No backend/frontend application source, upload limits, credentials,
originals, Qdrant records or citation identities were changed.

## New maintainer-executed evidence

| Check | Outcome |
| --- | --- |
| Gateway/configuration regressions | 8 passed |
| RunPod contracts | 9 passed |
| Compose monitoring/authentication/privacy contracts | 5 passed |
| JS/Python syntax and base-to-head whitespace | Passed |
| Actual Dockerfile provider-path sed expression on temporary YAML | Passed; generated directory matches |
| Real Grafana browser before case | Failed as expected: remained on monitoring hostname `/monitoring/dashboard` |
| Real Grafana browser corrected case | Passed link click, separate DocLens login, workspace and assets |

The browser used different `grafana.localhost` / `doclens.localhost` hostnames,
real form logins and no injected cookies or API stubs. It verified no DocLens
cookie before navigation, no monitoring-cookie transfer, a host-only
Secure/HttpOnly DocLens cookie after its own login, and 9 loaded Next assets.
Grafana scripts/styles loaded without failures. The final focused rerun restarted
Grafana against the SAME uniquely named synthetic database before loading the
corrected configuration. All fixture containers/network/volume were removed.
Screenshots and complete saved logs are under `back-link/` in the ZIP.

Failures retained: the original route regression returned 404; a redirect-only
attempt passed units but failed browser navigation; an intermediate fixture
permission error exposed the need for explicit directory permissions. Those logs
and the subsequent passing reruns are retained. The final unit suite verifies
repeat generation under umask 077 and unchanged dashboard UID/panels.

## Scope and remaining gates

The reviewer reported independently passing all 63 baseline checks, image builds,
browser logins/assets, authentication and local restart/recreation preservation
on `f8577fa`. Those results are attributed to Reviewer Codex; they were not
repeated or presented as newly executed maintainer results.

This follow-up browser fixture uses real Grafana image
`sha256:45900b2eda7da0cbda80b9025e446147d9085fee71675ba86a48a1cad34e4c8a`
and existing production frontend image
`sha256:60f8893a7727fa08a6457ad4b255b9d47a2da103270484651dd69e70611ac30e`
with the unchanged Compose internal Grafana destination. It runs the current
production gateway/configuration functions. Raw Grafana has no published port
and trusts only that frontend. It mounts only synthetic dashboard/provisioning
fixtures read-only; it does NOT substitute files into a final RunPod image.

This is a **focused navigation/configuration regression**, not a new final-image
or whole-stack acceptance run. No backend, Qdrant, Gemini or documents were
started/admitted for this test. The final follow-up image was not rebuilt here;
its build/startup verification belongs in independent re-review on a host with
sufficient disk. HTTP localhost Secure-cookie behavior is NOT provider HTTPS
validation. Actual RunPod HTTPS/browser and attached-storage acceptance remain
pending. Native Safari/VoiceOver were not tested.

## Reviewer handoff

Review the follow-up diff against `f8577fa`, build the final image, rerun the
focused back-link browser check, and inspect the retained failures/reruns.
Keep publication/deployment approval pending until the required gates pass.
Main, published images, the Mac and existing application data remain unchanged.

Download [evidence.zip](evidence.zip). Prior evidence is retained alongside the
new `back-link/` commands, fixture source, logs, results and screenshots. The
fixture accepts `DOCLENS_REPO=/path/to/checkout` for reproduction. No customer
content, real credentials or session-token dumps are included.

SHA-256: `3a6a0a84119322bca96140240ad52855b98dfa23f9a47153952791d212570d96`.
