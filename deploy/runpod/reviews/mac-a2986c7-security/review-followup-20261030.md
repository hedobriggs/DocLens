# Scoped review decisions and advisory-specific follow-up — 30 October 2026

## Current original-ledger state

Two accepted decisions are recorded exactly within reviewer scope: original system libsqlite3-0 CVE-2025-7458 ADDRESSED in rebuilt candidate 4e3a0339..., and original exact Debian core-libz CVE-2023-45853 NOT AFFECTED (only SHA256 7e2a72b4..., excluding bundled/unidentified copies). Remaining 137 entries are OPEN. No candidate security or execution approval. See original-ledger-current.csv, append-only review-decision-history.jsonl and reviewer-6cfb68e-decision.txt (decision excerpt supplied by the user). No independent review timestamp was invented. Original high-critical-ledger.json and original-ledger-proposals.csv remain byte-for-byte unchanged; earlier 139-open statements are historical snapshots, superseded only by these two scoped decisions.

Reviewer limitations retained: no rebuilt-image execution; reviewer lacked gpgv and inspected supplied signature records rather than rechecking them. Team source-signature checks below are separately executed evidence, not retroactive reviewer coverage.

## Renamed/missing packages: all seven assessed, no closure

libssl3 3.0.22-1~deb12u1 maps explicitly to candidate libssl3t64 3.5.7-1~deb13u3. Both originate from OpenSSL; new package owns libssl.so.3 and libcrypto.so.3. Exact Debian control says Replaces: libssl3 (and t64 Provides). This is a rename/replacement, not removal. Active DTLS CVE-2026-84782 backport and changelog provide evidence for that system copy; this does not clear Node/wheel-bundled OpenSSL.

The other six gaps are original util-linux-extra source-package advisory occurrences. Its old package/files are not recorded in candidate package ownership, but related affected code is retained: mount/libmount1 for CVE-2026-53613, -76642, -78409, -78410; libblkid1 for -53615; util-linux /usr/bin/nsenter for -78408, all source 2.41.5-0+deb13u1. The last four advisories remain scanner-reported on retained packages. Missing the extra binary package cannot clear its original source-level occurrences. CVE-53615 has fixed-source evidence; CVE-53613 has residual-path uncertainty. All seven original gaps remain OPEN. See missing-package-seven-assessment.csv and package ownership JSON in evidence ZIP.

## Other 18 unreported occurrences: advisory-specific evidence, all still OPEN

| Advisory | Original occurrences | Candidate assessment |
|---|---:|---|
| CVE-2026-53615 | 7 | util-linux 2.41.5 exceeds CNA fixed 2.41.4; authenticated upstream dos.c shows widened arithmetic and bounds checks before first-two-entry handling. Proposed fixed evidence, not closure. |
| CVE-2026-53613 | 7 | Debian 2.41.5 changelog claims fix, but CNA distinguishes fixed new mount API from affected legacy mount paths through this version. Residual applicability/backport completeness remains unresolved. |
| CVE-2026-41992 | 1 | gzip 1.13-1+deb13u1 active patch, changelog and upstream commit clear stale LZH decoding state. Vendor backport evidence; numeric version alone insufficient. |
| CVE-2026-11822 | 1 | SQLite deb13u2 claims a combined FTS5 backport. Its patch's explicit origin maps directly to -11824; complete mapping to separate -11822 upstream fix references is not independently established. Keep open. |
| CVE-2026-11824 | 1 | SQLite deb13u2 active patch origin 4a5ad516ea93 matches CNA reference and fixes FTS5 leaf validation with test fixture. Backport evidence, not blanket SQLite clearance. |
| CVE-2026-84782 | 1 | OpenSSL 3.5.7-1~deb13u3 backport resets init_off and avoids retransmission during suspended handshake writes; active patch and tests retained. Numeric 3.5.7 is still below upstream fix 3.5.9. |

Every individual package occurrence, version and source path is in unreported-18-advisory-assessment.csv. All remain OPEN until independent disposition review; scanner absence alone is not used as evidence of a fix.

## Evidence authenticity and limits

advisory-followup-evidence.zip contains original CNA JSON for all ten unique follow-up IDs; exact Debian .dsc and Debian source archives/patches; selected upstream util-linux source; package inventory ownership; signed Debian trixie and trixie-security InRelease records; Sources index hashes and matched source paragraphs; GPG logs/receipts and fetched-content hashes. Official archive-keyring verification exited 0 for both source suites; signed index -> dsc -> source archive hash chains verified for all four exact source versions. Normal GPG personal trust warnings retained, not hidden. Entire Sources indices are excluded but URLs/checksums retained for reproduction. No signature bypass, severity suppression or runtime/library replacement.

This is source/package/advisory assessment, not execution of exploit fixtures against the rebuilt candidate. Metadata package ownership is not proof of absence of all unowned/bundled copies. Functional tests and Grafana Go provenance limitations remain separate. No new app/dependency/base changes.

## Separately planned baked-image acceptance: no results available

Exact image: sha256:4e3a0339cb5e1465701f757ca136039c369ab96fa672401a938e3efa0e5467d8. No baked-image acceptance ZIP/logs have been supplied here; remote review branch was still d898473 at preflight. The image is local to the Mac; this cloud Docker host lacks it and has insufficient disk space. Therefore inference/PDF/TLS/auth/live citations/failed replacements/expiry recovery/monitoring/restart/recreation remain NOT RUN in this acceptance submission. Prior mounted base-compatibility checks are not substituted. No full Compose or actual RunPod coverage claimed. The accepted scan does not count as functional execution.

Local-agent task is already documented in LOCAL-ACCEPTANCE-HANDOFF.md. Required next artifact is its actual synthetic acceptance ZIP/checksum with failures/reruns and safe pre/post inventories; no further rebuild or repeat scan is needed first. Status is pending execution/artifact transfer, not passed. The original HTML/JSON incident remains unresolved.

Security clearance, merge, publication, deployment, paid resources, migration and existing-data changes remain blocked.
