# Native/image assessment — 29 October 2026

Status: blocked security release. This is assessment and collection tooling, not a remediated image or a passed image acceptance run. Application remains a2986c786ed50d271fb99ad787218695e9fd4d82. The Mac build/scan is user-executed; artifact analysis and collector safety checks are independently executed here.

## Priority critical findings

CVE-2025-7458: the upstream CNA record specifies SQLite >=3.39.2 and <3.41.2 and requires attacker ability to execute arbitrary SQL with crafted ORDER BY expressions. Debian libsqlite3-0 3.40.1-2+deb12u2 is reported affected, without a fixed package version. A Debian backport must be proven from source/changelog, not inferred from version or suppressed. Python _sqlite3 normally dynamically loads libsqlite3; collect actual runtime version, mapped library path and hash. SBOM also lists Grafana modernc.org/sqlite v1.54.0, a separate embedded implementation requiring its own underlying SQLite mapping. Inspect native wheels (PyMuPDF, Pillow, ML), Grafana/plugins, Qdrant and Node for further embedded copies; scanner inventory is not exhaustive proof.

Application source has no direct SQLite or user-controlled SQL route. Qdrant production client uses remote http://qdrant:6333; installed qdrant-client local persistence does use sqlite3 and parameterized/fixed SQL. This distinction reduces one apparent request path, but does not establish whole-image non-reachability. Grafana uses SQLite for its own state; query generation, plugins, authenticated administrative features and embedded engines need assessment. Do not remove libsqlite3 to silence the scanner or replace it with a wheel that leaves the system copy vulnerable. Preferred remediation: verified vendor-fixed base/package; if unavailable, separately reviewed reproducible patched library/base with ABI and full acceptance coverage. No such binary has been selected or built yet.

CVE-2023-45853: upstream CNA identifies MiniZip zipOpenNewFileInZip4_64 and attacker-controlled long ZIP metadata. This is not generic zlib decompression. Debian reports zlib1g will_not_fix, not security clearance. Upstream zlib v1.2.13 CMakeLists builds core zlib separately; that alone does not prove the exact Debian or wheel binaries omit MiniZip. Inspect package files and native binary symbols/markers, including pyminizip, PyMuPDF, Pillow, Grafana/plugins, Qdrant and Node. Stripped/static code can evade symbol searches. User upload path opens with fitz.open(..., filetype='pdf'), not a user ZIP writer; Grafana plugin/archive operations and transitive native parsers remain separate paths. A present affected MiniZip copy needs a verified fixed/rebuilt owning component; a not-affected disposition needs exact-binary/source proof and independent review. Do not blanket-waive zlib or delete core compression libraries.

## High findings by component

- Debian: 61 high occurrences; 59 have no fixed version in the supplied scan. Includes util-linux family (bsdutils, blkid, mount, smartcols, uuid, util-linux and extra), ncurses/tinfo, ACL, gzip, SQLite, OpenSSL, systemd/udev and perl-base. Assess daemon uid/capabilities and actual commands/libraries per advisory. Authentication does not eliminate parser/local-privilege risks. Review fixed vendor updates first; retain no-fix entries individually. Scanner severities are not a substitute for Debian applicability.
- Grafana main: 7 high occurrences (5 kin-openapi, 1 go-jose, 1 Go stdlib). Upstream fixes reported. Select a supported pinned Grafana build that actually includes corrected modules/toolchain. Preserve host-only authentication and dedicated gateway behavior; do not hand-edit binary metadata or merely update top-level Go modules outside the shipped binary.
- Grafana bundled plugins: 69 high occurrences across 13 binaries. Most share x/net and Go stdlib; stackdriver also includes grpc and tempo includes tempo advisories. A Grafana main-only upgrade is insufficient unless bundled plugin binaries are verified too. Prefer vendor-fixed full distribution; removing unused plugins is a separate compatibility decision, not assumed safe.
- Prometheus: no high/critical in this snapshot; 3 unknown entries including one no-fix OpenPGP advisory remain open for actual reachability assessment.
- Python: no high/critical, but two medium filelock advisories now report fixed version 4.2.1. That upgrade needs Python 3.11 graph resolution and lock/symlink/config regressions; prior successful remediation does not waive newly reported findings.
- Node packages: zero reported in this snapshot. This does not cover every native/static component or constitute clearance.

Full per-occurrence high/critical ledger is high-critical-ledger.json. No CVE is marked resolved by this assessment.

## Exact-image collection and database provenance

collect-native-evidence.py validates isolated Mac source and exact image, then uses a NEW read-only, network-disabled, 512 MiB/one-CPU container with no mounted application data, ports, secrets or Docker socket. It records native ELF hashes/markers, runtime SQLite and loaded mappings, package inventory and original cache metadata if present. No startup, upload, migration or application operation is performed. Static marker absence cannot clear stripped/embedded copies. Filesystem errors are explicit.

Original cache is on the Mac under security.RoWmtn/cache/db/metadata.json, not available on this cloud host. The collector preserves current bytes and mtime without updating DB; compare UpdatedAt/DownloadedAt against the original 2026-10-29 15:26 UTC scan before calling them original-scan provenance. If unavailable or newer, perform a separately labelled fresh scan with a NEW cache, and capture --version AFTER database download, metadata.json and DB digest. Do not overwrite original scan evidence.

## Execution and failure evidence

Cloud host: only 5.4 GiB free Docker filesystem (VFS); exact Mac image absent. No image rebuild, candidate container run or image acceptance performed here. No unrelated images/volumes deleted, no paid host provisioned. Current source/image evidence is preserved.

Metadata research initially failed because system Python lacked requests; corrected to stdlib urllib (initial-fetch-failure.log). Attempted GitHub Debian tracker mirror returned 404; this is unavailable vendor-source evidence, not a clean applicability result. Official CVEProject CNA records were retrieved successfully; source URL/status/size in upstream-fetch-results.json. An exploratory Grafana v13.2.2 go.mod fetch is not proof of the installed Grafana version and is not used to clear findings. No original Mac failed-run logs have been supplied; none are invented.

Collector checks executed: missing directory stops before Docker; wrong source stops before Docker; wrong image stops before probe; simulated exit 137 preserves exit status and evidence without automatic retry. These four checks do not establish image functionality.

## Remaining gates

1. Obtain exact-image native inventory and original DB metadata (or fresh labelled scan).
2. Resolve affected code presence/reachability; submit separately reviewable component pins/build patches and no-fix dispositions.
3. Rebuild and scan full final image including all bundled copies; retain initial failures and corrective reruns.
4. Fresh synthetic-volume acceptance of exact rebuilt image: login/anonymous rejection, authenticated 3000/3001/9090 routing and assets, upload/failed-replacement preservation, five-employer live answers/citations, session expiry and UI recovery, restart/recreation identity/history persistence, monitoring failure isolation and core shutdown. Full Compose monitoring is a separate suite. No runtime-file substitutions.
5. Independent security and functional review before any execution approval. Actual RunPod HTTPS/attached storage remains separate. Original HTML/JSON incident remains unresolved.

No publication, deployment, merge, migration or existing-data modification performed.
