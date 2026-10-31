# One prioritized security-release plan

Status: PLAN ONLY. Local synthetic functional milestone CLOSED under the user-conveyed acceptance recorded in `local-functional-acceptance-20261031.json`. Exact accepted image `sha256:4e3a0339cb5e1465701f757ca136039c369ab96fa672401a938e3efa0e5467d8`; evidence `20f497f70f040fe7aaa3c42371dc3570cb85d793`. This record completes the decision requested by FINAL-LOCAL-READINESS.md; it does not supersede that report's limits or change earlier failed results. No rebuild/test repeat occurred. Merge, registry publication, deployment and security clearance remain BLOCKED.

## Ground truth and closure rule

Original ledger:139 immutable occurrences,2 narrowly accepted dispositions,137OPEN. Candidate scan:0critical/120high occurrences,44Debian +7Grafana core +69bundled Grafana binaries, plus medium/low/unknown findings. Counts refer to different populations and must not be subtracted from one another. `security-release-component-worklist.csv` enumerates all120 high occurrences with exact target, package, installed version and scanner-reported fix field; every row starts OPEN. These are the accepted2026-10-29 scan results, not a new scan or a claim that vendor fixes remain current today.

For every occurrence retain stable original ID or assign a new candidate-occurrence identity; map original→current target/package/binary and track new findings too. Closure requires either (a) authenticated vendor fix/backport evidence mapped to the exact installed bytes plus relevant regression evidence, or (b) independently approved advisory-specific non-applicability supported by code/build/runtime evidence. Missing packages, renamed packages, scanner disappearance, authentication or disabled features alone do not establish closure. No-fix means OPEN unless defensible independently reviewed applicability evidence establishes a disposition. No suppressions or generic waiver to make the scan green. Keep both prior scoped SQLite/core-libz decisions exactly as recorded; no extension to bundled copies.

Each component submission: source commit, per-advisory before/after status, vendor evidence URL/revision and captured hash, exact binary/package mapping and affected path, initial failures/corrective results, regression commands/results and limitations. Reviewer decides dispositions before merge approval. No implementation is authorized merely by this plan.

## Priority1 — Grafana core and bundled binaries (76 high occurrences)

Why first: one vendor component supplies most current high occurrences and is part of authenticated network-facing monitoring. Prefer a supported official vendor release containing fixed dependencies over maintaining a custom Grafana fork or rebuilding Go in place. Verify whether such a release actually exists before selecting any digest. Scanner fix fields are leads, not vendor verification.

Evidence targets include opt/grafana/bin/grafana and13bundled plugin executables; exact targets are in the worklist. Recorded installed modules/fix leads include:

| Component | Recorded version and examples | Required remediation/disposition evidence |
|---|---|---|
| Go stdlib across binaries |1.26.6/1.26.7/1.26.9/1.27.1; CVE-2026-111943,78667,78669,97031 | Verify official Go advisories and compatible fixed branch; candidate Go build info and vendor provenance for EVERY affected executable. Updating the outer container OS/Go executable cannot repair statically linked binaries. Scanner leads include1.26.10/1.27.3; verify branch-specific applicability. |
| golang.org/x/net |0.58.0/0.59.0; CVE-2026-78669 | Verify upstream fix0.60.0 lead and exact vendor module build; assess reachable parsing/proxy paths individually. |
| kin-openapi |0.144.0; CVE-2026-100349,100351–100354 | Verify upstream fixes through0.149.0 and that vendor binaries contain them; assess affected schema/document parsing entry points. |
| go-jose/v4 |4.1.4; CVE-2026-116587 | Verify4.1.6 lead and actual auth/token call paths/build metadata. Preserve current authentication boundary. |
| gRPC |1.83.0; CVE-2026-84304/84445 | Verify compatible fixed branch1.83.2 lead and vendor incorporation; evaluate server/client usage per binary. |
| Tempo dependency | pseudo-version1.5.1-0.20260910130453-bcfe9f230c1d; CVE-2026-21728/28377 | Map commit lineage/cherry-picks to affected code. Do not numerically compare pseudo-version1.5.1 to the scanner's2.x fixed versions and call it resolved. |

