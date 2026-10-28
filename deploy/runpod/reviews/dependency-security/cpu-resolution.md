# Python 3.11 CPU candidate and scan evidence

Base: `b71c79fb0a84dec54b5ff7e940a2d8e7e8135f85`. Source candidate is the commit
containing this report. **Security release block remains; Web modes disabled.**

## Result and readiness

**Complete Python3.11.17 CPU graph resolved, installed and constraint-checked.**
73 runtime packages are pinned, including newly required transitives. Selected
ML/native pins: torch2.13.0 (official +cpu wheel), Transformers5.10.2,
sentence-transformers5.6.0, Hub1.5.0, Pillow13.0.0, fsspec2026.6.0. NumPy1.26.4
and fixed model revisions/384-dimensional contract are unchanged. No CUDA/NVIDIA/
triton runtime packages. Patched build pip26.2.2 is removed after dependencies and
models are installed; it is not an application runtime dependency.

**New final image ID/digest: NONE — not built.** Docker's VFS filesystem has only
5.5GiB free. It previously required multiple full image copies; attempting another
build would risk ENOSPC. No unrelated images/volumes deleted, storage relocation,
paid host, image publication, Pod, Mac, main or existing-data modification.
An existing sufficiently resourced Docker host is still required (conservative
headroom30GB free; at least10GiB after images are available for this VFS workload).

**Ready for independent CPU/source synthetic retest: YES.**
**Ready for isolated rebuilt-image retest: NO, image and final-image scan pending.**
This source candidate is not release/deployment approval. Native Intel Mac/8GB
whole-stack resource testing and actual RunPod HTTPS/storage remain separate.

## Dependency failures and real inference evidence

First resolve failed on old Hub0.36.2 versus Transformers>=1.5 Hub requirement.
Hub1.5.0 resolves. Initial Transformers5.10.0 install warned it is yanked; candidate
uses non-yanked5.10.2. All failures/warnings and successful resolution/install are
retained in evidence.zip under `cpu-resolution/`, including installed inventory,
CPU index provenance, final source resolution and source hashes.

Both fixed models load offline on CPU. Against the old Torch2.2.2 runtime and
same trusted snapshots, max embedding error is1.68e-7 and reranker error2.38e-6,
within predeclared1e-4 tolerance; minimum cosine>.99999 and synthetic rankings
against old vectors match. A real Qdrant-local index seeded with baseline vectors
also retrieves the expected employer using the candidate query/reranker. This is
finite synthetic compatibility evidence, not proof for every existing document.

A genuinely dense32-page synthetic PDF (222980 extracted characters,595732 bytes,
not padded to12MB) indexes288 chunks in11.893s. At20Hz health sampling:224 probes,
worst28.8ms,p954.59ms. Process peak835004KiB (~815MiB). Failed replacement returns
400 and preserves exact synthetic IDs/payloads. The first successful ingestion's
harness failed after flooding10000 probes; that failure and corrected measurement
run are retained. Measurements are cloud-only: not whole-stack Mac performance.
No live Gemini or customer document was used.

Final Python3.11 runtime: **13 dependency +57 application +6 packaging =76 checks
pass**, including framework/auth, metrics, limits, failures, publication/search
races and citations. Packaging guard preserved. Existing browser/UI and actual
image/Compose acceptance have not been relabelled as passes for these dependencies.

## Audit/SBOM findings — scopes kept distinct

- Explicit pinned graph/public-version audit: no reported known findings. The
  installed audit cannot find `torch2.13.0+cpu` on PyPI; the skip is retained and a
  separate base2.13.0 public-version audit is recorded. Neither proves the CPU
  wheel safe or resolves advisory IDs with unknown fixes.
- **Six original no-reported-fix IDs remain OPEN_NO_REPORTED_FIX**, even though
  absent from the new version audit: torch PYSEC-2025-189/190/192, PYSEC-2026-139;
  transformers PYSEC-2025-217, PYSEC-2026-4174. Complete per-ID ledger retained.
- Top-level audit initially found six distinct installer-pip IDs (12 raw records).
  Updating build pip did not fix its bundled dependencies. Trivy rootfs found
  eight findings in pip's vendored msgpack, setuptools and urllib3. Removing pip
  from the temporary runtime removes these components; final environment scan
  recognizes85 entries with zero findings. **Final image removal still unverified.**
  Ledger retains all eight findings with that conditional disposition. No ignore
  filters, risk waivers or substituted top-level libraries used.
- Plain Trivy `fs` did not recognize environment packages; its empty output is
  retained as a failed-coverage attempt, not a clean scan. `rootfs` recognizes
  package/vendored SBOM metadata. Runtime CycloneDX SBOM included. The environment
  scan excludes its external Python interpreter, OS, complete image and any
  components not detected by the tool. ensurepip/bundled installers, native wheel
  libraries and final runtime binaries require final-image inspection.

### Historical image scan — NOT this candidate

Read-only scan of existing image
`sha256:ce23cbb8278ab8ede485603d606340c065df280202788c959517a15079329f27`
(the older published d909540 image) produced706 detection instances:13 critical,
192 high,326 medium,132 low,43 unknown, across OS/Python/Node and monitoring Go
components. These are component instances, not706 distinct CVEs. CycloneDX SBOM
has2641 components. Raw scan, commands and DB metadata retained. No claim that
those historical findings persist or are fixed in an unbuilt image. No candidate
image digest is borrowed from this baseline or the accepted Mac trial image.

Scanner: Trivy0.76.1, official release checksum verified; database updated
2026-10-28T13:01:10Z, downloaded18:33:02Z (UTC). Exact metadata retained. Scanner
coverage does not establish Qdrant Rust-binary or standalone Node-runtime security;
manual inventory/current scanner coverage remains required.

## Remaining blockers / review boundary

1. Independently review these exact pin/build changes, complete graph, source
   regressions, model evidence and per-advisory dispositions. No-fix IDs need
   upstream fix/removal evidence or defensible independently reviewed mitigation
   plus explicit risk acceptance; passing inference and absent scanner records
   are insufficient. No such waiver is requested here.
2. On an authorized existing host, build exact final image, record its real ID,
   inspect installer removal/full inventory, generate SBOM and scan all OS/native/
   service components. Resolve or explicitly review findings; keep the release
   blocked. Do not deploy the historical image as a substitute.
3. Run exact-image and Compose isolated synthetic login, all service roots/assets,
   live Gemini answers/citations, upload/failure preservation, resource bounds,
   restart/recreation and failure handling without runtime bind substitutions.
4. Actual RunPod HTTPS/browser and attached-storage stop/start/forced-restart
   acceptance, merge, publication and deployment require separate authorization.

No migration, reindex, citation-ID change, raised limits or destructive cleanup.
