# Large-document ingestion — Stage 1 preservation and lifecycle contract

Status: submitted for independent review; not permission to proceed.
Repository: `hedobriggs/DocLens`.
Exact base: `31eb3455cd5dc02c47f343d62328d41c8a2c3458` (verified remote main).
This is Stage 1 of the newly approved large-document plan, distinct from the
already implemented Milestone 2 stage 1 durable-admission work.

## Authorization and implementation boundary

This stage defines requirements and synthetic preservation examples. It adds no
application behavior, migration, endpoint, worker, importer, runtime validator,
queue consumer, deletion capability, deployment configuration, dependency or
limit change. No customer data or Mac backup is accessed. Contract tests validate
the examples and source boundary; they do not prove future worker guarantees.
All requirements below describing workers or convergence are future acceptance
requirements, not claims about current main. Stage 2 needs separate authorization
following independent review of this exact Stage 1 commit.

## Approved sequence and dependencies

| Stage | Scope and review boundary | Dependency/exclusion |
| --- | --- | --- |
| 1 | Preservation, lifecycle, authority, resource accounting and publication contract; synthetic fixtures | This commit only; no schema/API execution |
| 2 | Additive worker controls: claims, progress, cancellation, leases/fences, checkpoint and reconciliation records | Reviewed contract; consumers remain disabled at schema review |
| 3 | Reserved streaming admission using existing reservation/submission/job transaction | Reviewed controls; existing live limits stay unchanged |
| 4 | Supervised bounded processing, immutable checkpoints, retries and restart recovery | Reviewed admission/control; no public incomplete versions |
| 5 | Private staging and bounded authorized retrieval | Separate review; publication disabled for new path |
| 6 | Complete-revision publication and uncertain-outcome recovery | Separate from staging/retrieval review; faults and races required |
| 7 | Durable browser progress, discovery, cancellation and reauthentication | Reviewed job APIs and terminal-state semantics |
| 8 | Whole-stack Intel Mac measurements and proposed support profile | Synthetic tests; measured limit increases need separate approval |
| 9 | Separately approved Mac convergence rehearsal on copies | Mapping/original/provenance checks; actual migration/cutover separate |

Each implementation stage supplies exact base/head commits, commands, fixtures,
failed runs, subsequent passing runs, limitations and an accessible handoff.
Independent review must precede any request for merge approval. No stage implies
permission to merge, deploy, admit customer data, increase limits or migrate it.

## Baseline facts to preserve

Read `docs/MILESTONE-2-STAGE-1.md`, migrations 001–003, `platform_jobs.py` and
`platform_api.py` at the exact base. Do not amend applied migration files/checksums.

- Existing PostgreSQL reservations pin prospective document/version UUIDs,
  expected active version/publication revision, client fingerprint, processing
  manifest, original key/hash, retention policy and an expiring private upload token.
- The reservation commits before the retained conditional original PUT. One SQL
  transaction accepts submission, queued job, accepted reservation and event.
  PostgreSQL is the transactional queue/outbox; add no separate queue/job catalog.
- An accepted replay identifies the same job under current authorization. NULL
  token/fingerprint rejection from migration 003 must remain regression-tested.
- Current durable admission is default-off, synthetic-only, at 10 MiB, with eight
  live reservations/nonterminal jobs per organisation and 32 globally. Current
  version schema caps pages at 100; synchronous ingestion caps passages at 1000
  and search rejects a workspace candidate set above 1000. Those are different
  constraints, not evidence of large-document support.
- Main has no worker claim, cancellation, processing progress or worker publication
  implementation. Existing job IDs are identifiers, not authority. Main's original
  read helper also has a 10 MiB read bound; later streaming changes must account
  for downloads/ranges, not just the upload endpoint.

## Mac preservation contract (must precede migration design)

The reviewed Mac application commit is
`76b81c1bf5a23fd62e344e893b1bff45e24e8cb4`. It uses a Qdrant server revision
catalog different from the platform SQL catalog. The recovery helper at
`37ac3223235b017b0aae4c7fa08667feb03976c7` has a separate review; this contract
neither approves it nor asks anyone to execute it. Do not merge recovery branches
wholesale into main or switch readers against incompatible data.

