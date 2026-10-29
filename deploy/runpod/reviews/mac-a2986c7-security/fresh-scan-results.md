# Fresh rebuilt-image scan: artifact review

Source: 299f3b48bbcd1058845ce14f528fba553d68a783 (runtime source matches source-approved c5d566c). Local Docker image identifier: sha256:4e3a0339cb5e1465701f757ca136039c369ab96fa672401a938e3efa0e5467d8, linux/amd64. Underlying image config recorded by Trivy: sha256:7beedeb9bd93ad148b09c79bb53db672134b7c4d73d37267f4d813616cb2c9ad. These are local identifiers, not a published registry reference.

Evidence: fresh-security.Z5FSQB-evidence.zip, SHA-256 1c495175eafbc6c825413429394c0af609b09284a2c23649e512e082babbcf35. Independent artifact checks here verified ZIP integrity, image-inspect identity, exact image layer equality against Trivy DiffIDs, and recovered DB metadata hash against recorded checksum. Original database bytes/image archive are not bundled, so their recorded hashes are provenance supplied by Mac execution, not independently recomputed here. No Mac build/scan was independently rerun on this cloud host.

## Result of the bounded SQLite/base correction

Original CVE-2025-7458 occurrence is absent in new report. Original CVE-2023-45853 occurrence is absent too. Total critical occurrences: 2 -> 0. System libsqlite3 package is 3.46.1-7+deb13u2, zlib1g is 1:1.3.dfsg+really1.3.1-1+b1. Build log confirms the SQLite floor assertion and fresh installation, followed by pinned requirements taking precedence and pip removal. No extra rebuild was performed to obtain these results.

Component-level occurrences (not distinct advisories):

| Severity | Original | Rebuilt |
|---|---:|---:|
| Critical | 2 | 0 |
| High | 137 | 120 |
| Medium | 289 | 236 |
| Low | 120 | 74 |
| Unknown | 39 | 37 |
| Total | 587 | 467 |

Distinct IDs: 161 -> 107. CycloneDX inventory has 2626 components. Debian, Python, Node and Go binary results are present. Counts do not automatically resolve ledger entries or prove exploitability/non-exploitability. All 139 original critical/high entries remain OPEN pending independent disposition review.

## Remaining scan findings and scope

120 high occurrences remain (44 OS, 7 Grafana main, 69 bundled Grafana plugin binaries). Python retains two medium filelock advisories at pinned 3.20.3. Other SQLite findings are CVE-2026-50812, CVE-2026-50813, CVE-2021-45346, CVE-2025-70873, with no reported fixed version in this snapshot; zlib also has other findings. Their existence must not be hidden or conflated with the original targeted CVE. Zero critical findings is NOT security clearance. No unrelated source remediation is initiated by this evidence commit.

The original copied-library and embedded engine applicability proposals, Grafana provenance limitation, unfollowed symlinks and static/native scanner coverage limitations remain applicable. Whole-image scan recognition is not proof that every opaque native library is identified. No waivers or severity suppressions added.

## Fresh scanner provenance and retained logs

Trivy 0.76.1; DB schema 2, UpdatedAt 2026-10-29T13:09:46.269823229Z, DownloadedAt 2026-10-29T18:13:14.013341152Z. New report CreatedAt 2026-10-29T18:16:29.324491886Z. Fresh isolated cache download, same upstream DB update as earlier scan. Recorded DB SHA-256 162d88bff697bee519561c90bb5766f2b9d27e3f0f0eb051b7a3d7bf1df42ff7; metadata SHA-256 d22136734d2b26e92d96d4303ea2df0ecefa5b87e6faae2249691e4af2340889. Scanner image inspection and post-download version JSON included. SBOM converted from raw report including all recognized packages, avoiding a second image analysis.

Full build log shows python3 deploy/portable/build.py --no-cache and docker build --no-cache final assembly; actual pip installation output and final fixed pins retained. Build and scan command logs, identifiers, image inspection, SBOM, raw Trivy JSON/table and DB provenance are supplied unchanged. No failed build/scan is reported in this supplied run; earlier failed collection/vendor attempts remain in their original artifacts, not overwritten or relabelled. Scan report archive was packaged while commands.log remained open; commands through scan/conversion are present, but later packaging terminal output is not implied captured.

## Next and pending

Validate THIS exact baked image using synthetic-only fresh volumes: native imports/inference, PDF/TLS/auth, login, upload/failed-replacement preservation, live answers/citations, authenticated monitoring, restart/recreation persistence and component failure handling; full Compose separately. Existing preliminary mounted dependency tests do not substitute for baked-image acceptance. No further scan/rebuild needed before that step unless an actual failure/change justifies it.

These functional/image/Compose tests remain unexecuted for this rebuilt image in the supplied evidence. Local agent on Mac can execute them without user command relaying, limited to isolated review resources. No remote Mac access exists from this cloud host, whose Docker disk remains inadequate. Actual RunPod HTTPS/storage remains separate. Original HTML/JSON incident unresolved. No security clearance, merge, publication, deployment, paid resources, migration or existing-data changes.
