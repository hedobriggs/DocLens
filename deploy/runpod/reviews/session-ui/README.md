# Home, conversation and expired-session UI review

Base: `5b83917c044d8b648032a3930a3399ef5c26dfcf` (separate dependency candidate).
This commit changes UI/session presentation only; no backend, dependency pins,
monitoring listeners, data format, stored data or limits change. Security release
block and disabled Web modes remain. Independent review required before execution
approval; no merge, publication, deployment, paid resource or Mac/Pod modification.

## Implemented

- Home/Conversation concepts guide navy/gold sidebar, warm canvas, serif welcome,
  compact upload panel, light question bubbles and white answer/source cards.
  Home/return preserves the existing conversation and draft. Documents navigation
  means **files uploaded in this tab**, not persistent account history.
- Real PDF chooser and single-file drop use the existing upload handler. PDF-only
  size/page/text limits remain visible; Word/multiple drops are rejected before
  API submission. No invented page counts, profile identity, working Word support,
  copy/rating controls, persistent history or original-page viewer.
- Native search-source menu: Documents only default; Web only / Documents + Web
  visibly unavailable and disabled. No Web API call or silent Web fallback.
- Sources remain keyboard-expandable page references with explicit original-page
  viewing limitation. The Gemini disclosure remains visible and accurate.

## Expired-session behavior

The server still verifies the signed JWT before rendering the dashboard. Only its
expiry timestamp, not the token/secret, enters a client context. At that expiry,
on tab focus/visibility resumption, or on an API401, all dashboard auth presentation
switches to **Sign in**. Log out disappears; the alert has a real clickable link
to the existing login page. Server authentication policy/duration/cookies unchanged.

Expiry aborts client upload/question requests and finalizers clear busy state.
Upload pending filename clears; question draft is restored on authentication
failure without erasing the displayed documents/conversation. No new requests are
admitted from expired controls. An unauthenticated server response is recognized
before parsing its body, so malformed401 JSON cannot hide the Sign in action.
Client abort is not proof of server rollback: previously accepted work may have
completed; no backend cancellation/publication semantics are changed or promised.
Reload/sign-in still has the existing tab-list limitations, not durable history.

## Executed tests and visual evidence

[evidence.zip](evidence.zip) includes before/after PNGs, full logs, JSON, commands,
source hashes and original failures. Production Next16.4.3 build/TypeScript, lint,
JavaScript syntax, six packaging guards and nine bootstrap checks pass. The new
client module is explicitly allowlisted and hashed; source-integrity checks stay.

- **Four session scenarios pass**: upload/question receive an actual expired-JWT
  rejection from the production Next API; upload/question expire via the verified
  server timestamp and deterministic browser clock. All verify busy controls exit,
  Log out is replaced, draft/document UI preservation and keyboard activation of
  Sign in reaching the real login form. Signed fixture cookies are injected for
  these tests; this is not a real-password login or a live backend upload test.
- Final UI run: **17 screenshots, 685 contrast samples, zero contrast failures**;
  1440×900 and1280×800. Empty/uploading/success/error/cancel/answer/citation states,
  file chooser Enter, source select mouse/keyboard, visible focus, Home/return,
  PDF drop/Word rejection and unbroken/spaced filename clipping checks pass.
- Home chooser and support limitation must both fit completely in each viewport.
  Actual image inspection found the note clipped at1280×800; the new assertion
  reproduces failure (ratio.169). Tighter spacing/line-height fixes it; no font
  contrast waiver or delay. Both final screenshots show the note above composer.

Failures retained: before run ended on one focus-outline contrast failure1.58:1;
all its screenshots retained. First UI tab-order check expected textarea directly
after source select, but the new Choose PDF control intervenes; corrected to test
that control and the actual Tab/Shift+Tab order. Initial lint required Next Link
for root navigation; corrected without disabling the rule. A few commands ran
from root instead of frontend and failed ENOENT; their logs are retained, with
correct-directory reruns. No test failure is relabelled as a pass.

Environment: maintainer Linux Chromium with real built frontend, fixture JWT and
controlled upload/answer responses. Expired401 responses use actual Next JWT
validation; clock cases explicitly use simulated client time. Screens approximate
MacBook Air viewports; **native Intel Mac, Safari, VoiceOver, actual GPU/browser
rendering, full rebuilt container, live Gemini and RunPod are untested here**.
Contrast samples are from the standard UI suite; expiry screenshots and keyboard
checks are separate. Previous Mac image acceptance does not apply automatically
to this newly changed UI/security candidate.