Any later authorized inventory must be read-only, private and local to the Mac.
Any copy/import/write needs the relevant separate approval. Never upload the
Mac's real metadata, document text, credentials, backups or images as test evidence.
Define and verify these preservation units before proposing a rehearsal:

| Unit | Required preservation evidence | Blocker / prohibited shortcut |
| --- | --- | --- |
| Existing Qdrant state | Server version, collection configuration/indexes, point IDs, vector bytes/numeric values, complete payloads, revision pointers and counts; consistent recoverable backup of the existing volume | Count-only comparisons are insufficient; no reset/recreate/overwrite of the original collection or volume |
| Originals | Exact bytes and SHA-256, filename as metadata, version-pinned storage locator when present, retention/holds and rights/provenance | Qdrant excerpts/embeddings cannot reconstruct or authenticate a PDF; a missing original blocks original-backed migration of that item |
| Platform identities | Existing organisation/workspace/library, document/version/passage IDs, original object versions, hashes, pointers/revisions, reference selections and audit records | Never rewrite existing UUIDs or infer tenant scope from a filename/content hash |
| Legacy citations | Exact legacy reference, source snapshot/version, page, chunk/excerpt and hash; availability/uncertainty explicitly recorded | Never retarget an old citation to the current same-name document or manufacture coordinates |
| Ownership/provenance | Explicit owner-approved mapping of legacy identity to scope, original, source dates and rights; unknown attribution stays unknown | Same filenames, same bytes or proximity in a directory do not establish ownership |
| Local recovery material | Modified and untracked files, backups, credentials, relevant runtime configuration and private recovery artifacts | Artifacts may contain plaintext secrets; no Git/registry/chat upload, deletion or silent replacement |

A compatibility mapping is append-only in meaning: each approved legacy reference
continues to resolve to its original evidence, not whichever version is active.
New platform IDs may be explicitly associated with a legacy namespace, without
rewriting historical references. Ambiguous unversioned filename citations remain
unresolved until independent provenance establishes their target. An excerpt-only
archive can remain preserved as such, but must not be described as an original-backed
citation. A blocker is item-specific; unrelated verified items are not automatically
blocked or approved. No mapping or importer is implemented in this stage.

The fixture includes two platform scopes with the same displayed filename, a
historical citation to a retired version, retained old/new legacy vectors and a
current pointer. It also includes explicit missing-original, unknown-owner and
ambiguous-source blockers. Synthetic attestations are fixture data, not owner
approval or real migration evidence.

## Admission, idempotency and resource reservations

Future streaming admission extends the existing reservation contract. A bounded,
authenticated preflight provides declared size/hash, strict metadata and expected
version. Commit scope-checked reservation and byte/resource budgets before scratch,
original or derived-artifact writes. Stream bounded bytes into reserved storage;
compute actual hash/size and reject mismatches before retained original PUT and
acceptance. Client declarations are never proof. Preserve first-reservation
processing manifest and prospective IDs across retries and server upgrades.

After a version-pinned retained original is verified, accept submission/job/event
and reservation state together in one SQL transaction. Model/storage I/O is outside
that transaction. A lost 202 does not undo a commit: current-authorized idempotency
lookup/job discovery must recover it without creating a second job. Before committed
acceptance, browser loss may require reupload; do not promise durable processing.

Reservations account for original, scratch, checkpoint and vector staging budgets.
Expired authority does not remove retained bytes. Keep uncertain writes charged
until reconciled; do not release persistent capacity merely because a lease expired.
Persistent-data cleanup is inventory/dry-run only, with no delete executor, grants,
lifecycle rule, hold release or automatic abort/delete of persisted uploads. Any
normal disposable scratch lifecycle must be explicitly approved; otherwise retain
and account for it and refuse further admission when full.

## Job lifecycle and current authority

Existing job states queued/running/retry_wait/succeeded/failed/superseded/cancelled
are the starting vocabulary. Future additive design must specify cancellation
requests and uncertain publication without overloading success or losing audit.

