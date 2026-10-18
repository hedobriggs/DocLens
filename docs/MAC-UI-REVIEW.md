# Focused Mac usability update — independent review

Review branch: `ui/mac-focused-usability` in `hedobriggs/DocLens`.
Review base: approved Mac recovery application `76b81c1bf5a23fd62e344e893b1bff45e24e8cb4`.
This is a UI-only increment on that application, not a merge of the recovery branch into platform main. Main remains `31eb3455cd5dc02c47f343d62328d41c8a2c3458`. Independent review is requested before any merge/update approval. No deployment, Mac source replacement, migration, limit increase or stored-data changes were performed.

## Changes

- Preserve the header/sidebar/chat/composer layout. Reduce toolbar, conversation and empty-state padding.
- Show selected filename while uploading/processing, a polite live status and explicit completion confirmation. The request has no stage/progress API: there are no percentages, invented stage transitions or durable-job claims. Failures are alerts; the existing abort/deadline/finally behavior remains.
- Secondary Cancel button, brighter secondary text, darker primary buttons for legibility, named question field and 3px keyboard focus outlines.
- Show existing size/page limits before selection. Expandable details disclose current extracted-text/passage limits and unsupported OCR. All enforcement constants are unchanged.
- Sidebar says files uploaded in this tab and explains that selection scopes chat. Replace the nonfunctional “My Documents / Web / Documents + Web” selector with “Search source: documents only.” No functional web search existed in this selector. Selected document buttons expose pressed state.
- Ready documents display their selected local file size instead of technical chunk counts. Page counts are not returned by this upload endpoint and are not invented. The existing successful-response validation still checks chunk count internally.
- Citations remain deduplicated by document/page. Keyboard-operable disclosure controls expand the exact source reference and instructions to check the original PDF. They do not pretend to open an original page.
- Visible disclosure: questions and retrieved passages are sent to Google Gemini to generate answers. This matches backend/generation.py's existing prompt construction. No provider behavior changed.

## Evidence and reproduction

Run from repository root with the existing locked frontend dependencies and Chromium installed:

```sh
npm run build --prefix frontend
npm run lint --prefix frontend
node tests/mac_ui_review.cjs after
node tests/mac_upload_browser.cjs fixed frontend /tmp/doclens-ui-upload-review
```

`CHROMIUM_PATH` may override `/usr/bin/chromium`. The existing upload suite expects its documented synthetic padded PDF fixture (`tests/mac_upload_fixtures.py`, `DOCLENS_FREEZE_FIXTURES`). Neither suite admits customer data. Both run the real built Next application in disposable local processes with synthetic sessions. New dashboard scenarios intercept browser API requests deliberately; the existing suite additionally exercises the real Next gateway against a controlled local backend, including a real 120-second deadline. These are not real inference or actual-PDF compatibility tests.

Environment: cloud Linux; Node24.19.0, Next16.3.6, Chromium154.0.8037.57. Viewports1440×900 (all requested states) and1280×800 (answer/composer geometry). Mac model/scaling is not known, so these cover common Air/scaled desktop sizes; this is not native Safari, VoiceOver or physical Intel-Mac validation.

Evidence: [validation directory](../validation/mac-ui/). JSON reports include measured colors, ratios, keyboard checks and fixture boundaries. Logs are copied with line-end trailing whitespace removed; screenshots and JSON are unmodified.

| State | Before | After |
| --- | --- | --- |
| Empty | [image](../validation/mac-ui/screenshots/before-empty.png) | [image](../validation/mac-ui/screenshots/after-empty.png) |
| Processing | [image](../validation/mac-ui/screenshots/before-processing.png) | [image](../validation/mac-ui/screenshots/after-processing.png) |
| Success | [image](../validation/mac-ui/screenshots/before-success.png) | [image](../validation/mac-ui/screenshots/after-success.png) |
| Error | [image](../validation/mac-ui/screenshots/before-error.png) | [image](../validation/mac-ui/screenshots/after-error.png) |
| Cancellation | [image](../validation/mac-ui/screenshots/before-cancellation.png) | [image](../validation/mac-ui/screenshots/after-cancellation.png) |
| Answer/citations | [image](../validation/mac-ui/screenshots/before-answer-citations.png) | [image](../validation/mac-ui/screenshots/after-answer-citations.png) |
| Keyboard focus | [image](../validation/mac-ui/screenshots/before-keyboard-focus.png) | [image](../validation/mac-ui/screenshots/after-keyboard-focus.png) |

Additional evidence: [expanded citation](../validation/mac-ui/screenshots/after-citation-expanded.png), [1280×800](../validation/mac-ui/screenshots/after-answer-1280x800.png).

Contrast method: browser computed text colors converted to sRGB with Canvas; alpha backgrounds composited through ancestors, then WCAG relative-luminance ratios calculated. Visible text nodes are checked at4.5:1 (3:1 for large text); disabled controls are excluded. Enabled textarea placeholders are checked separately; solid keyboard focus outlines are checked against surrounding background at3:1. Before:56 failures among102 text samples, minimum2.44:1. After:184 text/focus samples, no failures; minimum text6.78:1; measured focus outlines18.31:1 (Upload) and9.89:1 (citation). These sampled states are not a complete WCAG certification or screen-reader audit.

Keyboard checks use real Tab/Enter: Log out → limits disclosure → Upload; open/close limits; Enter opens the native file chooser; activate Cancel and recover busy state; expand deduplicated citation; question field → enabled Send. Browser assertions also check pending filename, no progressbar, prior Ready document retained after rejection/network failure, selected filename/question preserved in request payload, clear success and Gemini disclosure, and no horizontal overflow/composer clipping at both viewports.

Final checks: production build/TypeScript and ESLint passed; dashboard suite passed; all12 existing upload recovery cases passed. The real gateway forwarded a28MiB synthetic body, rejected malformed/oversized/broken responses, closed upstream on disconnect, and returned504 after120.009seconds despite response trickle. Base-to-head whitespace check passed. Backend/API/dependency/limit files are byte-unchanged from the review base.

Failures retained: first harness assumed Upload was the next tab stop after Log out, overlooking the new limits disclosure; second tried to focus Send with an empty question (correctly disabled); the old suite's broad `/32 MiB/` locator became ambiguous with pre-selection limits. Corrected test expectations/selector, without relaxing product assertions. See three `*-failed.log` files and subsequent passing logs/JSON.

## Separate dependencies and limits

- Original-page viewing is unsupported. It needs a separately reviewed original-file access/storage path, provenance mapping and authorization. A filename alone does not establish ownership or identify a safe original. No original was fetched, inferred or migrated.
- Detailed progress, persistent document inventory after refresh and web search are not implemented by this UI patch. Sidebar accurately describes its existing tab-local list; stored indexes are untouched.
- The separately pending frontend recovery-helper review is not included. Do not execute an unapproved helper or replace Mac files on the strength of UI approval.
- The actual32-page PDF/page-limit discrepancy remains a separate investigation awaiting Mac parser metadata/logs. UI tests do not claim to fix that backend/runtime discrepancy.
