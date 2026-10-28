# ML/native remediation plan — not implemented

Planning base: framework candidate
`9ba24d1aa3f31cb076f8e66c71c3502454a8b306`.
No ML/native pin, model, data or deployed image changes in this plan. Review the
framework patch independently before authorizing the following work. Security
release block and disabled Web modes remain. No migration, merge, publication,
deployment, customer-data admission or paid resources are authorized by this plan.

## 1. Establish a compatible Python 3.11 CPU graph

On an authorized existing host with sufficient disk, use a clean Linux/amd64
Python3.11 environment and the CPU-only PyTorch index for its wheel. Retain
resolver commands, indexes, Python/OS/CPU details, full report and all failures.
Resolve the complete application requirements, not the current non-ML test subset.
Check Requires-Python, NumPy/SciPy/scikit-learn, tokenizers, safetensors, Hugging Face
hub, Transformers and sentence-transformers constraints together. Do not use
--no-deps, ignored requirements or a GPU wheel to claim this gate passes.
Inspect native wheel CPU/ABI support, including the Intel Mac's actual supported
instruction set and Docker memory allocation. No assumption that latest wheels
work on every Intel i5. Verify no unintended CUDA/NVIDIA packages enter the CPU
runtime. Install the resolved graph, run pip check and audit all resolved Python
packages as well as explicit pins; record wheel/model hashes and dependency sources.

The remaining five audited packages are fsspec, Pillow, sentence-transformers,
torch and transformers. Earlier advisory fix candidates include fsspec2026.6.0,
Pillow13.0.0, sentence-transformers5.6.0, torch2.13.0 and transformers5.10.0.
These are **investigation candidates, not selected compatible pins or proof of
complete remediation**. Use current upstream metadata and advisories when selecting.
If the graph has no defensible compatible solution, report the conflict and keep
the release blocked; do not waive it or quietly change Python/platform targets.

## 2. Submit small source candidates, with per-advisory evidence

- **Filesystem/image dependencies:** fsspec and Pillow may be separate candidates
  if the resolved graph permits. Test safe model-cache/filesystem handling,
  text-PDF parsing, unsupported/scanned/malformed input, bounded memory and normal
  inference imports. Use temporary synthetic fixtures only; no existing volume.
- **Coupled inference stack:** select compatible torch/transformers/
  sentence-transformers/tokenizers pins together when splitting would create an
  invalid intermediate graph. Change both the requirements torch pin and the
  CPU-wheel Dockerfile install in the same candidate. Update application-manifest
  hashes for changed build inputs. Preserve build CA/TLS trust, offline inference,
  model revisions and resource bounds. No framework or Web-feature changes.

Keep a ledger for every original and newly discovered advisory: ID/aliases,
installed candidate version, affected operation, reported fixed versions, test or
vendor evidence and explicit disposition. Preserve duplicate raw scanner records.
The six OPEN_NO_REPORTED_FIX IDs remain open unless upstream evidence establishes
a fix or an independently reviewed mitigation is defensible and explicitly
accepted. An absent audit record, safetensors-only download, a newer version or
passing tests alone does not resolve those IDs. If no safe solution is available,
retain the block; removal/replacement is a separate design decision.

## 3. Prove model and existing-index compatibility without migrating

Use the existing fixed model revisions and 384-dimensional embedding contract.
Inventory allowed model files and hashes; do not admit arbitrary repositories,
custom code, checkpoints, training/conversion paths or new model revisions to
avoid a dependency issue. Safetensors/offline settings reduce exposure but do not
prove the import/config advisories unreachable.

Run real CPU embeddings and reranker predictions on fixed synthetic passages.
Record score/vector tolerances and retrieval expectations before judging results.
Test retrieval against a synthetic Qdrant index created by the previous model
runtime, plus new ingestion; compare complete-document answers and citation source
identities. A numerical/model change that breaks compatibility must stop rollout;
no automatic re-embedding, index deletion, ID regeneration or migration is allowed.
Keep originals, points/payloads, publication revisions and citation IDs unchanged
when an attempted replacement, model startup or provider call fails.

Retain dense/text-heavy synthetic PDFs (not padded size alone), malformed/scanned
inputs, header/resource limits, timeout/cancellation, concurrent API responsiveness,
publication acknowledgements, search races and restart/recreation tests. Measure
whole-stack peak RSS/cgroup memory, CPU, processing stages, disk growth and latency
under the existing documented limits, including representative Intel Mac/8GB host
constraints. Do not increase limits or infer performance from mocked inference.

## 4. Rebuild, scan and independently accept the actual image

After source review, build the complete final image from the exact candidate on
an existing sufficiently resourced Docker host, with no runtime-file bind-mount
substitution. Record immutable local image/config ID, base/service image digests,
full build commands/logs and installed package inventories. Generate an SBOM and
run a current vulnerability scanner with its version/database time and complete
results. Cover OS packages, Python resolved transitives, Node, Grafana, Prometheus,
Qdrant and native libraries; account for bundled binaries the scanner misses.
Do not equate a zero npm or requirements audit with a clean image.

Independently run final-image and Compose authentication, all service links/assets,
monitoring queries, live synthetic Gemini answers/citations, upload-failure
preservation, resource/restart/recreation and core/monitoring-failure checks. Retain
failures and corrective reruns. Review exact source/image IDs and all unresolved
risks before seeking separate merge/publication/deployment approval.
Actual RunPod HTTPS/browser and attached-storage stop/start/forced-restart tests
remain a separate authorized acceptance gate; local tests cannot satisfy it.

## Recovery constraints

All experiments use fresh synthetic storage. Preserve the earlier image and its
configuration as evidence; do not overwrite or retag it as a new candidate.
Any rollback to vulnerable dependencies needs an explicit risk decision and must
not reset saved settings or data. No schema conversion, destructive cleanup or
irreversible operation is part of remediation. Existing Pod and Mac stay untouched.
