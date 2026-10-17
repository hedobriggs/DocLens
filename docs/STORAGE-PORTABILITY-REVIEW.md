# Independent review: explicit S3 configuration portability

Review only the follow-up diff from
`3ea027d311d20d31c9bc71f7199b9f2d77515406` to the exact commit in the user handoff.
The earlier Milestone 1 approval remains limited to its successfully tested
configuration. This follow-up needs independent review; it is not a deployment,
merge authorization, or a claim that Milestone 1 previously hardcoded AWS hosting.

## Finding and change

Both production originals and the integration runner previously used the global
`boto3.client`. Explicit endpoint/keys did not prevent profile/shared-file lookup.
An unrelated nonexistent machine AWS profile could prevent either client from
being constructed, and the runner retried configuration errors until a generic
readiness timeout.

`platform_core.s3_client` now creates a fresh Boto3 session backed by a Botocore
session with session-specific profile/config-file/credentials-file sources. It
has no profile environment provider and points shared configuration/credentials
files at `os.devnull`. It neither edits the process environment nor mutates Boto3's
default session. Both production originals and the runner use this factory.
Explicit endpoint and nonempty credentials are required; no ambient credential
fallback is permitted. Region, v4 signing and path-style addressing remain explicit.

TLS verification remains enabled. The supported `AWS_CA_BUNDLE` trust override
and normal HTTP proxy settings remain available; bypassing machine profiles/files
does not disable certificate validation. No new third-party dependency is added.

Initialization errors identify S3-compatible storage and the underlying exception
class, suppressing exception body/chaining. Client creation happens outside the
readiness retry loop. Actual readiness timeouts identify PostgreSQL or MinIO and
the exception class, without the connection URL, credentials or SDK response body.

## Checks executed on this follow-up

- Six focused regression tests passed: nonexistent selected/default profiles plus
  malformed shared files; conflicting default shared configuration; explicit keys
  and endpoint (including v4 presigning without ambient session token); retained
  TLS/custom CA configuration; sanitized initialization/readiness errors; and no
  fallback when explicit credentials are missing. Each named test can exercise
  multiple related assertions/subtests; six is the runner's test count.
- All 23 backend acceptance tests passed with `AWS_PROFILE` and
  `AWS_DEFAULT_PROFILE` naming nonexistent profiles and shared-file paths nonexistent.
  These use actual PostgreSQL and retained private MinIO with generated MinIO
  credentials, not an AWS account. Default embeddings are deterministic.
- The Python 3.11 CPU image rebuilt with verified TLS/artifact checks. The non-root,
  read-only container smoke check passed: dependency consistency, verified sessions,
  workspace RLS, retained original range read, cross-firm denial and revocation.
  The harness now always sets nonexistent AWS profiles/config paths **inside** the
  API container as well, independently of the host process environment.
- Python compilation and `git diff --check` passed. Temporary containers were removed.

Raw outputs: `validation/portability-unit.txt`, `portability-acceptance.txt` and
`portability-image.txt`. Image ID is recorded with the smoke evidence.
No skipped or expected-failure tests were reported. Existing PyMuPDF SWIG warning
remains. Frontend, real-model and unrelated legacy suites were not rerun for this
storage configuration change; their earlier results are historical, not fresh
portability evidence. No full Compose deployment or live AWS endpoint was tested.

## Reproduce

From the existing DocLens checkout with the documented platform dependencies:

```sh
backend/.venv/bin/python -m unittest discover -s tests/milestone1 -p test_storage_portability.py -v
AWS_PROFILE=doclens-nonexistent-profile AWS_DEFAULT_PROFILE=doclens-nonexistent-default-profile \
  AWS_CONFIG_FILE=/nonexistent/aws/config AWS_SHARED_CREDENTIALS_FILE=/nonexistent/aws/credentials \
  backend/.venv/bin/python tests/milestone1/acceptance.py
backend/.venv/bin/python tests/milestone1/build_image.py
AWS_PROFILE=doclens-nonexistent-profile AWS_DEFAULT_PROFILE=doclens-nonexistent-default-profile \
  AWS_CONFIG_FILE=/nonexistent/aws/config AWS_SHARED_CREDENTIALS_FILE=/nonexistent/aws/credentials \
  backend/.venv/bin/python tests/milestone1/image_smoke.py
```

Review session isolation rather than clearing AWS variables as a workaround.
Verify exception diagnostics do not reveal endpoint/credential values or chained
SDK errors, and certificate verification has not been weakened. Return prioritized
findings and an approve/request-changes recommendation. Do not merge or deploy.
