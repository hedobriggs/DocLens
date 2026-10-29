# Original native inventory: verification and targeted remediation proposal

Application: a2986c786ed50d271fb99ad787218695e9fd4d82. Mac command image identifier: sha256:a16cdbc1657012fd60dc1ac67b44ce9c643d16e2912e8ad4ff146a304e06bbee. Native ZIP SHA-256: 7e00e8a80d6930eb3ea974d2a1b9d9cf818102e28fa3155c2d75ef2d589a4549.

Independent artifact checks here: supplied checksum matches; ZIP integrity passes; embedded probe matches reviewed collector; recovered metadata SHA-256 matches cache-provenance.json. Container execution is Mac-executed evidence, not independently rerun here. Original ZIP/checksum are unchanged. This is not a remediation implementation or security clearance.

## Original scanner database metadata recovered

Scanner: Trivy 0.76.1 from original security ZIP. Database schema Version 2; UpdatedAt 2026-10-29T13:09:46.269823229Z; DownloadedAt 2026-10-29T15:26:10.015334357Z; NextUpdate 2026-10-30T13:09:46.269822928Z. Metadata SHA-256 157de354c79394f3387821bf9d733efbf785819c55986fdc067dd67d57a07bb8. Original report CreatedAt is 2026-10-29T15:26:21.135657116Z, approximately 11 seconds after download. Dates are consistent with original scan provenance; metadata alone does not cryptographically prove unchanged DB contents. DB binary/artifact digest is unavailable. No fresh scan is claimed or needed merely to replace missing metadata.

## SQLite CVE-2025-7458: affected system version confirmed, reachability not cleared

Python runtime sqlite3.sqlite_version = 3.40.1; /proc/self/maps confirms /usr/lib/x86_64-linux-gnu/libsqlite3.so.0.8.6. Debian package libsqlite3-0:amd64 = 3.40.1-2+deb12u2. File SHA-256 2e6eef9a727f081f0d453b4e5e6cbd8b9ef8b6f86cbf7681cbad444d3b0b55c8. The upstream CNA affected range >=3.39.2,<3.41.2 includes this runtime version; vendor backport evidence is still needed before ruling out affected code. sqlite3KeyInfoFromExprList marker is present, but a marker does not show whether the function is patched. No direct untrusted SQL request path was identified in DocLens source; that observation is not whole-image non-exploitability proof.

A SECOND distinct SQLite library is shipped at /opt/qdrant/lib/libsqlite3.so.0.8.6 (1571096 bytes), SHA-256 132db4406f676c9516f3e7f6cbf1aaa2b08787cdf28ead75eba99c79afdb1010. It has SQLite format and sqlite3KeyInfoFromExprList markers. Its version is NOT established by the filename, marker or Debian system package database. RunPod supervisor launches Qdrant using its copied loader and --library-path /opt/qdrant/lib, so this directory is relevant to Qdrant dependency resolution, but actual SQLite loading/use by Qdrant is NOT yet proven. Docker assembly copies the entire Qdrant source image lib directory; an incidental unused copied library is possible. Do not delete it or infer it is active without dependency-resolution evidence.

Grafana /opt/grafana/bin/grafana SHA-256 91040ca83733197346a586b79b102a408b269d0d63af72fb78f6f5055ea0df15 also contains both SQLite markers. SBOM reports modernc.org/sqlite v1.54.0; this is a Go module version, NOT an SQLite engine version. Map that exact module/source revision to its embedded SQLite version/backports and inspect Grafana query paths independently. Marker presence does not establish this Grafana copy is affected by this CVE.

Proposed separately reviewable patch A: select a vendor-supported fixed Python base/system SQLite package with patch provenance, preserving Python ABI, TLS and installed-data formats. Verify the copied Qdrant library independently; select a fixed Qdrant distribution if needed. Alternatively narrow copied libraries to a measured dependency closure only after loader validation proves the SQLite copy unused. Do not drop or replace that library speculatively. Avoid a pysqlite wheel workaround that leaves the system/other copies unchanged. No fixed image/pin selected or built yet.