| Transition/condition | Required future behavior |
| --- | --- |
| Accepted -> queued | Same durable submission/job survives browser close/logout/session expiry |
| queued/retry_wait -> running | Atomic restricted claim; bounded global/per-scope capacity; increment fenced generation |
| running -> checkpoint/progress | Persist only verified durable units, artifact hashes and counters under current lease/policy |
| running -> retry_wait | Bounded backoff, same submission/version/manifest, at most existing three attempts; no blind duplication of uncertain external operations |
| invalid/no-text/resource limit | Clear bounded permanent failure, no publication; OCR may remain deferred |
| Current write permission lost / actor disabled | Stop further authorized processing; no publication; record non-content reason safely; restoration does not silently revive terminal work |
| Cancellation | Current-authorized idempotent request fences later work; cancellation/publication have one transactional winner |
| Lease lost | Reject old transitions/publication immediately; stale computation cannot be recalled but must not mutate a winning generation |
| Restart | Resolve prior publication outcome before retry; verify checkpoints and resume/recompute deterministically within budgets |
| Success | Only a complete, committed publication with receipt; queued or indexed is not success |

Worker capability binds actor, scope, job/submission, document/version, pinned
manifest, worker ID, allowed operation/stage, lease generation and database-time
expiry. Proposed starting lease/heartbeat are 60/15 seconds, subject to testing.
It grants no browser login, general SQL owner/BYPASSRLS, arbitrary impersonation,
shared storage administrator access, delete or publication outside its fixed path.
Use fixed narrow control functions/mediated operations, not trusted client scope.
Recheck current actor-active/write membership and processing policy at heartbeat,
original fetch, stage/checkpoint boundaries, vector batches and publication.
No worker depends on a browser session bearer.

One physical ingestion slot is the initial Mac target. A lease fence is not a CPU
kill: a supervisor enforces child lifetime, memory/CPU and termination, and confirms
old execution has exited before releasing local physical capacity. An unreachable
execution stays quarantined rather than being assumed stopped. Global controls
must not multiply with API replicas; fairness/multi-host scaling are later measured
capabilities. Provider processing remains disabled/synthetic-only.

Progress is database-backed, bounded and scoped: stage, durable pages/passages/
batches completed, known totals, attempt, timestamps, cancellation and error code.
Unknown totals remain unknown. Retry can repeat computation; distinguish durable
units from current-attempt work. Avoid fabricated percent/ETA. Terminal outcomes
clear UI busy state; a 401 requires reauthentication without cancelling accepted
work. Reconnected users get fresh permission checks. Tokens, object keys and
content are not exposed through status, events, metrics or error messages.

## Staging/retrieval boundary (Stage 5, publication disabled)

Existing version routes expose stored versions to scoped readers. Partial output
must therefore remain private in staging until publication, rather than being
inserted into the publicly readable version catalog. Retries reuse deterministic
new passage identity derived from pinned input/chunker rules; existing passage IDs
and citation hashes are never regenerated.

Use attempt-generation-specific vector/artifact IDs. An expired worker's late
Qdrant write can affect only its unselected namespace, never winning-generation
points. Complete staged manifests include counts, IDs, hashes, model revision and
artifact/object versions. Counts alone cannot prove completeness.

SQL resolves permitted published versions/generations before Qdrant candidate
search or lexical retrieval. Dense and lexical paths share that snapshot; bounded
candidate/top-k retrieval replaces unbounded corpus materialization. SQL supplies
canonical passages and rechecks current authorization and selected-version rules
before text reaches a reranker/provider or response. Changed publication selection
causes a bounded retry/failure, not mixed revisions or unauthorized candidate text.
Indexing existing platform data later must retain its existing passage IDs. No
Qdrant import, indexing or search implementation occurs in this stage.

## Publication/recovery boundary (Stage 6, independently reviewed)

SQL is the publication authority, not a claim of distributed atomic transactions
with Qdrant/S3. Verify all staged immutable output before a short final transaction.
That transaction validates live lease/generation, cancellation, current policy,
expected active version and publication revision, then atomically exposes the
complete version/passages, updates the pointer, marks the job successful, and
records a publication receipt/audit event. No external model/storage call holds
publication locks. Test actual lock duration for large promotions.

Permission revocation and publication require one explicit serialization protocol:
supported permission mutations must participate in the same guard/epoch scheme.
Acquire guards then re-read current permission in a fresh statement; an earlier
check or stale transaction snapshot is insufficient. An owner bypassing the
protocol is maintenance requiring workers to be quiesced, not a supported race.

