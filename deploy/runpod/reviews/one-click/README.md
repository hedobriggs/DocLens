# RunPod one-click monitoring candidate — review pending

Application baseline: `d9095402cf393aa75f790c8e13b15ee215575412`.
Git parent: evidence-only `30db78736a292c525ab1cadf1daf9773e32075e2`.
Branch: `fix/runpod-monitoring-links`. The exact candidate commit is the commit
containing this report; maintainer handoff supplies its full SHA.

## Behavior and boundary

The template and image expose 3000 (DocLens), 3001 (Grafana gateway), and 9090
(Prometheus gateway). Both monitoring root links redirect automatically to the
correct service page. Anonymous pages redirect to a same-host login form; APIs
reject missing/invalid DocLens sessions. Each RunPod port hostname needs its own
login with the same admin credentials. No parent-domain cookies, token transfers
or raw monitoring authentication bypass were added.

The gateways have a fixed loopback frontend upstream, 16 concurrent requests
per listener, 2 MiB request bound and read/upstream timeouts. They do not load
private settings. Existing frontend session validation remains the authority;
spoofed Grafana identity/internal authorization headers are stripped. Grafana
continues requiring the trusted frontend proxy. Its raw listener moves to
127.0.0.1:13001 and raw Prometheus to 127.0.0.1:19090. Do not expose those ports.
Compose keeps its previous internal destinations and published ports.

Startup, gateway script, template ports and RunPod-only datasource URL are baked
into the image. Persistent paths, UIDs, matching configuration checks, installation
lock, session secret, upload/resource limits, data/citation identities and core
failure behavior were not changed. No migration or reset is added. Preserve the
same volume and secret bindings when a separately approved recreation occurs.

## Executed evidence

Final built local image (not published):
`sha256:72ee8d9178cda195de99457618b3bf2c563dc4ca94fbd5074cc0e3e05a3bf99c`
(linux/amd64, 3,944,530,492 reported bytes). The unchanged backend input is
`sha256:6630a9b44c22c047906d1aaba571f39e4e72d075921297dbc480ea98d01140b5`.
Frontend source hashes were checked against the updated packaging manifest.
The frontend production build and final RunPod assembly both passed.

Maintainer-executed checks: **63 passed**:

| Check | Result |
| --- | --- |
| Gateway network/framing/identity/cookie regressions | 4 passed |
| RunPod packaging/startup contracts | 9 passed |
| Compose monitoring/authentication/privacy contracts | 5 passed |
| Bootstrap | 9 passed |
| Portable packaging | 6 passed |
| Portable launcher | 11 passed |
| Controlled-inference document coverage | 6 passed |
| Controlled-inference upload/preservation regressions | 13 passed |

Changed frontend proxy ESLint, JS/Python syntax and whitespace checks passed.
The last two Python suites ran in an isolated host-test environment, not the
production dependency environment; they use synthetic PDFs and controlled
inference. They do not establish performance or live Gemini correctness.

## Failures and pending gates — do not approve deployment

* First build hit a read-only buildx config path; writable buildx config rerun
  passed. Both initial failure and passing build logs are included.
* First direct-image run failed before application startup because VFS Docker
  exhausted disk. Its assertion and evidence-writer failure are retained. The
  original captured Docker stderr was not preserved by that initial assertion;
  the harness now includes it and attempts cleanup even if log writing fails.
* Current-task orphan copies/cache were reclaimed and the image rebuilt.
  A subsequent resource guard stopped testing: about 7 GB free is insufficient
  for two 4.12 GB allocated VFS root copies plus headroom. The final image has
  **not successfully been started/tested directly**. No successful browser,
  dashboard-asset, restart or recreation result is claimed for it.
* An extra default-host coverage run lacked qdrant_client; isolated dependency
  setup and corrective rerun passed. An extra root Compose run lacked the
  default compose-auto frontend tag; it cleaned its own project, and full
  Compose runtime acceptance is **not claimed passed**.
* Actual RunPod HTTPS hostnames, provider login/cookies, storage locking and
  stop/start/forced-restart persistence remain pending. No RunPod was changed.
* Native Mac, Safari, VoiceOver and live Gemini were not rerun in this change.

`tests/runpod_links_browser.cjs` is a real-browser, no-cookie-injection/no-stub
suite for the three root links and assets. `tests/test_runpod.py --browser`
includes actual public monitoring queries, simulated TLS-offload Origin checks,
forced/graceful restart, exact synthetic document/configuration identities,
container recreation against the same volume, monitoring failure and core
shutdown checks. These new acceptance paths are **pending execution**, not
passing evidence. Reproduction commands are in the evidence ZIP.

Before merge/publication/deployment approval: independently inspect the diff,
finish final-image acceptance with sufficient disk, inspect its failures/reruns,
and review actual RunPod validation as a separate explicit gate. Main, published
images, the Mac installation and existing application data are unchanged.

## Transferable evidence

Download [evidence.zip](evidence.zip). It contains safe commands, complete saved
logs/outcomes (including initial failures), image/source hashes and build details.
No secret values or customer documents are included.

SHA-256: `71b38245fc4d72d3c1ddf9b0b4a705f14504fa2da4e069841186c867a2aba8bc`.
