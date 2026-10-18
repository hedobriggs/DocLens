# Main-compatible dashboard usability — independent review

Repository: `hedobriggs/DocLens`. Review ref: `refs/heads/ui/main-compatible-usability`.
Baseline: `31eb3455cd5dc02c47f343d62328d41c8a2c3458`.
This is a new UI port based directly on that baseline. The earlier Mac review at `d0980c6c5ea07032cc5c060ff726b8042c9bef51` does not approve this integration. Its recovery branch is not merged or copied wholesale. Independent review is pending; nothing has been merged, deployed, migrated or installed on the Mac.

## Scope and deliberate compatibility differences

Product changes are limited to `frontend/app/dashboard/page.tsx`, its dashboard layout and `globals.css`. The existing upload regression selector is scoped to dashboard alerts; two standalone review harnesses and this evidence are added. Backend code, migrations, API routes, proxy/authentication, Docker/Compose configuration, package declarations and lockfile are unchanged.

- Keep the two-column dashboard. Improve secondary text, primary-button contrast, keyboard focus and spacing. Retain the authenticated Monitoring navigation. Use a flex height layout so that navigation does not push the composer below the viewport.
- Show pending filename, combined uploading/processing status, absence of detailed progress, live completion and error alerts. No fabricated stages, percentages or durable-job claims.
- Preserve main's existing **50 MiB legacy upload limit**; display it before file selection. Do not introduce the Mac-specific 32 MiB, 300-page or extracted-text limits. The separate platform uploader's existing 10 MiB/100-page policy is untouched; the legacy dashboard remains inaccessible in platform mode.
- **Cancellation is not ported.** Main has no reviewed cancellation propagation through its gateway. The UI says cancellation is unsupported and leaving the tab may not stop processing. It adds no Cancel control, AbortController, timeout or gateway behavior. The earlier Mac Cancel-button feature is excluded from this integration rather than misrepresented.
- Preserve upload/search URLs and request payloads, selection and replacement-list behavior. One UI recovery correction moves FormData construction inside the existing try/finally so a synchronous construction error cannot strand the busy state. It does not alter backend processing or publication.
- Show local file size instead of technical chunk counts; no page count is invented. Explain the sidebar as files uploaded in this tab, and selection as chat scope. Replace the nonfunctional Web/My Documents selector with an accurate documents-only label.
- Expandable, keyboard-operable citation references retain document/page deduplication. They explain how to check the original and explicitly disclose that original-page viewing is unavailable in this chat. No viewer URL, ownership or provenance is inferred from a filename. This says nothing about the separate platform workspace's existing original-viewing feature.
- Explain visibly that questions and retrieved passages are sent to Google Gemini; verify against the unchanged generation prompt.

## Reproduce without editing application files

Use a disposable checkout at the exact integration commit, with the committed lockfile and a compatible Node/Chromium installation. The test commands write review outputs outside the checkout; normal build/Playwright generated files remain ignored.

```sh
npm ci --prefix frontend --cache /tmp/doclens-review-npm-cache --no-audit --no-fund
DOCLENS_PLATFORM_ENABLED=0 NEXT_TELEMETRY_DISABLED=1 npm run build --prefix frontend
npm run lint --prefix frontend
DOCLENS_PLATFORM_ENABLED=0 npm run test:e2e --prefix frontend
node tests/main_ui_review.cjs after /tmp/doclens-main-ui-review-1
node tests/main_ui_review.cjs after /tmp/doclens-main-ui-review-2
node tests/main_ui_mode_smoke.cjs /tmp/doclens-main-mode-review
git diff --check 31eb3455cd5dc02c47f343d62328d41c8a2c3458 HEAD
```

`CHROMIUM_PATH` overrides the default `/usr/bin/chromium`. Existing e2e fixtures bind loopback ports 3100/8101. Standalone harnesses choose disposable loopback ports and synthetic signed sessions. No customer PDF, hosted Gemini call, existing index, original, PostgreSQL, MinIO or Qdrant instance is used.

