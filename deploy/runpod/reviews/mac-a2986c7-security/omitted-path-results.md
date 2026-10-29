# Omitted native paths: received evidence and matching Node vendor runtime

Mac ZIP native-supplement.wa2me75f.zip SHA-256 0a61429c67cdb152346dd65a20e565ddaac3a8ef48f3f29eaffaea540633d305 matches user-reported checksum. Independent artifact checks: ZIP integrity passes, embedded probe exactly matches accepted e164ec1 code, expected original image identifier appears in command. This is Mac-executed evidence, not a rerun of the entire final image here.

## Collection result

Original image identifier sha256:a16cdbc1657012fd60dc1ac67b44ce9c643d16e2912e8ad4ff146a304e06bbee; application a2986c786ed50d271fb99ad787218695e9fd4d82. Read-only, no network, cap-drop ALL, no-new-privileges, 256 MiB, one CPU, no mounts/ports. Exit 0, empty stderr, no reported read/traversal errors, no bounded stop. Elapsed 3.563535558 seconds; 240184200 native bytes; 1098 files; 168 symlinks recorded but not followed. This completes selected-root regular-file collection, NOT full whole-image native coverage or security acceptance.

Compared with original native inventory: 781 overlapping paths all have identical hashes, 317 additional paths, 1601 distinct native paths in union. Original failed frontend reads and successful owning-user reads remain unchanged. No chmod/chown or capability escalation.

No selected MiniZip byte markers found in supplement. As before, marker absence does not exclude stripped/static code; skipped symlinks and unselected paths remain explicit limitations. The accepted signed Debian libz attribution is separate, stronger component-specific evidence, not a global waiver.

## Newly inspected Node SQLite: verified vendor runtime version 3.51.3

/usr/local/bin/node was omitted previously and is now hashed: fde6a4bf8d0562f7751d1a2d6cb9b417c4cfe107bbcb0aa3e9a24e125e348f48, 124827920 bytes; sqlite3KeyInfoFromExprList marker present.

Independently pulled the exact official frontend base node@sha256:c3de60bf2f9dd0ac6370e6117950ff62d6e339527e7472301c9c78a017978392 and ran only a bounded no-network/read-only hash plus node -p JSON.stringify(process.versions). Its Node binary hash exactly matches the Mac candidate; process.versions reports Node 22.23.3 and SQLite 3.51.3. Commands, pull/runtime logs and exit statuses are preserved in node-vendor-evidence.zip. No DocLens services, data volumes or credentials attached. This is matching-binary vendor execution; final-image Node execution and request-path testing were not rerun here.

Proposed per-copy disposition: this Node SQLite engine is outside CVE-2025-7458 affected range >=3.39.2,<3.41.2; no Node replacement is indicated for this specific CVE on current evidence. Independent reviewer must accept any disposition; no ledger entry is closed. This does not establish general Node security or resolve other native advisories.

## Remediation and release state

All 139 original critical/high occurrences remain OPEN. Fixed-base source patch c5d566caa566d7a7281a600943cfa58d133a8926 targets affected system Python SQLite 3.40.1 and is separate from this evidence-only commit. Model pins, limits and data/citation identities remain unchanged. Preliminary base compatibility tests are not rebuilt-image acceptance.

Retain Grafana limitation: exact binary/module/source mapping supports engine 3.53.3, but no Grafana runtime SQLite query or independently recomputed Go h1 source sum was obtained. Original module ZIP fetch failure remains in vendor evidence. Qdrant package/hash attribution and direct loader listing do not rule out later dynamic loads. No fabricated failed runs or retries are added; new supplement and Node vendor checks passed first recorded runs.

Next: independent review of omitted-path/Node evidence and separate fixed-base patch, then uniquely tagged rebuilt final image with fresh full SBOM/scan and explicit DB provenance; baked-image native imports/inference/PDF/TLS/auth plus isolated synthetic persistence/monitoring/Compose acceptance. No runtime-file substitutions presented as final-image tests. No rebuilt DocLens image ID, whole-image scan or local/RunPod acceptance result is claimed here. Actual RunPod remains separate. Security clearance, merge, publication and deployment remain blocked; existing data/containers/Mac installation unchanged.
