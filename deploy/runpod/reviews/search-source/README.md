# Search-source dropdown follow-up

Base: `355afaffa3d1e6ab8156bded679229cc34e8d134`. This UI change is committed
separately from the security/manifest correction. Review the commit containing
this document against that base.

## Implemented behavior

A labelled native select replaces the static search-source text. **Documents
only** is the default and the only enabled mode. **Web only — unavailable** and
**Documents + Web — unavailable** remain visible disabled options. The adjacent
accessible description states Web search is unavailable in this version.
No fake Web result, silent fallback, new provider call or changed question payload.
The document selection, upload limits, resource controls and citations are unchanged.

The native browser control provides mouse and keyboard operation, labelled
semantics and the existing visible focus outline. It fits the toolbar at both
reviewed viewports; on narrow displays it takes a full toolbar row. Updated the
two application-manifest hashes for dashboard/CSS; no integrity check removed.

## Executed evidence

[evidence.zip](evidence.zip) contains complete logs, screenshots, browser JSON,
commands and source hashes. Existing `tests/mac_candidate_ui.cjs` now exercises
the new dropdown in addition to its prior upload/answer/citation checks.

- Production Next build and TypeScript: pass.
- Lint: pass.
- All six packaging checks: pass, including changed-source refusal before build.
- Browser regression: pass, **15 screenshots, 566 contrast samples, zero contrast
  failures**, keyboard focus, selector click, Tab/Shift+Tab, disabled Web options,
  default document value and unchanged synthetic question/document payload.
- Existing empty, processing, upload error, cancellation, completion, answer,
  citation and long-filename clipping checks pass at 1440×900 and 1280×800.
- JavaScript syntax and base-to-head whitespace: pass.

Retained failures: first build command ran from repository root (no package.json),
then the correct frontend-directory build passed. The first dropdown browser test
pressed Enter and reopened Chromium's native menu before expecting Tab to move
focus. It failed with the selector still focused. The corrected test explicitly
closes the popup using Escape, then verifies Tab/Shift+Tab. No sleeps or retries
mask that failure; original logs/screenshots and separate passing rerun retained.

These are maintainer-executed Linux Chromium checks against the real production
Next build with synthetic browser API responses and fixture authentication.
They are not native Mac/Safari/VoiceOver, live Gemini, full-container monitoring
acceptance or actual RunPod HTTPS/storage tests. No new image was built.

## Proposed Web implementation — not implemented or approved

A separate proposal must choose the search provider, permitted domains, costs,
privacy disclosure and outbound policy. Implement server-validated explicit modes
with document mode as default; reject unavailable modes rather than silently
falling back. Keep Web evidence separate from original-document citations.

For Web-only mode, bound query/result counts, response bytes, deadlines and cost;
if fetching external pages, prevent SSRF with approved destinations and safe
redirect handling. Treat fetched text as untrusted data, never instructions.
Preserve authentication, avoid sending document text to a search provider without
informed authorization, and do not store Web data as an original document.

For combined mode, label which claims use document evidence and which use Web
sources; document identity/citation IDs remain intact. Test provenance, prompt
injection, provider failures, no-results, cancellation, rate limits, keyboard
operation and privacy behavior with synthetic inputs. Enable each mode only after
its independent review and separate implementation/release approval.

Whole-image security findings remain open under the dependency-security report.
Actual RunPod acceptance, merge, publication and deployment are separate gates.
No existing data, Pod or Mac installation was modified.
