# Milestone 2, stage 1: incremental migrations and durable admission

Review base: `474a50d5b8df21fab90df39e832d0163afda2ce2`.
Branch: `milestone/2-durable-jobs`. The exact head is in the review handoff.
This is the first review boundary, not completion of Milestone 2. Synthetic data
only. No merge, deployment or customer-data admission is authorized by this stage.
Cleanup is restricted to future inventory/dry-run work; this commit provides no
cleanup executor, delete function, lifecycle rule, or new deletion privilege.

## Incremental upgrade and preservation

`platform_admin.migrate` now owns one transaction for all pending migrations and
serializes concurrent runners with a PostgreSQL transaction advisory lock. It
checks ordered versions and recorded SHA-256 values, skips already applied files,
rejects missing/changed/newer history and refuses to run inside a caller's active
transaction. Failures roll back schema, roles, history and new migration changes.
It never drops/recreates existing tables or resets data.

The original `001_foundation.sql` is unchanged. For legacy v1 databases its previously
executed file checksum cannot be reconstructed: adoption explicitly records NULL
with `legacy-unverified` provenance. New executions record actual source checksums.
This is not a retroactive verification of arbitrary legacy schema drift. An owner
must inspect any unexpected existing schema; migration does not repair it silently.
The tested upgrade snapshots all pre-existing rows and checks document/version/
passage IDs, source metadata, active pointers, audit rows and original PDF bytes.

Migration 002 adds reservation/submission/job/event/attempt tables and forced RLS.
A new `documents.publication_revision` defaults to zero for existing rows. A trigger
increments it when the active version changes, including through the retained
synchronous upload path. Existing IDs, passages and citation hashes are untouched.
Attempts/state/lease columns prepare the schema for a later worker stage; no worker
is granted claim, transition or publication authority in this commit.

## Admission contract and transactions

Durable endpoints are OFF unless `PLATFORM_DURABLE_JOBS_ENABLED=1`. Enable it on
both API and frontend only for synthetic stage acceptance. Existing `/documents`
uploads and the existing UI keep their synchronous behavior. No job-progress UI,
retry/cancel command, extraction worker or automatic queue consumption exists yet.

- `POST /workspaces/{id}/ingestions` or `/libraries/{id}/ingestions`: authenticated
  multipart `file` + the existing strict `metadata`, plus an `Idempotency-Key`
  containing 16–128 ASCII letters/digits or `._:-`. The gateway forwards this header.
- The API verifies current write scope before consuming/parsing the body. It retains
  the 10 MiB original limit and two concurrent body admissions per API process.
  Shared queue admission is checked before writing an object, after bounded parsing
  and hashing. This does not replace ingress bandwidth limits.
- A fingerprint covers actor, scope, original bytes, filename and all client metadata.
  The first reservation separately pins the server processing manifest, so a later
  server model update cannot retarget or invalidate an identical client replay. A short committed reservation records the exact
  prospective document/version UUIDs, expected version/publication revision, original
  key/hash and retention settings BEFORE an S3 write occurs.
- A conditional retained PUT happens outside SQL transactions. If an earlier PUT
  succeeded but its response was lost, a retry pins the existing storage version
  only after fetching/verifying its bytes against the reservation hash. It never
  overwrites an original or changes its prospective document/version IDs.
- A second SQL transaction creates the immutable submission, queued job, acceptance
  event and accepted reservation together. `202` means this committed acceptance,
  not successful extraction/indexing/publication. Queue rows are the PostgreSQL
  transactional outbox; there is no separate external broker to notify or lose.
- Replaying an accepted identical request returns the same currently authorised job.
  Changed requests/key collisions return generic 409 without another scope's IDs.
  An identical request already uploading returns 409/in-progress; retry the same key.
- `GET /jobs/{id}` returns bounded status fields under current read permission.
  Proposed version IDs have no public original/passage route until later publication.
  Job IDs and idempotency keys do not grant access. Revocation blocks current reads.