Keep modernc embedded-SQLite provenance limitation visible. A claim for the system libsqlite3 or Qdrant library does not close Grafana's static copy. Disabled plugin runtime routes may reduce exposure, but do not remove affected bytes; any code-removal proposal must prove no dependency/feature break and be reviewed separately. Do not drop needed Prometheus functionality or any of the12dashboards to evade findings.

Completion: independently accepted vendor digest/source selection, all76 current occurrences individually remediated or explicitly disposed, per-binary SBOM/build-info/hash verification, auth/spoof/raw-service privacy regression, root-link/assets/back-navigation and all12panel/query regressions on any changed image. Preserve session/configuration/metrics history with synthetic upgrades; never attach existing customer volumes. If no supported vendor release exists, those rows remain blocked; do not imply an available fix.

## Priority2 — Debian runtime (44 high occurrences; no fixed version reported in accepted snapshot)

| Family | Current evidence | Required next evidence |
|---|---|---|
| util-linux and split packages |2.41.5-0+deb13u1 family; CVE-2026-76642/78408/78409/78410 across bsdutils,libblkid1,liblastlog2-2,libmount1,libsmartcols1,libuuid1,login,mount,util-linux | Authoritative Debian tracker/source patches and upstream advisory affected functions; map each package to actual code/files/callers. Distinguish source-level duplication from actual affected binaries without bulk-closing rows. Verify vendor backport or pin supported fixed base when available. |
| acl |libacl1 2.3.2-2+b1; CVE-2026-54369 | Exact Debian source/backport and filesystem/ACL affected-path evidence; preserve container permissions. |
| ncurses/tinfo |6.5+20250216-2; CVE-2025-69720 | Source patch/build attribution and affected terminfo/input path; assess retained linked copies before suggesting removal. |
| systemd/udev libraries |257.13-1~deb13u1; CVE-2026-16742 | Assess actual library APIs used, not whether systemd daemon runs. Require vendor fix or precise non-applicability. |
| perl-base |5.40.1-6+deb13u1; CVE-2026-9538 | Vendor advisory/patch and runtime/package-script usage. Remove only if proven unnecessary and independently reviewed; no blind apt autoremove. |

Use authenticated signed Debian Release→Sources/Packages→source/deb checksums and active patch series, retaining verification failures. Proposed fixes must be compatible with Python3.11 and native wheels. Do not weaken permissions or blindly upgrade libc. No reported fix is not a reason to close findings, regardless of network exposure.

Completion: all44 current OS high rows have reviewer-approved specific evidence. Base/deb changes preserve model revisions, upload limits, auth, data/citation identities. Any changed native/OS graph must pass imports/inference, PDF/TLS/config/auth and relevant isolated persistence tests. If vendor support is unavailable, release remains blocked pending separately reviewed policy decision; this plan does not grant an exception.

## Priority3 — Reconcile the137original entries and opaque copies

Perform this evidence work while vendor candidates for Priorities1/2 are identified; it need not wait for a rebuild. Keep original ledger and decision history immutable; append decisions only after independent approval. Map all original occurrences into the current inventory, including disappeared/replaced packages and newly introduced findings.

- Preserve libssl3→libssl3t64 mapping; verify each OpenSSL backport against exact source, installed libssl/libcrypto and actual TLS path. Separately identify Node statically linked OpenSSL and wheel-bundled copies.
- Six util-linux-extra package gaps do not prove removal of code: map to mount/libmount,libblkid,nsenter/util-linux as recorded. Current package family assessment in Priority2 must cover original occurrences too.
- For18original unreported occurrences, use `unreported-18-advisory-assessment.csv`:14util-linux occurrences (53613/53615),gzip41992,SQLite11822/11824,OpenSSL84782. Review individual active backports/affected functions. CVE-2026-53613 residual fallback paths remain unresolved; do not accept version-only closure. SQLite11822 full fix lineage remains incomplete;11824 origin evidence cannot automatically close11822.
- System SQLite3.46.1, Qdrant's separate3.46.1 library, Grafana embedded SQLite and Node SQLite3.51.3 require copy-specific hashes/engine/source provenance and advisory applicability. Keep no-fix SQLite50812/50813,2021-45346,2025-70873 open until supported disposition/fix. A result for CVE-2025-7458 is not blanket SQLite clearance.
- Original MiniZip disposition applies only to exact assessed original Debian core-libz. Assess remaining zlib advisories and any bundled MiniZip independently; retain omitted-path/symlink/native-inventory limits. No marker hit is not proof of absence.
- Retain original Python/ML no-fix PYSEC findings and exact model revisions. Do not repeat broad Torch/transformer upgrades just because scanner output changed; first prove affected serialization/model-loading path for the pinned exact stack. Model downloads/pickle policy and native wheel copies need actual evidence. Runtime import success alone is not a security disposition.

