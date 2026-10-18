# Synthetic contract examples — not importable customer data

`preservation.json` and the two tiny PDF originals are author-created examples.
IDs, scope/owner attestations, retention fields and storage version strings are
fictional. No service is contacted and these files must not be loaded into a real
catalog. Vectors are hand-authored unit vectors, not model output. The illustrative
legacy pointer ID is not an assertion about a real Qdrant catalog's ID algorithm.

The graph captures retained old/new originals, stable passage/excerpt identity,
same-name and same-byte documents in different scopes, old/new legacy vectors,
a historical citation distinct from the active pointer, and blocked mapping cases.
A positive case means eligible only for a separately approved rehearsal, not
permission to migrate or a simulated owner sign-off for actual data.

Offline tests check consistency, negative mutation examples and unchanged baseline
files. They do not implement a migration checker or establish live preservation,
RLS, publication, workers, performance, PDF extraction or Mac compatibility.
The PDF cross-reference checks are structural; a separately recorded parser check
can confirm their actual page text without implying ingestion/model validation.

The fixture-local `.gitattributes` marks PDFs as binary. Their standard fixed-width
xref entries contain spaces; SHA-256, structural and parser checks validate their
bytes. This does not disable whitespace checks for code, JSON or evidence logs.
