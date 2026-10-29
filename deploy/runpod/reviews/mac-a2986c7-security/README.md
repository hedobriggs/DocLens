# Intel Mac candidate security evidence

Application source: `a2986c786ed50d271fb99ad787218695e9fd4d82`.
Mac-reported Docker image identifier: `sha256:a16cdbc1657012fd60dc1ac67b44ce9c643d16e2912e8ad4ff146a304e06bbee`.
Underlying image configuration: `sha256:162232f0b3fe2d0ad9948c387a37b97f25b79c4af256271fdf6bce5037dd6fd4`.

The ZIP is the unchanged user-supplied Mac evidence. Artifact inspection verified ZIP integrity, saved report checksums, matching image filesystem layers, and configuration identity in build/scan logs. The Mac build and scan were not independently rerun by Team Codex.

Contents: build output, source/image identifiers, image inspections, CycloneDX SBOM, complete Trivy JSON/text findings, scanner version and scan commands. Trivy 0.76.1 reports 587 component-level occurrences across 161 advisory IDs: 2 critical, 137 high, 289 medium, 120 low, 39 unknown. This is not an exploitability determination.

## Evidence limitations

Exact database update metadata is absent (repository/schema `trivy-db:2` is logged). Build output does not capture every build shell command. No separately identified failed-run logs are present. Missing artifacts must be supplied separately, not reconstructed as executed evidence. Synthetic functional acceptance remains pending. The original HTML/JSON incident remains unresolved.

## Priority critical findings

- CVE-2025-7458: libsqlite3-0 3.40.1-2+deb12u2, reported affected with no fixed version. Assess actual shipped library and whether attacker-controlled SQL can reach the affected execution path. Open.
- CVE-2023-45853: zlib1g 1:1.2.13.dfsg-1, reported will_not_fix. Verify presence and reachability of affected MiniZip code rather than treating package identification as proof of exploitability or safety. Open.

Security release block remains. No merge, image publication, deployment, migration or customer-data admission is authorized by this evidence commit.
