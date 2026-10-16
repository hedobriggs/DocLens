# Reliability fixes and foundation proposal — independent review

Local branch: `fix/ingestion-reliability`.
Base: `00fada211a0a663e053132fa2559a896abe9036f` (the previously approved/pushed head).
Implementation + architecture commit: `7baee9de9246b00cd4023d7cdc8a2f3783320e29`.
The final review head adds this report and raw test evidence only. No new commit
or branch has been published; no deployment, main push, force-push or merge occurred.

## Reliability changes

All production local-Qdrant reads/writes now share a reentrant process lock. The
supported SQLite cross-thread option is enabled **with** that lock, not by itself.
Replace no longer deletes old data first: fresh revision-tagged points are staged,
then a SQLite publication pointer is committed transactionally. Dense, BM25 and
hybrid search and storage counts all use the published view. Partial vector writes,
failed pointer commits and pre-publication process death leave prior data visible;
incomplete first uploads remain invisible. Existing unversioned data remains
visible until its filename is successfully replaced. Publication metrics failures
after commit do not turn a successful upload into a reported failure.

Cost configuration is optional, finite and nonnegative. Missing/incomplete,
malformed, negative, nonfinite and overflowing estimates never invalidate a valid
answer. Provider-reported token metrics and successful-generation operation metrics
still update. Invalid/unavailable costs have **no cost sample**, plus a bounded
`doclens_gemini_cost_estimate_skipped_total{reason=...}` counter. Valid zero prices
correctly produce a supported zero cost sample. Config values never become labels.
Provider exception bodies/traceback chains and document filenames/passages are
excluded from application generation/retrieval logs.

## Exact checks

Final source was tested from a clean local clone:

```sh
umask 022
git clone --no-hardlinks --branch fix/ingestion-reliability /workspace/DocLens /tmp/doclens-reliability-clean
cd /tmp/doclens-reliability-clean
set -o pipefail
/workspace/DocLens/backend/.venv/bin/python -m unittest discover -s tests -v \
  2>&1 | tee /tmp/doclens-reliability-tests-final.txt
```

**Exit 0; 31 tests passed in 35.161 seconds (Python 3.12).**
Raw output: `validation/reliability-tests.txt`.

| Group | Count | Dependencies/evidence |
|---|---:|---|
| Pricing and log privacy | 13 | Real answer/metric code; provider response/error mocked; no live Gemini |
| Storage reliability | 10 | Real Qdrant/local SQLite, real PDF parsing/chunking, deterministic model substitutes |
| Existing monitoring | 2 | Dashboard references plus real metrics/Qdrant with model/provider isolation |
| Existing upload HTTP checks | 6 | Endpoint/auth/size/health/metrics checks with storage/model isolation |

Storage cases cover eight simultaneous same-filename uploads; eight different
filenames; partially written replacement; failed catalog publication; failed first
upload; retries; fresh Python-process reopen; abrupt `os._exit(23)` after staged
writes; existing unversioned data; and retrieval plus health/metrics during failed
replacement. Counts refer to **published** documents/chunks, not retained physical
points. The 60-page dense-text fixture asserts at least 180 chunks; it is not a PDF
padded with whitespace. The earlier padded 25 MiB transport test remains separately.

Production-dependency compatibility, same clean source mounted read-only into the
previously built CPU backend image:

```sh
set -o pipefail
docker run --rm --entrypoint sh \
  -v /tmp/doclens-reliability-clean:/src:ro -w /src doclens-review-backend \
  -c 'python -m pip check && python -m unittest discover -s tests -v' \
  2>&1 | tee /tmp/doclens-reliability-container-final.txt
```

**Exit 0; no broken requirements; 31 tests passed in 32.997 seconds (Python 3.11).**
Raw output: `validation/reliability-container-tests.txt`. This validates current
source against production dependencies, not a rebuilt/deployed release image.
The temporary container was removed. Both runs have a PyMuPDF SWIG deprecation
warning; no failed, skipped or expected-failure tests were reported.

Real-model check, clean checkout, offline cached models:

```sh
set -o pipefail
HF_HOME=/workspace/.cache/huggingface HF_HUB_OFFLINE=1 OMP_NUM_THREADS=2 \
  /workspace/DocLens/backend/.venv/bin/python tests/real_model_concurrency_smoke.py \
  2>&1 | tee /tmp/doclens-reliability-real-model-final.txt
```

**Exit 0.** Four simultaneous genuine 10-page synthetic PDFs (two same filename,
two distinct) used real embeddings, reranking, local Qdrant and SQLite. All uploads
returned 200; settled view has **3 documents, 60 active chunks**, with exactly one
complete active revision for the replaced filename. Filtered hybrid retrieval
passed. No Gemini request was made. Selected stdout is in
`validation/reliability-real-model.txt` (progress bars omitted).

`backend/.venv/bin/python -m py_compile backend/*.py tests/*.py` and `git diff --check` passed.
Frontend was unchanged, so its build/browser suite was not rerun for this patch.
Historical monitoring/deployment evidence in `VALIDATION.md` pertains to the earlier
branch, not a claim that this new commit was deployed or independently reviewed.

## Scope and outstanding acceptance

This remains a **single-process**, single-admin prototype: one owner of local
Qdrant, no `uvicorn --workers N`, multiple replicas or shared-directory workers.
Concurrent same-filename replacements use last successful publication order, not
arrival order. Filenames remain legacy identity only in this repair. No tenant or
restricted-workspace isolation, durable job queue, stable document IDs, immutable
original files, exact-version citation viewer, insurance reports/review workflow
or exports have been implemented here.

Retired/unpublished vectors are retained and filtered out; physical storage grows
until retention-aware cleanup is implemented. No automatic deletion is introduced.
Back up the whole `qdrant_data` directory, including `publications.sqlite` and Qdrant
metadata, with the owner stopped; do not treat unrelated live file copies as a
consistent snapshot. Restore drills, storage-device failure/power-loss behaviour,
model/provider capacity bounds and multi-worker fault recovery remain unverified.
A failed post-commit metric refresh may temporarily leave gauges stale.

The architecture/backlog are proposals before further implementation:

- `ADR-001-shared-document-platform.md`: PostgreSQL/RLS, private originals,
  transactional jobs, service-backed Qdrant, conditional publication and exact citations.
- `MVP-MILESTONES.md`: the four requested milestones and concrete gates, with
  tenant/workspace route isolation, jobs/restarts, reviewer exports and pilot/restore checks.
- `INSURANCE-EVALUATION-PLAN.md`: 20 candidate scenario specifications. These are
  **not** professionally adjudicated expected findings or completed evaluations.
  Expert thresholds must be agreed before tuning. UK commercial property is provisional.

No live Gemini success/token billing, deployed upload/proxy limits, full backup
restoration or professional insurance evaluation was performed in this revision.
No production-readiness claim is made. Use synthetic data until isolation and
processing-policy gates pass. Do not approve automatic coverage decisions, claim
rejection or claims of comprehensive legal research; authorised uploaded references
and human review bound the proposed insurance workflow.