## MiniZip CVE-2023-45853: presence/reachability unproven, still OPEN

Python zlib runtime = 1.2.13; Debian zlib1g:amd64 = 1:1.2.13.dfsg-1. These are zlib versions, NOT proof of an installed MiniZip writer version. No zipOpenNewFileInZip4_64, zipOpenNewFileInZip4 or unzOpen64 marker is recorded in any of 1284 inventoried ELF files. PyMuPDF native libraries, Pillow bundled libraries, Grafana and Qdrant paths are among inventory entries. This supports only absence of selected byte markers in the inspected files. It cannot clear stripped/static code or unvisited paths. No MiniZip version is established by this evidence.

DocLens's upload parser specifies filetype=pdf and has no direct MiniZip ZIP-writing API route. That does not assess all native parser paths or Grafana archive/plugin functionality. Debian will_not_fix is not a waiver. Proposed separate disposition B: obtain exact Debian zlib build/source/package-file evidence showing whether MiniZip code is compiled/shipped, and verify bundled copies through owning distribution build records/exports. If affected writer exists, upgrade/rebuild the owning component at a verified fixed revision. If absent, submit a per-copy not-affected proposal with binary/source proof for independent review, without changing/deleting generic zlib. No not-affected disposition is issued now.

## Remaining high findings and smallest supported changes

The exact 139-occurrence mapping remains critical-high-dispositions.csv and is not modified: every entry OPEN. Debian 61 high occurrences (59 without reported fixes), Grafana core 7, Grafana bundled plugin binaries 69. System OS scan does not comprehensively assess copied /opt/qdrant libraries under another distribution's package database.

Proposed separate patch C: vendor-fixed full Grafana distribution, including the 13 bundled plugin binaries, with exact Go module/toolchain evidence; preserve gateway authentication and dashboards. Do not update Grafana main alone or edit SBOM/module labels. Proposed patch D: verify availability of Debian OpenSSL/libssl3 3.0.22-1~deb12u2 and use fixed vendor package/base, then TLS/login regressions; no-fix Debian findings stay open pending per-advisory source/backport/execution assessment. Python filelock medium advisories (outside 139) require their own Python 3.11 compatibility patch; do not conflate earlier source approvals with current scanner state.

## Failures, scope and next evidence

Original probe exit 0 with two recorded PermissionError entries and empty stderr. Preserve these together with frontend-permissions.esbi3xy9.zip showing owning-UID successful reads; no chmod/chown needed. The original broad collector opens text files during ELF detection. Directory traversal errors are not reported by os.walk in that version, and symlinks are skipped. It scans configured roots but misses /usr/local/bin/node and /usr/bin binaries. Thus 1284 entries do not establish whole-image native coverage; no claim of complete native absence is made. Frontend permission probe is not a native remediation or acceptance test.

Before implementation: supplement only needed gaps: Qdrant loader dependency listing and SQLite revision provenance; exact Grafana modernc module/engine mapping; /usr/local/bin/node and omitted native roots with explicit traversal errors; Debian MiniZip package/source attribution. Keep bounds/no network/no mounts/no added capabilities. Do not load the alternate Qdrant libc into Python or execute untrusted SQL payloads as a shortcut.

After separate remediation source review: rebuild unique tags, preserve original/corrective logs, full-image SBOM and fresh scan with exact DB metadata/digest, then isolated synthetic functional acceptance (login/access boundaries, 3000/3001/9090 assets, upload/failed replacement, live five-employer citations, session expiry, restart/recreation and monitoring/core failure behavior). Not executed on this cloud host: exact image absent and only 5.4 GiB Docker filesystem space. Mac work still requires explicit bounded commands; no remote Mac access is claimed.

Security clearance, merge, publication, deployment, paid resources, migration and customer-data admission remain blocked. Original HTML/JSON incident remains unresolved.
