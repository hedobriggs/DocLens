# ADR 001 — Shared, permissioned document intelligence

Status: **Proposed for review**, 2026-10-16. No foundation migration is implemented
by this ADR. Insurance launches first; UK commercial property is a provisional
pilot hypothesis, not a confirmed customer requirement. Legal and HR later reuse
the foundation with separate source rules, templates and evaluations.

## Decision

Retain Next.js for the UI and FastAPI for the application API. Introduce PostgreSQL
for transactional metadata, permissions, immutable version records, publication
pointers, durable jobs/outbox and audit events; private S3-compatible storage for
originals/derived artifacts; and a Qdrant **server** for vectors. Run bounded workers
separately from web requests. Redis/Celery is not required initially: a leased
PostgreSQL job queue is adequate for the controlled pilot and keeps enqueue and
metadata changes in one transaction. Revisit scheduling only against measured load.

Local Qdrant plus a process lock is a transitional, single-owner repair, not the
multi-worker production architecture. Do not share its directory across processes.
SQLite publication pointers introduced by the reliability patch preserve visible
legacy data and isolate incomplete writes; they are not the target tenant catalog.
The current application has no tenant/workspace isolation and is not ready for
confidential multi-firm use. Migrate via a rehearsed, backed-up import, not a silent
in-place assumption that legacy filenames identify customer documents.

## Identity, storage and publication

- Organisations, users, memberships, workspace memberships and roles are explicit.
  Workspace reader/editor/reviewer/admin permissions are separate from organisation
  user administration. An organisation administrator does not automatically gain
  access to restricted workspace content. Policy checks run in the API, not the UI.
- Documents have opaque stable UUIDs; filenames are display metadata. Each upload
  creates an immutable version with hash, uploader, provenance, original-object key,
  extraction/chunking/embedding revisions, relevant dates and ingestion status.
  Replacement targets a document ID and expected active version, never a filename.
- Reference libraries are separate from claim/matter documents. Library permissions,
  authorised use/licensing, source authority, review state, jurisdiction and relevant
  dates are recorded. A workspace selects permitted library versions explicitly;
  no implicit cross-organisation sharing. Even approved reference text is untrusted
  as model instructions.
- Upload admission validates authorisation and quotas and stores an immutable private
  object. Metadata + job/outbox are committed together; orphan uploads are reclaimed
  by retention-aware cleanup. No object becomes readable merely because it exists.
- Workers claim jobs with `FOR UPDATE SKIP LOCKED`, leases, heartbeats, attempt limits,
  backoff and per-organisation/resource concurrency budgets. Version/model-derived
  chunk/vector IDs and an organisation-scoped idempotency key prevent duplicates.
  Lease loss stops publication; uncertain provider requests are not blindly retried
  where that could duplicate generation charges.
- Extract/embed/index into an unpublished version. A short SQL transaction locks the
  document, checks the lease and expected publication revision, then atomically
  publishes only a fully verified version. An older job cannot overwrite a newer
  selection. Failures/restarts leave the previous pointer intact. Qdrant writes are
  not distributed transactions: SQL is the publication authority; staged orphans
  are invisible and collected later. Retired versions remain for citations/audit.

## Enforcing access and preserving evidence

Use a non-owner PostgreSQL runtime role with forced row-level security, transaction-
local organisation/principal context derived from verified identity, and explicit
workspace policy joins. Never trust organisation/workspace IDs supplied by the
browser. Test connection-pool context reset and deny missing context. Workers use
scoped job capabilities/current policy checks; no general bypass role in request
handlers. Administrative maintenance is a separate audited capability.

For dense and lexical retrieval, first resolve permitted published versions in SQL,
then constrain Qdrant by organisation + workspace/library scope + exact version IDs.
Re-authorise returned records before model submission and response delivery; never
use vector payload filters as the sole security boundary. Downloads, citation
passages, job progress, reports and exports all repeat server-side checks, including
revocation. Keep Qdrant/object-store credentials and network access server-only.
Use an authenticated download/range gateway for originals instead of bearer URLs
that bypass subsequent workspace checks. In-flight data already sent to an approved
provider cannot be recalled after revocation: agree the processing policy before
real confidential data is admitted.

Citation records pin document/version/hash, page, chunk, text span and available
bounding boxes/excerpt hash. The viewer opens the immutable original at that exact
passage. OCR/layout uncertainty is explicit; unavailable coordinates must not be
invented. Findings pin the selected policy pack and evidence versions, reasoning,
assumptions and missing facts. Reviewer edits, overrides and reviewed exports have
immutable revisions and attribution. A changed policy pack invalidates old review
status rather than silently updating its citations.

Audit events are access-controlled, append-only records with actor, action, object
IDs and version references; runtime roles cannot rewrite history. Operational logs
and metrics exclude document text, prompts, names and other confidential labels.
Provider success/usage, worker queues, stage failures and publication health are
monitored without tenant/content labels. Configure retention, legal holds, encryption
and tested backups across SQL, originals and vector rebuild manifests together.

## Product boundary and trade-offs

Insurance produces **draft research findings for human review**, not automatic
coverage decisions, claim rejection or comprehensive legal research. Start only
with authorised uploaded material. Show potentially relevant cover, exclusions,
conditions, exceptions, conflicting provisions, missing evidence and open questions.
Prompt-injected document instructions cannot grant permissions, change system rules
or cause tools/exports to run. Policy/jurisdiction/date assumptions require confirmation.

Costs: three storage components, careful publication/reconciliation logic, per-route
policy testing and backup coordination. Benefits: tenant isolation, recoverable jobs,
correct versioned citations and reuse by Insurance, Legal and HR. Do not expand the
implementation until this ADR/backlog has been reviewed; quality thresholds require
an insurance professional's agreement before tuning or pilot readiness claims.
