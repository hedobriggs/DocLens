# Main UI follow-up: filename wrapping and keyboard evidence

Review ref: `hedobriggs/DocLens`, `refs/heads/ui/main-compatible-usability`.
Immediate review base: `c2d2be7783d58d06adbeb323a6f1c02895847387`.
Original main baseline: `31eb3455cd5dc02c47f343d62328d41c8a2c3458`.
Independent review is pending. No merge, deployment, migration, stored-data changes or Mac checkout changes are performed.

## Product changes

- `overflow-wrap:anywhere` on the upload status and citation reference containers, and a shrinkable toolbar text column. Message/citation flex items can shrink within the available width. This preserves full filenames in completion messages, the toolbar and expanded references.
- The single-row question placeholder refers to the selected document rather than repeating a potentially clipped filename. Actual selection and ask payload are unchanged. Sidebar rows retain intentional truncation with their existing full-name title and accessible name.
- Upload is disabled during server rendering and becomes enabled through React's client snapshot after hydration. This uses `useSyncExternalStore`, with no dependency, API or backend changes. It exposes a public readiness condition instead of inviting a gesture before its handler exists.
- All enforcement limits, gateway deadlines, authentication, publication behavior and unsupported-cancellation disclosure remain unchanged. The Mac recovery branch/backend is not imported.

## Long-name reproduction and independent geometry checks

The added geometry test failed against the previous UI: unbroken filenames clipped the completion message, toolbar and citation body at both1280×800 and1440×900. The raw failure and before screenshots are preserved.

Final tests exercise both a237-character unbroken filename and a spaced filename, at both viewports. Sixteen target checks cover completion, toolbar, citation summary and expanded reference text. Each checks scroll/client dimensions, text-range rectangles, viewport bounds and clipping ancestors, after scrolling the target into view. This detects content hidden inside a fixed-width element even when the document itself has no horizontal scrollbar. All16 pass after the fix. They deliberately exclude truncated sidebar rows and offscreen conversation history; those remain scrollable/intentional.

There are14 final dashboard captures, including four long-name screenshots. [Final screenshots](../validation/main-ui-followup/dashboard/screenshots/) and [clipping/contrast JSON](../validation/main-ui-followup/dashboard/after-results.json) are included in the review bundle.

## Enter-to-picker investigation

Evidence is retained rather than attributing every timeout to hydration:

1. The original independent review timed out waiting for a chooser. Its log is copied as `original-independent-timeout.log`; provenance is the earlier Mac review at `d0980c6c5ea07032cc5c060ff726b8042c9bef51`.
2. A controlled pre-hydration test against the immediate base held application scripts and found Upload enabled before React could handle it. The disabled-readiness assertion failed as expected; see `keyboard-before`. The public hydration guard addresses this separate usability gap.
3. Hydration readiness alone did **not** eliminate the harness failure: the subsequent dashboard run still timed out. See `dashboard-timeout-preserved.log` and `checks-before-listener-fix.json`. Build, lint and13 regressions had passed before that timeout.
4. A late-listener negative control, otherwise using the same keyboard sequence and focus screenshots, passed its first browser context then timed out in the second. Its DOM trace records a focused Upload button, trusted Enter and button click, and the file input's programmatic click with user activation still true. The test did not receive a chooser event. This is evidence of an event-observation/interception registration race, not evidence that Enter failed to reach the application.
5. Final harnesses register a real `filechooser` listener before navigation, then wait on public Upload enabled state and document focus. They use actual Tab/Enter, not a programmatic substitute for the gesture. No private React properties, animation-frame readiness waits, fixed sleeps, automatic retries or enlarged picker timeout are used. The picker watchdog is5seconds in the dedicated harness, shorter than the original30seconds.
6. Two separate fresh-process runs pass20 new contexts each:10 at each viewport, including one deliberately script-blocked hydration case per viewport per run. **40/40 contexts passed**, with4 controlled hydration cases overall. Every context records trusted event/activation evidence and a focus screenshot.

The late-listener control supports the registration-race diagnosis. The exact historical timeout lacks an equivalent event trace, so its individual cause is not claimed proven retrospectively. Likewise,40 headless Chromium trials are repeatability evidence, not proof that every browser/OS combination is covered.

The disposable negative-control/diagnostic scripts are retained exactly as run, with `/workspace/DocLens` as their diagnostic repository path. They are evidence, not release gates. The final portable test entry points resolve the repository relative to themselves.

## Reproduce final validation

With the existing locked dependencies installed, run from repository root:

```sh
DOCLENS_PLATFORM_ENABLED=0 NEXT_TELEMETRY_DISABLED=1 npm run build --prefix frontend
npm run lint --prefix frontend
DOCLENS_PLATFORM_ENABLED=0 npm run test:e2e --prefix frontend
node tests/main_ui_review.cjs after /tmp/main-ui-followup-dashboard
node tests/main_ui_keyboard.cjs /tmp/main-ui-followup-keyboard-1
node tests/main_ui_keyboard.cjs /tmp/main-ui-followup-keyboard-2
node tests/main_ui_mode_smoke.cjs /tmp/main-ui-followup-platform
git diff --check c2d2be7783d58d06adbeb323a6f1c02895847387 HEAD
```

[Exact commands and exit codes](../validation/main-ui-followup/checks.json) are retained. All7 final checks exit0: production build/TypeScript, ESLint, **13/13 existing regressions**, dashboard, two keyboard runs and platform isolation. The platform smoke checks actual Next legacy-route404 boundaries, workspace200 and the307 workspace landing redirect without starting a platform backend. The13 regressions use the existing controlled upstream and1,500ms fixture deadline; no production timeout is changed or newly certified.

Dashboard validation passes515 contrast samples, with no failures; minimum text contrast6.78:1. It includes long-name states in addition to the previous200 basic-state samples. The existing computed-color/sRGB/alpha-compositing method and3:1 focus/4.5:1 normal-text thresholds remain. Numeric focus samples may vary during color transitions; thresholds are asserted rather than a fixed ratio. Disabled controls are excluded. This is not a complete WCAG audit.

Fresh final runs were preceded by passing development runs. Retained failures are the before-fix clipping check, pre-hydration disabled-state check, dashboard chooser timeout and late-listener control. No failure was hidden by automatic retries. `checks-before-composer-label.json` records the passing run before the final placeholder wording correction; all7 checks were then rerun against the final source.

## Validation limits and boundaries

Cloud Linux, Node24.19.0, Next16.3.6, Playwright1.64.1 and Chromium154.0.8037.57. The CSS viewports1280×800 and1440×900 use scale1. Dashboard API responses are synthetic/intercepted; the legacy regression suite uses a controlled upstream. No actual customer PDF, real inference, stored index, original or external Gemini call is involved.

**Physical Intel MacBook Air: untested. Native Safari: untested. VoiceOver: untested.** Native file-picker behavior, hardware keyboard mappings, Retina scaling, whole-stack8GiB performance and Docker Desktop rebuild remain outside this evidence. Original-page viewing and cancellation are still unsupported in this legacy chat. The recovery helper and32-page PDF discrepancy remain separate. This is a code-review handoff, not a Mac installation instruction.
