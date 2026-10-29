# Separate original-ledger disposition submission

This submission does NOT close entries. All 139 original critical/high occurrences retain OPEN_PENDING_INDEPENDENT_REVIEW. Exact source ledger high-critical-ledger.json is unchanged. Candidate evidence accepted at 8d8f0ec: local image 4e3a0339cb5e1465701f757ca136039c369ab96fa672401a938e3efa0e5467d8, source 299f3b48bbcd1058845ce14f528fba553d68a783.

Each CSV row retains original advisory/component/version and matches candidate by advisory+package within OS class (distribution target string changed), or exact binary target. Go/plugin target renaming/deduplication is NOT assumed equivalent. Missing target is a mapping gap, not resolution. Candidate package IDs include release/epoch when recorded; vulnerability hit versions are scanner-reported installed versions. No-fix advisories remain open; no-fix status is not proof of applicability or non-applicability.

Observation counts: {"NOT_REPORTED_ON_CANDIDATE": 20, "PACKAGE_NOT_RECORDED": 7, "STILL_REPORTED": 112}. These are scan observations only, not accepted dispositions. Missing package records require copied/bundled equivalent assessment; named binary target gaps require hash/ownership mapping. No severity-based automatic closure.

Original system SQLite critical: propose addressed through verified engine upgrade outside its affected range plus accepted scan evidence. Original MiniZip critical: propose no longer reported in rebuilt image; original signed Debian core-libz attribution is independently reviewed evidence, not a blanket waiver. Qdrant/Grafana/Node per-copy evidence and Grafana Go source/runtime provenance limitation remain explicit in vendor reports.

The new candidate still has 120 high and other medium/low/unknown findings, including other SQLite advisories. This original-ledger comparison does not cover every newly reported finding or clear candidate security. Functional acceptance is separate, pending baked-image execution on the Mac. No merge, publication, deployment, existing-data changes or security approval.

Formatting evidence: initial CSV export used CRLF and failed the whitespace check. Converted line endings to LF without changing row content; subsequent base-to-head whitespace check passed. Original failure output and passing result preserved separately in ledger-format-checks.zip.
