# Narrow frontend PermissionError assessment

Application source a2986c786ed50d271fb99ad787218695e9fd4d82; image identifier a16cdbc1657012fd60dc1ac67b44ce9c643d16e2912e8ad4ff146a304e06bbee. No application code or permissions changed.

Reviewer/user reports original native inventory PermissionError for /opt/frontend/package.json and /opt/frontend/next.config.ts. The native ZIP itself has not been attached here, so file ownership/mode/read results are not independently verified for that image.

## Reproduced source/build mechanism

The Mac build block sets umask 077 before git clone. Git's tracked 100644 mode does not promise a checkout file readable by all users: independent local clone/checkout of exact a2986c7 under that umask yielded both files mode 0600 (frontend-permission-reproduction.log). deploy/portable/build.py copies source modes explicitly to its temporary build context. Dockerfile.frontend copies package.json and next.config.ts with --chown=node:node without --chmod; final RunPod assembly uses cp -a, preserving ownership/modes. The supervisor starts the frontend as uid/gid 1000. The native collector runs as the final image default root user but drops ALL capabilities, including DAC override/read-search. Root without these capabilities cannot read uid-1000-owned 0600 files. This is a supported explanation awaiting exact-image stat/identity confirmation, not a direct Docker-image reproduction here.

The broad collector opens every regular candidate file to check its first four ELF bytes, including these text/configuration files. Thus these errors alone do not demonstrate missing native SQLite/MiniZip code coverage in those two files. They also do not establish general complete coverage: os.walk directory errors are not reported by that collector and stripped/static copies can evade markers.

## Narrow corrective evidence collection

inspect-frontend-permissions.py performs stat and bounded reads of only those two paths twice, as uid 0 and frontend uid 1000. Both new containers retain read-only filesystem, network none, no-new-privileges, cap-drop ALL, no mounts/secrets/ports, 128 MiB and one CPU. It captures mode, owner, errno and strerror; hashes readable files and compares to exact git source. It neither changes permissions nor adds capabilities. No file contents are printed.

Expected confirming evidence: uid 1000 ownership/mode 0600, uid 0 EACCES, uid 1000 successful reads with source-matching hashes and non-ELF headers. These remain expectations, not passed image results. Any different observation invalidates the proposed explanation and must be retained/investigated; do not chmod/chown, escalate capabilities, or attach existing application volumes.

Independent checks passed: exact-source umask reproduction; probe syntax and synthetic owner-only file reads/non-ELF classification/hash verification. Logs retain their limited scope. Original native errors are preserved on the Mac/reviewer side; not replaced by these later checks. No original Mac failed-run logs were invented. No image acceptance executed here.

## Proposed remediation and security applicability

For these collection errors, no application permission change is warranted on current evidence. Use the owning frontend identity for the narrowly required text reads. Broader collector improvement should select file candidates before opening them and explicitly report directory traversal errors, with partial coverage clearly retained.

The two text files are not themselves native libraries. Successful source-hash verification can close only their collection discrepancy; it cannot clear SQLite CVE-2025-7458 or MiniZip CVE-2023-45853. See assessment.md and critical-high-dispositions.csv: all 139 occurrences remain OPEN. Obtain the actual native inventory's runtime SQLite version/mappings, per-binary markers/hashes, embedded copy evidence and scanner DB metadata before final applicability dispositions. Modernc SQLite in Grafana must be mapped independently from Debian/Python SQLite.

Smallest conditional fixes: vendor-supported libsqlite3/base backport or verified rebuilt owning SQLite components if affected; vendor-fixed owning component for any shipped affected MiniZip writer, without removing core zlib. MiniZip non-applicability needs exact package/source/binary evidence, not will_not_fix or missing strings alone. OpenSSL has reported Debian fixed version 3.0.22-1~deb12u2 pending vendor availability verification. Grafana needs a fixed full distribution including plugin binaries/toolchains; a main-binary-only upgrade is insufficient. Do not interpret these proposals as selected, built, or tested remediation.

Security clearance, merge, publication and deployment remain blocked. Rebuilt-image scan and isolated synthetic functional acceptance remain pending; actual RunPod acceptance is separate. Existing containers, data and permissions are unchanged.
