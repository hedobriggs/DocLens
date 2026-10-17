# Independent review handoff: Milestone 2 stage 1

Base: `474a50d5b8df21fab90df39e832d0163afda2ce2`.
Review branch: `milestone/2-durable-jobs`. Verify the exact commit supplied by the
user before reviewing. Review this stage separately; it is not a request to merge,
deploy, admit customer documents or approve later Milestone 2 stages.

Read `docs/MILESTONE-2-STAGE-1.md`, the base-to-head diff and
`docs/MILESTONE-2-STAGE-1-VALIDATION.md`. Reproduce the relevant checks independently.
Prioritize:

1. Incremental migrations: unmodified v1 source, truthful legacy checksum adoption,
   existing row/citation preservation, transaction rollback, checksum drift/downgrade
   detection, concurrent runner serialization and owner-only execution.
2. Fixed SECURITY DEFINER admission functions and their NOLOGIN owner: search path,
   inherited forced RLS, current actor/scope checks, global/organisation capacity
   counts, privilege escalation, private-column grants and append-only records.
3. Reservations before object writes; atomic submission/job/event acceptance; exact
   fingerprints and idempotency; version-pinned retained originals; response loss,
   crashes, expired tokens, current membership and replay after session expiry.
4. No publication by admission. Old document/version/passage identities and originals
   must survive, and proposed queued version IDs must remain unreadable as sources.
   Publication revision is captured, not a claimed implementation of worker CAS.
5. Default-off feature gates in API/gateway, authorization before multipart parsing,
   idempotency header forwarding, non-leaking status and the unchanged sync UI path.
6. Reviewer conditions: capability scope/expiry/revocation documented; no unmeasured
   performance claims; scans may be rejected later without publication; cleanup
   remains inventory/dry-run only and destructive eligibility/grace periods need
   separate agreement. No new deletion capability exists in this stage.

Commands (existing checkout; documented Python dependencies, Docker, Chromium):

```sh
backend/.venv/bin/python tests/milestone2/stage1.py
backend/.venv/bin/python tests/milestone1/acceptance.py
backend/.venv/bin/python -m unittest discover -s tests/milestone1 -p test_storage_portability.py -v
backend/.venv/bin/python -m unittest discover -s tests -v
backend/.venv/bin/python tests/milestone1/build_image.py
backend/.venv/bin/python tests/milestone1/image_smoke.py --durable-jobs
cd frontend
npm run lint
npm run build
npm run test:platform
npm run test:e2e
```

Tests use disposable real PostgreSQL/MinIO and generated synthetic credentials.
Only fixture embeddings for the retained synchronous path are deterministic; durable
admission performs no inference. No actual/customer documents, production database,
bucket or deployed service are needed. Raw current-run results are committed in
`validation/milestone2-stage1-*.txt`.

Known limitations are explicit in the implementation note: no workers, Qdrant,
processing/CAS, retries/cancel UI, reclamation or performance validation yet. Do not
translate durable enqueue success into ingestion/publication success. The queue is
not useful for normal uploads until reviewed consumers are implemented. Any previous
approval remains limited to the configuration/commit it actually covered.

Return prioritized findings, file/line references, acceptance checks and an
approve/request-changes recommendation. Do not modify code, merge or deploy.
