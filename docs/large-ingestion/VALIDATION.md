# Stage 1 evidence and limits

Base is verified main `31eb3455cd5dc02c47f343d62328d41c8a2c3458`.
Evidence is committed under `validation/large-ingestion-stage1/`.

- `contract-tests.txt`: 11 offline checks passed. They verify original fixture hashes,
  byte sizes/PDF offsets, graph/excerpt references, pinned library selection,
  accepted-but-unpublished job identity, cross-scope filename/hash ambiguity,
  historical versus active versions, blocked mapping examples and corruption
  examples. One check compares every baseline tracked file's Git blob digest:
  all 133 are byte-identical, including code, migrations, locks and configuration.
- `expected-negative-controls.txt`: two deliberate corruptions in temporary copies
  produce the expected failing assertions: changed original bytes and a historical
  citation retargeted to the active version. Runner exit 0 means both were caught;
  the normal suite subsequently passed unchanged. No unexpected test failure occurred. The initial whitespace check did fail on
  valid fixed-width PDF xref entries; `first-whitespace-failure.json` records it.
  Fixture-local attributes correctly classify PDFs as binary; all text files
  remain subject to whitespace checking. Original PDF bytes were not modified.
- `pdf-parser.txt`: PyMuPDF 1.26.5 opens both synthetic PDFs, checks their single
  page, exact extracted text and original SHA-256. This is not ingestion/inference.
- `environment-and-fixtures.json`: interpreter/platform, fixture hashes, exact base,
  protected file count and scope. No environment variables, credentials, user data
  or content from a Mac backup are recorded.
- `scope-and-whitespace.txt`: staged change scope, protected baseline counts and
  whitespace verification.

The normal checks need Python's standard library and Git only; no installation,
configuration-draft change or running service is needed. The separate parser check
reused the existing `/tmp/doclens-search-review/bin/python` environment and performs
read-only parsing of the two committed synthetic files. Reproduction:

```sh
python -m unittest discover -s tests/large_ingestion -p 'test_*.py' -v
python tests/large_ingestion/reproduce_negative.py
python - <<'PY'
import hashlib, json, fitz
from pathlib import Path
root=Path('tests/large_ingestion/fixtures')
for original in json.loads((root/'preservation.json').read_text())['originals']:
    data=(root/original['fixture_file']).read_bytes()
    with fitz.open(stream=data,filetype='pdf') as pdf:
        assert len(pdf)==1 and pdf[0].get_text().strip()==original['text']
    assert hashlib.sha256(data).hexdigest()==original['sha256']
    print('PASS', original['fixture_file'], fitz.VersionBind)
PY
```

No new database migration, storage write, worker, progress API, Qdrant change or
model call is exercised. Existing runtime suites, container/browser builds and
large-PDF benchmarks were not rerun: application/runtime files are unchanged and
this stage implements no runtime behavior. Existing migration acceptance evidence
belongs to its previously reviewed commit, not a fresh guarantee from this stage.

Not established: actual Mac originals/provenance availability, a complete live
inventory, live RLS/permission or cancellation behavior, worker fencing/restart,
publication atomicity, browser reconnection, restore/cutover feasibility, whole-stack
Mac resource budgets or support for a 28 MB document. Those are explicit later
review/approval gates. Fixture oracles are test examples, not a production
preservation validator or an importer. No live Mac inspection or data migration
was attempted. Frontend recovery-helper review remains separate.
