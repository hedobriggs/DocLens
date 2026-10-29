# Exact-image frontend permissions: received Mac evidence

ZIP: frontend-permissions.esbi3xy9.zip
SHA-256: 9c2c45314abe0d61af6bafb7ec090a9b3a21012345ca90633bc86bcedd23c2ee
Image specified in both recorded commands: sha256:a16cdbc1657012fd60dc1ac67b44ce9c643d16e2912e8ad4ff146a304e06bbee.

Artifact inspection independently verified ZIP integrity, matching reviewed probe source, and both readable-file hashes against exact git application source a2986c786ed50d271fb99ad787218695e9fd4d82. Docker execution is Mac-executed/user-supplied evidence, not independently rerun on this host.

Both paths /opt/frontend/package.json and /opt/frontend/next.config.ts are regular files, mode 0600, uid/gid 1000. UID 0 with all capabilities dropped records PermissionError errno 13 for each. UID 1000 reads both successfully, with non-ELF headers and exact-source matching hashes (717 and 133 bytes respectively). Both probe processes exit 0 and stderr is empty; UID 0 exit 0 means the error was recorded, not that the reads succeeded. Commands retain read-only filesystem, network none, cap-drop ALL, no-new-privileges, bounded resources and no mounts/ports.

The expected collector identity mismatch is confirmed by supplied evidence. No application chmod/chown/capability change is warranted for these two paths. Preserve original failed-read records together with the later owning-user results. These are configuration/text files, not native binary copies; resolving their collection discrepancy does not establish complete native inventory or clear any advisory.

All 139 critical/high findings remain OPEN. Original native-assessment ZIP (runtime SQLite mappings/versions, native hashes/markers and DB metadata) has not been supplied in this chat. It is still required before selecting native remediation or claiming applicability/non-applicability. Rebuilt-image scan and isolated functional acceptance remain pending. No merge, publication, deployment, security clearance or existing-data change.
