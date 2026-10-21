# Law-firm dashboard presentation: review handoff

Exact base: `675064b3c7646c419c75c1a5240c9b8fda6ac8d4`, on the reviewed Mac candidate lineage. This is a separate UI branch, not a main integration or cloud deployment. Main, the user's Mac installation and stored documents are untouched.

## Changes

A navy document sidebar, warm white reading surface, restrained gold accents, serif welcome heading and compact wordmark create a more formal legal-workspace appearance. Answer cards distinguish questions from document analysis, typography/spacing are tighter, source references remain expandable and document filenames wrap. Toolbar, composer, selected-document indication, focus rings and secondary text have matching colours. Narrow screens now expose the upload/sidebar rather than hiding all document controls.

No invented security, confidentiality or legal-compliance claims. Gemini disclosure and original-page-viewing limitation remain explicit. This presentation does not turn generated answers into legal advice, change retrieval coverage or introduce document-viewer features.

Product diff: only `frontend/app/dashboard/page.tsx` and `frontend/app/globals.css`. All dashboard state and event handlers before the JSX return are byte-identical to the base. Upload size/page/text limits, cancellation, deadlines, auth/API routes, storage, worker caps, inference, publication and recovery scripts are unchanged. See `validation/legal-workspace-ui/preservation.json`.

## Validation

Commands from repository root:

```sh
npm --prefix frontend run lint
NEXT_TURBOPACK_EXPERIMENTAL_USE_SYSTEM_TLS_CERTS=1 NEXT_TELEMETRY_DISABLED=1 npm --prefix frontend run build
DOCLENS_LEGAL_VIEWPORT_CHECK=1 node tests/mac_candidate_ui.cjs after /tmp/doclens-legal-final
node tests/mac_candidate_keyboard.cjs /tmp/doclens-legal-keyboard
git diff 675064b3c7646c419c75c1a5240c9b8fda6ac8d4 --check
```

- Lint and production build passed. No dependency or lockfile changes.
- Built-dashboard synthetic browser checks passed for empty, processing, upload success, error, network failure, cancellation, FormData failure, answer/citations and expanded reference states. APIs are browser-intercepted; this is UI behavior evidence, not a new backend/live Gemini trial.
- 16 filename-clipping checks passed at 1280×800 and 1440×900, covering long spaced and unbroken names in completion, toolbar and collapsed/expanded citations. Selected document names now also wrap rather than truncate.
- 638 measured text/placeholder/focus contrast samples: zero failures under the harness's WCAG thresholds (normal text 4.5:1, large text and focus 3:1). This is a scoped contrast measurement, not a complete accessibility certification; disabled controls and decorative elements are excluded.
- Keyboard sequence covers logout, limits disclosure, upload via Enter, citation expansion via Enter and Send. Separate repeatable public-hydration keyboard harness: 20/20 passed, including two held-hydration cases, no arbitrary sleeps/retries or React internals.
- Narrow viewport 375×812: upload visible, no horizontal page overflow, Send within viewport. This does not establish native mobile Safari support.
- 14 baseline and 15 updated synthetic screenshots, full result JSON, geometry and clipping measurements are in `validation/legal-workspace-ui/`. Baseline screenshots were taken from the existing pre-edit production build; they are contextual visual evidence, not a fresh baseline rebuild. Representative comparisons: before/after `screenshots/after-empty.png` and `screenshots/after-answer-1440x900.png`.
- An initial editing command ran from the frontend directory with repository-root-relative paths and failed before changing product files; it was corrected. No failing product tests were hidden or retried. Final build, lint, browser and keyboard runs passed. The initial successful after-run had 529 contrast samples; the expanded final run adds narrow-screen coverage and reports 638.
- Base-to-head whitespace check passed. Product UI was inspected visually in captured Chromium screenshots.

## Boundaries

Physical Intel Mac, Safari and VoiceOver are not tested here. No backend tests were broadened because backend files and all processing handlers are unchanged; prior application approvals remain scoped as before. No new live-provider call or customer document was used. The UI retains existing session-tab document listing and chat behavior. Text/state checks are not proof of full zoom or assistive-technology coverage.

Submit this exact branch commit for independent review before any merge, installation update or deployment. No AWS deployment or Mac replacement is included.