Validation environment: cloud Linux, Node24.19.0, Next16.3.6, React19.2.8, Playwright1.64.1, Chromium154.0.8037.57. Locked dependency installation succeeded without changing package/lock files. Backend and container builds were not rerun: no backend/container files changed. Native Docker Desktop/Intel-Mac behavior is not established by this review.

## Complete outcomes, including failures and retries

Raw outcomes, commands and exit codes are in [validation/main-ui](../validation/main-ui/). Log copies only normalize line-ending/trailing whitespace; substantive output is retained. PNG/JSON evidence is copied unchanged.

| Check/run | Outcome |
| --- | --- |
| Initial production build and lint | Passed |
| Initial existing e2e run | **9 passed, 4 failed**, exit1. The new unscoped alert selector matched both a visible dashboard error and Next's route announcer. No product recovery defect established. |
| Selector correction and e2e retry | **13 passed**. Selector now uses the dashboard's alert role, preserving all assertions. |
| Initial main dashboard scenarios | Passed: 192 samples, zero contrast failures, ten screenshots, six keyboard checks. This preliminary run did not sample the separate navigation text. |
| Final pre-install dashboard runs | Passed after including navigation text in contrast sampling and clarifying labels: 200 samples, zero failures; cold retry also passed. |
| Initial platform-mode smoke | Failed: expected an absolute landing redirect. All six route-status assertions passed before that assertion. |
| Platform diagnostic retry | Failed with observed307, Location `/workspaces`. This is the correct relative form of the expected URL, not an isolation defect. |
| Correct URL-normalization assertion | Passed: all six route statuses plus landing redirect. Product route/proxy code unchanged. |
| Initial `npm ci` | **Failed, exit254**, ENOENT writing `/home/agent/.npm/_cacache`; noisy tarball warnings retained. No checksum or TLS validation disabled. |
| `npm ci` with writable task cache | **Passed**, exit0; 457 packages installed using the existing lockfile. |
| Fresh locked-install production build/TypeScript | **Passed**, exit0. |
| Fresh locked-install ESLint | **Passed**, exit0. |
| Fresh locked-install existing e2e suite | **13 passed (16.1s)**, exit0. |
| Fresh locked-install dashboard run | **Passed**, exit0: all scenarios, ten screenshots, six keyboard checks, 200 contrast samples with zero failures. |
| Fresh locked-install dashboard cold retry | **Passed**, exit0 with the same counts. |
| Fresh locked-install platform-mode smoke | **Passed**, exit0: legacy dashboard/monitoring/ask/login/upload404, workspace200, landing307 to `/workspaces`. |
| Baseline-to-integration whitespace and protected-file checks | Passed; protected files byte-unchanged from baseline. See checks and manifest. |

The existing 13 e2e tests exercise actual Next gateway responses against a controlled upstream: monitoring/admin authorization, successful slow upload, header/body deadlines, capacity failure, malformed response, disconnect and invalid schema, network/non-JSON/unauthorized/oversize UI recovery, 25 MiB forwarding, malformed/missing-file/anonymous/oversize request status codes. They use an explicit **1,500ms fixture deadline**; this stage does **not** independently repeat the production600s timeout. That production configuration is unchanged.

The dashboard harness deliberately intercepts browser upload/ask responses. It checks empty, processing, successful, rejected, network-failed and upstream-interrupted states; preservation of the prior Ready sidebar document/selected search payload; synchronous FormData failure; explicit unsupported cancellation/no cancel control; no progressbar; Gemini wording; deduplicated, expandable citations; named question field; no horizontal overflow or clipped composer at both viewports. An interrupted request is not represented as a supported cancellation test. Real PDF parsing, inference and backend atomic replacement are not exercised or newly claimed.

## Screenshots, keyboard and contrast

