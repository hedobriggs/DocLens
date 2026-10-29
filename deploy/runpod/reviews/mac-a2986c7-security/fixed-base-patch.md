# Fixed-base source patch for independent review

Only application/build change: deploy/portable/Dockerfile.backend switches from pinned Python 3.11 bookworm to verified official Python 3.11.18 slim-trixie amd64 manifest 6d10e720318bd84cc3d88af92bb5a47189222e17620a2fd214da6445e4afb679, then fails the build if Python is not 3.11 or SQLite <3.41.2. The verified base runtime is SQLite 3.46.1, outside CVE-2025-7458 affected range. Vendor proof is in accepted e164ec1 vendor evidence. No cross-suite package mixing or SQLite wheel workaround. No permission changes.

Unchanged: all 73 application dependency pins/CPU torch installation, model snapshots and download allowlists, pip removal policy, upload/page/text/resource limits, authentication and monitoring code, document/revision/publication/citation identity handling, frontend behavior and source-integrity manifest. No migration. Source equality/hashes are in fixed-base-evidence.zip.

## Preliminary independent compatibility checks

- 67 regression test executions pass in the new pinned base with the existing approved CPU graph mounted read-only (includes inherited/repeated cases).
- Real CPU embedding/reranking passes at unchanged model revisions; output difference from earlier candidate is zero on measured synthetic fixtures.
- Six packaging checks pass, including source-integrity rejection and credential/context isolation.
- Full logs, commands/options, scripts, scope and comparison/preservation results in fixed-base-evidence.zip. No failure/retry in these runs; historical failures remain preserved separately.

This is NOT rebuilt-image acceptance. Dependencies/models/source fixtures were read-only mounted for compatibility testing only; final-image tests must use baked runtime files. Graph has not yet been freshly installed by a completed new-base DocLens build. Python 3.11.17 ->3.11.18 and Debian/glibc transition remain material compatibility risks even though preliminary checks pass.

## Mandatory remaining gates

1. COMPLETE for selected roots: original Mac image omitted-path evidence was received and accepted in e84b5eed937f932bd50f8a59aec6ce6ce66a32b3. No reported errors or bounded stop; 168 symlinks remain recorded but unfollowed. See omitted-path-results.md. This is not full-image coverage or rebuilt-candidate acceptance.
2. Review this separate base patch, then build backend/frontend/final image sequentially under unique tags on adequately resourced authorized host. Record exact source/base/dependency/final IDs and complete installer/build output. No overwritten tags/old volumes.
3. Fresh WHOLE final-image SBOM and vulnerability scan, separate cache/provenance (scanner identity, DB metadata and digest); include copied Qdrant libs, embedded SQLite/Go/native dependencies and all OS packages. All 139 original findings remain OPEN until independently reviewed; do not claim this base change fixes them all. No fix/no-reported-fix entries waived.
4. Baked-image native imports/inference and PDF/TLS/auth regressions (not just these mounted probes), plus isolated synthetic login, five-employer live answers/citations, failed-upload preservation, expiry/cancellation recovery, persistent identity/session/history across restart/recreation, authenticated 3000/3001/9090 dashboards/assets/queries, monitoring failure isolation and core shutdown. Full Compose stack separately. No runtime file substitution, old installation/data/volumes or customer documents.
5. Independent source/security/image/local acceptance review before execution approval. Actual RunPod HTTPS/attached-storage remains separate. No merge, publication or deployment.

## Grafana provenance limitation retained

Matching pinned vendor binary's Go build information and exact module origin documentation identify modernc.org/sqlite v1.54.0 / SQLite 3.53.3. Matching binary string corroborates it; no SQLite engine runtime query was executed inside Grafana. Public module ZIP download was blocked after redirect; Go h1 source checksum was not recomputed from the GitLab snapshot. Do not promote this to reproducible-build proof or general Grafana clearance. Existing per-copy dispositions remain proposals for reviewer acceptance.

The original HTML/JSON incident remains unresolved. Existing containers/data/Mac installation remain unchanged.
