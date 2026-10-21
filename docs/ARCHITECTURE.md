# DocLens architecture

The frontend authenticates one configured administrator and forwards authenticated
requests to the private Python backend. Qdrant stores document chunks, embeddings
and publication pointers. Docker Compose exposes only the frontend on loopback;
an optional Caddy proxy supplies HTTPS. Backend and database ports stay private.

PDF parsing and embedding run through the existing bounded processing worker,
not on the API event loop. Limits remain 32 MiB, 300 pages, one million extracted
characters total, 100,000 per page and 1,500 passages. Backend processing is bounded
to 90 seconds; gateway/browser deadlines are 120/135 seconds. Cancellation is
cooperative. This is not a durable background job system.

Replacement stages a complete new revision and then changes a publication pointer.
Existing points are retained, including after failed or uncertain publication.
Retrieval captures one visibility snapshot, so concurrent replacements do not mix
revisions. Retired revisions accumulate; cleanup remains inventory-only. No
original PDFs, customer ownership or provenance may be inferred from filenames.

Ordinary questions use hybrid retrieval and reranking of three passages.
Comprehensive questions gather one selected document's visible passages, bounded
by 120,000 context characters and 1,500 chunks. Oversized requests fail explicitly;
they do not generate a truncated “complete” list. Detection is an English heuristic
and the API also accepts `comprehensive: true`.

Gemini receives the question and retrieved context and returns source numbers.
The API maps them back to document/page/chunk citations. Original-page viewing is
not implemented. Model output may still be incomplete or inaccurate.

Runtime memory controls remain backend 1,536 MiB/two CPUs and frontend 512 MiB.
Qdrant, Docker, models and host need additional capacity. These caps are not proof
that a whole installation fits an 8 GB Mac. Pinned models are built into the
backend image and operate offline at runtime; Gemini still needs network access.

The earlier workspace/durable-admission platform, including PostgreSQL migrations
and storage reservations, is retained on `archive/platform-milestone-2` at
`31eb3455cd5dc02c47f343d62328d41c8a2c3458`. It is not part of the default PDF
application after the authorized consolidation. Existing platform databases and
volumes remain untouched; restoring its code is not a data migration.

Root Compose startup adds one short-lived setup container, not a background job
system. It has no network, sees initial credentials only as a read-only secret,
and writes role-separated private settings to `app_config`. The backend/frontend
mount that volume read-only as different non-root UIDs. Settings and session
identities persist across down/up; mismatching input, partial setup and an existing
unowned index cause rejection without replacement. API/frontend entrypoints load
only their own settings; parsing, inference, retrieval and publication are unchanged.
