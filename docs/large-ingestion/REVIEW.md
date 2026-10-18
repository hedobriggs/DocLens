# Independent review — large-ingestion Stage 1 only

Repository: `hedobriggs/DocLens`.
Base: `31eb3455cd5dc02c47f343d62328d41c8a2c3458`.
Branch: `plan/large-ingestion-stage-1`.
Exact head: supplied in the review submission; verify it before reviewing.
Do not substitute a different branch head or review this as an implementation of
later stages. Main must remain unchanged. Review approval is not merge approval.

Read `STAGE-1-CONTRACT.md`, `VALIDATION.md`, the base-to-head diff and synthetic
fixtures. This stage defines the contract, not worker/control schema or a data
migration. No existing baseline tracked file should differ. The Mac helper review
at `37ac3223235b017b0aae4c7fa08667feb03976c7` remains separate.

Review priorities:

1. Is the existing reservation/idempotency/atomic acceptance system reused, with
   existing defaults, NULL-safe authority checks and limits retained?
2. Are Mac preservation requirements defined before migration, including exact
   Qdrant state, originals, provenance, reference selections, audit and citation
   identities? Do missing originals, unknown ownership or ambiguous filename-only
   citations block the relevant mapping without fabricated source evidence?
3. Are worker/session authority, cancellation, progress, leases/generation fences,
   physical execution limits, retries and restart requirements precise enough to
   guide Stage 2 without claiming they already exist?
4. Are staging/retrieval and publication/recovery separate review boundaries,
   including private staging visibility, permission/publication serialization,
   immutable generation namespaces and transaction-resolution/receipt semantics?
5. Are whole-stack Intel i5/8 GB measurements, provisional limits, persistent byte
   accounting and inventory/dry-run-only cleanup explicit? Does any proposed
   scratch lifecycle still require approval rather than becoming a deletion loophole?
6. Do tests truthfully distinguish fixture consistency, expected negative controls,
   baseline byte preservation and PDF parsing from unrun production/Mac guarantees?

Commands (Python 3.8+; PyMuPDF needed only for the separate PDF parser evidence):

```sh
python -m unittest discover -s tests/large_ingestion -p 'test_*.py' -v
python tests/large_ingestion/reproduce_negative.py
git diff 31eb3455cd5dc02c47f343d62328d41c8a2c3458 HEAD --check
git diff --name-status 31eb3455cd5dc02c47f343d62328d41c8a2c3458 HEAD
```

Negative-control output deliberately contains two failing assertion traces. The
control runner succeeds only when both disposable corruptions are caught. The
normal suite then passes against unchanged repository fixtures. These are not
unexpected implementation failures or proof a migration succeeded.

Expected scope: only new `docs/large-ingestion/`, `tests/large_ingestion/` and
`validation/large-ingestion-stage1/` files. No service startup, backend/frontend
build, migration, importer, limit increase, deployment or real-data access is part
of this stage. Do not request a live migration just to validate this contract.

Return approve/request-changes, prioritized findings and conditions for Stage 2.
Stop after review. User authorization is required before beginning Stage 2; any
merge, migration, larger live limits, deployment or customer-data admission remains
separately approved. No future implementation commit is implied by this handoff.