Completion: each of137original OPEN IDs has a reviewer-approved resolved or precisely not-affected decision, or is explicitly still blocking. No migration of identities and no closure solely from scan absence. All opaque-copy attribution limitations that affect a disposition must be resolved or remain blocking. Reconcile new scan entries so no current blocker is lost just because it was absent from the original ledger.

## Priority4 — Remaining severities and small dependency patches

Triage medium/low/unknown findings by component and reachable path; avoid treating severity as risk proof. In the accepted candidate snapshot filelock3.20.3 retains CVE-2026-112909/112910 (medium; scanner fix lead4.2.1). Verify vendor advisory, compatibility and fixed package provenance; a small separately reviewable pin patch must retain lock contention/timeout/symlink/TLS/config protections. Do not automatically rewrite the entire ML/native graph. Assess other Debian,Node,Python,Go findings and new advisories with the same evidence rule. Unexpected new critical/high findings take priority immediately.

Completion: every remaining finding has documented triage and proposed action; any residual risk requires explicit independent security disposition under the release policy. This plan grants none. Critical/high blockers cannot be hidden among lower severities.

## Priority5 — One security candidate and release evidence gate

After compatible source patches are reviewed and any implementation/build authorization is explicit, assemble one uniquely tagged candidate on an authorized existing host with adequate headroom. No rebuild now. Do not change the accepted image/tag in place. Pin verified base/vendor digests and dependency graph; preserve model pins/limits/recovery/data identities. Snapshot test fixture state only; preserve existing installations/volumes. Avoid repeated full builds for each evidence-only decision.

Record exact source/tree, build commands/options/output including failed builds, image config/layers/local ID, SBOM with native/Python/Node/Go inventories, scanner version/image and raw unfiltered whole-image scan, database version/metadata/hash and signed vendor evidence. Refresh scanner DB for this new security candidate in an isolated cache; retain the old accepted scan unmodified. Reconcile original ledger plus all current/new findings. Scanner success or0critical alone is not release approval.

Changed runtime bytes are a specific reason for relevant regressions; this does not reopen or erase the accepted4e3image milestone. Choose tests by change impact: Grafana-only changes require monitoring auth/assets/panels/history; TLS/framework changes require TLS/auth/session/upload; native/base/ML changes require inference/PDF/resource/failed-replacement/citation tests and synthetic restart/recreation preservation. A final changed integrated image needs the applicable baked-image security/functional acceptance once. Keep previously passed unrelated checks as evidence; repeat only where a dependency/cross-component risk justifies it. Preserve failures and corrective reruns. Full Compose and actual RunPod HTTPS/storage remain separately pending, with separate execution authorization; no paid Pod under this plan.

## Explicit security completion criteria

1. Complete, reproducible original/current/copy-level mapping; immutable history preserved; no unreviewed disappearance or package rename treated as closure.
2. Every release-blocking critical/high occurrence (original/current/new) has independent advisory-specific approved remediation or supported not-affected disposition. No-fix/unidentified copies stay OPEN/blocking. Remaining severities have explicit triage and approved residual treatment, if any.
3. All vendor fix claims validated against exact installed code/build/package provenance, not merely scanner fix strings; Grafana's relevant embedded provenance gaps addressed.
4. Exact new candidate has complete SBOM/raw scan/database provenance and no undisposed blocking findings. Failed runs and fresh-scan differences retained.
5. Change-appropriate security regressions and final integrated synthetic acceptance pass on exact reviewed bytes, with commands/logs/screenshots/persistence identities and stated limits.
6. Reviewer issues a distinct security-release decision. User separately authorizes merge, registry publication and deployment; any actual RunPod/Compose acceptance required for the destination completes under separate authorization. None follows automatically from local functional acceptance.

If any criterion lacks evidence, explicitly name the blocker and keep the gate closed. The next useful work is vendor fix/applicability research for the76Grafana and44OS rows plus original-ledger reconciliation, not repeating the closed functional suite or starting another speculative rebuild.
