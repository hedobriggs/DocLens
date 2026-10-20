# Live Gemini evaluation and P1 trial-safety correction

Base/application approval: `66db29f0b072fd9821869f4ffef008883ce0509b` (against its approved base `2eadf4ad8b2cb0c851be68739afc9725b0ef27e6`). This change does not alter any application backend/frontend code, existing limits, resource controls, publication logic or recovery behavior.

## Latest live evaluation: 3/3 passed after binding correction

The running environment now supplies `GEMINI_API_KEY` and no longer supplies `GERMINI_API_KEY`. Rerunning the unchanged live evaluation produced three HTTP 200 responses; each contains all five synthetic employers and exactly the five expected document/page/chunk citations. Results and complete synthetic answers are retained in `validation/mac-live-gemini/attempts-3/`.

Observed durations: 0.962 s, 7.361 s and 48.015 s. The slow third response is retained; this is not a latency guarantee or a browser/gateway timeout test. The evaluation uses real Gemini and the reviewed generation/citation implementation, real PDF ingestion/local Qdrant, and controlled embeddings. It does not establish physical Mac performance, Safari/VoiceOver coverage, or guaranteed completeness for arbitrary documents.

Earlier failures remain in attempts-1 and attempts-2; attempts-2 used the old fallback binding while the renamed binding had not yet reached the running environment. No application code changed for this retry. The prior credential blocker is resolved. The corrected Mac trial procedure still requires independent review before execution; no original-installation update is authorized or performed.

## Historical failure: initial live evaluation was blocked

Run `backend/.venv/bin/python tests/mac_live_gemini_cv.py /new/evidence/directory` with the existing securely configured Gemini binding. The helper accepts no customer document input. It uses a synthetic seven-page CV with five known employers and two distractor pages, real PDF ingestion and local Qdrant, controlled embedding vectors, the reviewed complete-context path, real Gemini client, and unchanged application prompt/parser/citation mapping. It requests three independent answers from the application's `gemini-3.5-flash-lite` model. It requires all five employer names and the exact five employer-page citation identities, not merely a nonempty response. This is not an embedding-model or physical Mac performance test.

All three attempts failed before an answer was returned. Failures were retained in `validation/mac-live-gemini/attempts-1/`. The wrapper raised RuntimeError; a retained-client direct SDK diagnostic identified HTTP 400 ClientError, API_KEY_INVALID (“API key not valid”). See sanitized `provider-diagnostic.json`. No key values, headers or full provider exceptions were recorded. Additional exploratory diagnostic calls using temporary unretained SDK clients produced client-closed RuntimeError; those calls did not establish provider status. The retained-client diagnostic above is the provider evidence.

The environment reports its existing `GERMINI_API_KEY` binding ready, but actual provider authorization fails. Correct that existing secret securely in cloud environment settings; do not paste it into chat. Do not retry the unchanged failing credential or change the model to manufacture a pass. After correction, rerun into a new evidence directory, retaining the initial failures. **All-five completeness and citation verification against live Gemini remain blocked.** No successful live answer is claimed and no Mac update steps are prepared.

Deterministic coverage regression rerun: 5/5 passed (`validation/mac-live-gemini/deterministic-regressions.log`). Provider output is controlled in that suite and cannot substitute for the blocked live evaluation.

## P1 trial instruction defect and correction

Reviewer reproduced that the old pasted blocks could continue after clone/cd failures, execute checkout in the original working directory and finish with status zero. The old nine-block instructions are withdrawn in `docs/MAC-SYNTHETIC-TRIAL.md`.

Replacement: `recovery/mac-ui-candidate/mac-synthetic-trial.sh`, executed as a script, not sourced/pasted. It uses fail-closed Bash settings, a status-preserving error trap, fresh private directory, clone with no checkout, repository/directory and exact commit-object checks before checkout, and exact HEAD/cleanliness checks before installs/trial. Checked assignments preserve errors from command substitutions; final evidence errors propagate. It requires the separately approved application SHA and an updated bundle containing that commit. No original installation, credentials, image tags or volumes are inputs. TLS verification remains enabled; dependency-image build and public model download are explicit prerequisites.

Six behavioral tests execute the real script with mocked Git from an original-directory stand-in: missing bundle, clone failure preserving 73, missing destination causing cd failure, incorrect commit assertion, failed commit lookup preserving 74, and final evidence assertion failure. Prerequisite failures assert no checkout and no changes to the stand-in. All six pass; Bash syntax check also passes. Evidence: `validation/mac-trial-safety/`. Script checksum is recorded there for reviewer verification.

Run:

```sh
backend/.venv/bin/python tests/test_mac_trial_safety.py
bash -n recovery/mac-ui-candidate/mac-synthetic-trial.sh
backend/.venv/bin/python tests/test_mac_document_coverage.py
git diff 66db29f0b072fd9821869f4ffef008883ce0509b --check
```

Independent review must approve this corrected procedure before a Mac trial. Full dependency builds, whole-stack headroom, physical Intel Mac execution, Safari and VoiceOver remain unverified. The old bundle is insufficient; an updated transferable bundle is supplied with this handoff. Do not run the trial while memory/disk headroom is uncertain, use original volumes, stop original services, or disable TLS to make prerequisites pass. Separate approval is still required for actual Mac installation changes. Nothing merged, deployed, migrated or admitted customer data.
