# Comprehensive CV answers: independent review handoff

Base: `2eadf4ad8b2cb0c851be68739afc9725b0ef27e6` on the separate Mac candidate lineage (application candidate `af5358f161d19fe6289316c5b4e224f9434bafa2`). This is not a main-compatible wholesale merge. Main remains separately controlled. No original Mac installation, customer documents, credentials or stored data were accessed or changed.

## Failure and correction

`/ask` previously always requested three ranked passages. In the synthetic seven-page CV, the first three passages contain Aster Research and Birch Analytics plus a skills passage; Cobalt Systems, Delta Robotics and Elm Computing occur later. Executing the baseline endpoint function with those controlled retrieval results reproduces an answer containing only two of five employers. See `validation/mac-comprehensive-answers/baseline-failure.log`. This isolates retrieval coverage; it is not evidence from a live Gemini request or the user's private CV.

Comprehensive questions now read every visible indexed chunk for the selected document, without embedding/reranking truncation. Automatic English detection recognizes whole words all/every/each/complete/comprehensive/entire/exhaustive. Callers can also set `comprehensive: true` on `/ask`; the existing frontend gateway forwards the body. Ordinary questions retain three-passage hybrid retrieval.

Complete coverage requires a selected document. Capture publication visibility once before scrolling, use batches of 64 without vectors, and retain original payloads and citation identities. Read-only coverage rejects missing/invalid source metadata rather than silently dropping it. Concurrent replacement cannot mix published revisions because existing revision points are retained by the unchanged publication implementation.

Bound the complete context to **1,500 chunks and 120,000 text characters**. This is a separate answer-context budget, not an upload-limit increase or claim about model tokens. Exceeding it returns HTTP 422 with a narrowing instruction, without generating an incomplete list. There is no multi-pass summarization or durable answer job. Per-query Qdrant timeout remains unchanged. This path runs in the existing synchronous endpoint's thread, not the API event loop.

The generation prompt requests examination of every supplied source, deduplication and every supporting source number. Existing document/page/chunk citations are mapped from those source numbers. Invalid non-integer citation numbers are ignored. Context is explicitly described as evidence rather than instructions. This does not establish comprehensive prompt-injection resistance or guarantee that a live model will always enumerate every item.

## Tests and results

Run from repository root with the existing backend environment:

```sh
backend/.venv/bin/python tests/test_mac_document_coverage.py
backend/.venv/bin/python tests/test_mac_upload_limits.py
backend/.venv/bin/python tests/test_mac_publication_server.py
git diff 2eadf4ad8b2cb0c851be68739afc9725b0ef27e6 --check
```

Results recorded in `validation/mac-comprehensive-answers/`:

- Baseline reproduction: only two of five employers reachable by generation; three missing employers recorded. Expected functional failure reproduced, not a failing test-suite run.
- Initial coverage suite: 4/4 passed (`coverage-first.log`). No failed implementation-suite run occurred.
- Final expanded coverage suite: 5/5 passed (`coverage-final.log`), real synthetic PDF ingestion and temporary local Qdrant. Actual generation prompt/JSON parsing tested with controlled provider output: all five employers and exact supporting citations. Also scope enforcement, both context caps, other-document exclusion, malformed metadata rejection, paginated publication race, explicit mode and unchanged ordinary top-three search.
- Existing upload/recovery regressions: 13/13 passed (`upload-regressions.log`). Includes resource admission, timeouts/cancellation, failed replacement, search publication race and lost publication acknowledgements.
- Real Docker Qdrant publication checks: 3/3 passed (`publication-server.log`). No customer data or original volumes used.
- Base-to-head whitespace check passed. PyMuPDF emitted its existing `swigvarlink` deprecation warning; suites completed successfully.
- `preservation.json` records unchanged upload/recovery, publication, inference, requirements, Docker/Compose, frontend and recovery-tool files against the exact base.

## Review boundary and limitations

Review the complete diff from the exact base and independently rerun the tests. The synthetic five-employer assertion uses a deterministic provider response whose stub also asserts that the **actual generated prompt contains every employer**. It proves ingestion-to-context-to-citation plumbing, not independent Gemini extraction accuracy. A live-provider evaluation remains outstanding; no external provider was sent document content in these tests.

Physical Intel Mac, Safari, VoiceOver, real-model performance and the user's private CV are untested for this fix. No frontend changes, document limits, worker controls, stored identities, recovery-helper behavior, data migration, cleanup or dependency changes are included. Large documents beyond the answer budget are explicitly unsupported for exhaustive questions. Legacy indexes missing text/citation provenance cannot be repaired by retrieval alone; re-indexing would need separate approval. Detection is an English heuristic, can over-trigger for words such as “each,” and does not cover all possible paraphrases; explicit API mode is available without a new UI control.

Request independent review at the submitted exact commit before any merge approval. Nothing is merged or deployed by this handoff.