CSS viewports: **1440×900** for all state captures and **1280×800** for answer/composer geometry. Device scale1. These are representative CSS desktop viewports, not a claim about the user's exact Mac model, display scaling or browser chrome.

- [Empty](../validation/main-ui/screenshots/after-empty.png)
- [Processing and cancellation limitation](../validation/main-ui/screenshots/after-processing.png)
- [Interrupted request/error recovery](../validation/main-ui/screenshots/after-interrupted-request.png)
- [Success](../validation/main-ui/screenshots/after-success.png)
- [Rejection](../validation/main-ui/screenshots/after-error.png)
- [Answer and citations](../validation/main-ui/screenshots/after-answer-citations.png)
- [Expanded source](../validation/main-ui/screenshots/after-citation-expanded.png)
- [Keyboard focus](../validation/main-ui/screenshots/after-keyboard-focus.png)
- [1280×800](../validation/main-ui/screenshots/after-answer-1280x800.png)
- [1440×900](../validation/main-ui/screenshots/after-answer-1440x900.png)

These are the integrated main-based UI captures, not screenshots reused from the Mac recovery build. This integration evidence does not include a new main-baseline before capture; earlier before/after Mac screenshots belong to the earlier, different-base review.

Six keyboard checks: Tab reaches Monitoring, Log out and Upload in order; Enter opens the file chooser; Enter expands the deduplicated source reference; Tab moves from question to enabled Send. The harness waits for React's click handler, font readiness and two animation frames before keyboard interaction, addressing the earlier recovery review's readiness concern. This uses React19 test instrumentation, not a new production hydration API. Both fresh-process repeats pass; the earlier flake's underlying cause is not claimed proven.

[Primary JSON](../validation/main-ui/dashboard-results.json) and [cold-repeat JSON](../validation/main-ui/dashboard-cold-results.json) contain actual computed colors, samples and assertions. Text colors are converted to sRGB through Canvas; alpha backgrounds are composited through ancestors before applying WCAG luminance formulas. Visible text in dashboard plus Administration navigation is checked at4.5:1 (3:1 for large text), enabled textarea placeholders separately, solid focus outlines against surrounding background at3:1. Disabled controls are excluded. Fresh runs: 200 text/focus samples each, no failures; minimum text **6.78:1**, measured Upload outline **15.61:1** in the primary run and **18.31:1** in the cold repeat, and citation outline **9.89:1** in both. The varying Upload measurement remains above3:1; font/frame readiness does not guarantee all hover/color transitions have settled. Treat exact focus ratios as sampled values, not deterministic constants. These are sampled states, not full WCAG certification; opacity/hover states, arbitrary Markdown, nontext control boundaries and screen-reader announcements are not exhaustively audited.

## Native coverage and outstanding boundaries

**Physical Intel i5 MacBook Air: not tested. Safari: not tested. VoiceOver: not tested.** No native macOS keyboard/file-picker evidence, Retina/scaling confirmation, actual document compatibility, real inference performance, whole-stack8GiB resource measurements or Docker Desktop rebuild is claimed.

Detailed progress, cancellation propagation and a legacy-chat PDF viewer require separate work; they are not supplied by this port. Platform backend browser acceptance was not rerun; the additional smoke verifies actual Next isolation routes only. The frontend recovery helper and32-page PDF discrepancy remain separate. No migration, original-file ownership inference or deletion is performed.

This is a main-based code review artifact, **not a safe Mac installation instruction**. The preserved Mac application has different limits and behavior. Do not replace that checkout, overwrite local changes or run a deployment based only on this document. Await the independent review and a separate preservation-aware Mac update procedure.

Evidence-only clarification: product code and test harnesses were validated at `cdbe3d008bd00363b07bda3f0251f140fb4d442a`; the subsequent documentation correction records the two distinct measured Upload focus ratios. It changes no product or test code. Review the full baseline-to-tip range.