| Uncertain outcome | Required reconciliation |
| --- | --- |
| Original PUT response lost | Inspect reserved immutable key/version; verify exact bytes/hash before acceptance; never overwrite |
| Vector batch response lost | Read immutable generation IDs and verify values/manifest before bounded retry |
| Publication commit response lost | Serialize with prior transaction resolution and inspect durable receipt for job/version/generation; no receipt before resolution is not proof of failure |
| Later publication already won | Receipt can prove earlier success even if active pointer changed again; never roll back the newer selection |
| Qdrant restart/index loss | Reconcile/rebuild from pinned durable evidence under scoped authority; fail clearly rather than exposing incomplete/wrong content |

Physical previous revisions and originals remain retained. Cancellation cannot
undo a publication that committed first. Runtime restoration is not a database
rollback; backups can be stale relative to newly accepted/published work. No old
reader may be pointed at a new layout without explicit compatibility evidence.

## Whole-stack Intel Mac resource evidence (Stage 8)

Target: Intel i5 MacBook Air, 8 GB physical RAM. Exact model/year, macOS, Docker
Desktop/VM resources and free space are still unknown. Do not extrapolate cloud
AMD throughput or ARM compatibility. Record CPU/thermal conditions, browser and
normal supporting services, whole-VM/host memory pressure and swap, plus every
resident model copy. Avoid overlapping an old and new stack just to benchmark
without accounting for their cost and separately approved downtime/copies.

Candidate experiment only: one execution, one CPU/thread and 1.5 GiB worker ceiling;
not a supported profile or a resource setting applied by this stage. Measure API,
worker, frontend, PostgreSQL, Qdrant, object storage, monitoring, browser, Docker
VM overhead/cache and host applications. Scratch tmpfs counts against memory;
disk-backed hard quotas must be verified on Docker Desktop. Preflight free-space
checks are not hard quotas or protection against unrelated disk consumption.

Test a small baseline and genuine text-heavy 28–30 MB PDFs (including approximately
650 pages/14.7 million extracted characters), images/scans, malformed/encrypted
PDFs and expansion/boundary cases. Record exact bytes/pages/chars/chunks/hash,
extractor/model revisions, warm/cold state, stage timing, memory/cgroup/cache,
scratch/persistent disk high-water marks, latency distributions and failures.
Oversized worker harness tests do not establish end-to-end upload support.
Proposed larger-profile end-to-end synthetic tests require explicit authorization;
existing live API/schema limits remain unchanged until measured, independently
reviewed and separately approved. No target is certified by these fixtures.

Proposed responsiveness gate for later review: health/auth/status p95 <250 ms,
p99 <1 second and no ingestion-induced timeouts/5xx. Establish sample count,
measurement overhead, duration, repeats and sustained-load/thermal effects before
claiming a result. Do not hide a failing stack by omitting normal services.

## Failure matrix, evidence and remaining decisions

Later stages must test restricted roles/RLS, NULL inputs, idempotency and acceptance
response loss; kill/restart at each checkpoint; stale worker/native-call overlap;
lease/cancel/revocation/publication races; original/vector/DB outages and lost ACKs;
partial staging; OOM, ENOSPC and disk quota exhaustion; source hash mismatch;
browser disconnect/refresh/session expiry/reconnection; complete old citation and
original access after failed replacement; and fail-closed cross-scope retrieval.
Each result needs actual outputs, exact source commit, synthetic fixture hashes,
commands/tool versions and clear failed/passed/skipped/unrun distinctions.

Unresolved: actual Mac capacity and support profile; approved scratch lifecycle;
precise control-function and permission-guard schema/API (Stage 2); API transfer
protocol and reservation renewal (Stage 3); checkpoint format/recomputation policy;
Qdrant durability/consistency and reconciliation time bounds; bounded retrieval
quality thresholds; actual original/provenance availability and owner mapping;
and separately approved migration/cutover/recovery procedure. None is resolved
by inventing a missing original, weakening retention, widening limits, automatic
cleanup, or treating Stage 1 contract tests as production acceptance.
