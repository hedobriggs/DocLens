# MVP milestone backlog — proposed

Next deliverable is the reliability patch + this plan, not a production platform.
Keep implementation local until explicitly approved for publication/deployment.
Use synthetic documents first. Sector-specific customer discovery must confirm the
pilot, jurisdiction, document rights and report needs; UK commercial property is
provisional. Legal/HR reuse the foundation later, not insurance assumptions.

## Review prerequisite — current reliability patch

- Serialize all local Qdrant reads/writes and support worker threads safely.
- Stage replacement vectors, commit a durable publication pointer, retain previous
  searchable data after partial writes or failed publication, and count visible
  documents/chunks only. Test same/different concurrent uploads and restart/retry.
- Optional Gemini prices cannot break valid answers. Validate absent/incomplete,
  malformed, negative, nonfinite, overflow, valid and zero prices; assert token,
  operation, skipped-estimate and cost metrics. Separate provider mocks from live tests.
- Record exact commits/commands/results and single-process limitations. Do not
  describe this repair as stable document identity, multi-tenancy or durable jobs.

## 1. Organisation/workspace isolation and versioned document access

Implement one vertical slice: sign in -> select permitted workspace -> upload a
version -> open its authorised original/citation. Introduce PostgreSQL migrations,
verified user identity, role/membership policies, RLS and the private object store.
Create document/version/provenance records and separate reference-library records;
provide stable IDs, content hashes and relevant dates. Require explicit membership
for restricted workspaces. Define retention/legal-hold and provider-processing policy.

Gate: two synthetic firms, several users/roles, and two restricted workspaces in
one firm cannot access each other through lists, guessed IDs, search (dense AND
lexical), passages, range downloads, job status, report/export routes or errors.
Test denied access before body parsing, pooled DB context leakage, membership
revocation, expired sessions, forged scope fields and library grants. Internal
services are not browser-accessible. Existing single-admin data is migrated only
through a reviewed, rehearsed mapping; never infer ownership from filename.

## 2. Durable ingestion, retries and atomic publication

Implement the transactional queue/outbox, leased bounded workers, admission quotas,
progress/status, immutable staging and conditional publication. Add deterministic
vector/chunk IDs, explicit model/extractor versions, recovery/reconciliation and
retention-aware orphan cleanup. Keep immutable originals and failed-attempt audit
records. Use Qdrant server, not a shared local directory. Publish via expected-version
compare-and-swap; retries must not supersede newer reviewer selections.

Gate: simultaneous same-ID and different-ID uploads, duplicate/replayed requests,
worker crashes at each boundary, lease expiry, queue/database/vector outages and
server restarts do not corrupt or duplicate the active corpus. Failed replacements
preserve the previous version and citations. Resource use stays within agreed
budgets under dense-document load; health/metrics remain responsive. Test genuine
multi-page text/scanned documents, not only padded files. Prove a restarted worker
resumes a durable job without a second visible publication or uncontrolled billing.

## 3. Insurance research, cited findings, review and export

Build claim-workspace creation and policy/evidence upload roles. Require confirmation
of selected wording, schedule, endorsements, jurisdiction, policy period, event dates
and source versions. Do not infer contractual priority from upload order. Generate
structured draft findings with reasoning, cited policy AND relevant claim evidence,
assumptions, missing facts, possible exceptions/conflicts and unresolved questions.
Provide exact-version passage viewer, reviewer edits/actions and a reviewed-report
export tied to immutable report/version hashes. Review status cannot survive silent
source substitution. Audit read/review/export activity with server-side authorisation.

Gate: automated fixtures cover endorsements, conflicts, time boundaries, missing
sources/facts and malicious instructions in documents. Malicious text cannot request
other workspaces, run tools, expose secrets or mark a draft reviewed. Exports resolve
all cited passages in the selected versions; stale/revoked sources block or explicitly
invalidate review/export. Never automatically decide coverage or reject claims.

Before tuning, agree quality thresholds with an insurance professional against at
least 20 realistic synthetic or authorised anonymised scenarios (see evaluation
plan). Professional expected findings, jurisdiction assumptions and adjudication of
ambiguous examples are required. Do not substitute model self-grading or engineer
expectations for that sign-off. Legal and HR later need their own templates,
jurisdiction/date/source rules and professional evaluation sets.

## 4. Deployment validation and controlled pilot

Validate the full deployed path (TLS/reverse proxy/browser/API/workers/object store/
SQL/Qdrant), dense upload limits, worker bounds and provider rate/usage behaviour.
Verify live Gemini success, measured tokens and configured estimate limitations;
never put secret values in chat, source, logs or reports. Test administrator-only
monitoring, alert delivery, permission failures and all-source backup restoration.
Rebuild vectors from pinned originals/extraction manifests and reconcile publication
pointers. Agree recovery time/point objectives and test them, rather than inventing
unmeasured readiness claims.

Gate: repeatable clean deployment, restore drill, isolation matrix, agreed professional
quality thresholds and representative load all pass. Confirm an authorised customer/
sector pilot, consent/data-processing/retention requirements, human review ownership,
incident handling, rollback/kill switch and scope limits. Begin a small monitored
pilot; expand only on evidence. No production-readiness declaration while live
provider, deployment, restore or review-quality checks remain outstanding.