A NOLOGIN/non-bypass function owner performs shared admission counts through fixed,
parameterised SECURITY DEFINER functions with a fixed search path. It inherits the
caller's principal-scoped content policies and has additional job-metadata access
for global counts. Runtime is not a member of this role and cannot SET ROLE to it.
Runtime cannot directly INSERT/UPDATE/DELETE job records or SELECT private upload
tokens, raw reservation metadata or submission object-version identifiers. Functions
verify caller/target/fingerprint rather than trusting a browser-supplied principal.

Shared limits in this stage are 8 live reservations/nonterminal jobs per organisation
and 32 globally. The fixed SQL limits include hidden restricted workspaces; replicas
cannot multiply the limit. Admission uses a short global transaction lock, with
5-second lock, 10-second statement and 15-second idle-transaction timeouts on the
service's SQL transactions. Objects/model work never runs under this lock. Fair
scheduling and configurable worker concurrency are a later review stage.

## Capability and revocation boundary

| Identifier/capability | Permitted action | Expiry and revocation |
| --- | --- | --- |
| Existing browser session | Submit to permitted scopes; read permitted job status | Existing eight-hour/session revocation and disabled-user checks, plus current membership/grants on every call |
| Private upload token | Accept or release only its exact reservation/original manifest, bound to the submitting principal | Fifteen-minute database-time lease; matching reclaim replaces the token; expired/stale token cannot accept or release a newer claim; current write membership rechecked after storage I/O |
| Accepted job ID | Identification only, no bearer authority | Durable row survives browser session expiry; status still requires a fresh valid session/current scope |
| NOLOGIN admission function owner | Fixed reserve/accept/release operations; shared metadata counts | Not an application login or worker identity; no public execution, role escalation, claiming, publication or deletion API |
| Worker capability | Not implemented/granted in stage 1 | Stage 2 must bind job, actor, organisation, workspace/library, document/version, processing manifest, allowed stage and a monotonically fenced claim generation to an expiring lease |

For the next worker stage, the proposed lease is 60 seconds with 15-second
heartbeats. Every heartbeat/stage boundary, original fetch, vector batch and
publication must recheck actor-active/current write permission and processing
policy. Revocation must prevent further steps/publication; in-flight computation
cannot be retroactively recalled. Browser logout/expiry alone must not invalidate
otherwise-authorised durable jobs, so workers must not retain browser session
bearers. Claim/capability design needs its own review; schema fields are not proof
that those worker guarantees already exist.

## Failure, retention and current limitations

Storage errors and failed acceptance leave the reservation and any immutable
original for retry/inventory. Best-effort release expires only the caller's upload
token; a database outage or lost membership can leave it until lease expiry.
Crashes need no final callback: after expiry a matching retry reuses the planned
key and checks retained bytes. A stale uploader cannot accept with an old token.

Queued jobs do not publish or create rows in the existing document/version/passage
catalog. Existing originals, old citations and active pointers remain readable.
Expected active version and publication revision are captured for later conditional
worker publication, but that compare-and-swap is NOT implemented in stage 1.
Worker retries, progress transitions, failed worker-attempt records, stale-job
terminal states and Qdrant integration remain for the next review stages.

Upload failures before job acceptance currently have reservation provenance, not
per-attempt worker audit records. No durable job is promised before a 202 response.
An S3 success followed by SQL failure can leave retained data; inventory is necessary
and retention costs remain. A timeout can follow a committed acceptance; retry the
same key to discover the job. Objects may remain locked for the existing workspace
minimum (libraries: 365 days). New SQL hold policy does not automatically rewrite
previously stored object-lock metadata; future inventory must conservatively protect
SQL holds and stored retention/holds. No weakening/release/deletion is introduced.

The opt-in queue will stop admitting at its limits because this stage has no
consumers/cancellation. Keep it disabled outside synthetic acceptance until the
worker stage is reviewed. Scanned/invalid PDFs may be admitted as pending originals;
the later worker must reject unsupported/no-text documents clearly without
publication. OCR remains deferred. No hosted model/provider is called by admission.
Legacy pre-platform data is not imported, assigned ownership or rewritten.
