# Monitoring fixture fetch correction

Reported Mac attempt focus.JBlwqI.zip stopped before monitoring because the external seed callback called browser Fetch Response.status as a function. Correct to numeric .status property. No application or image changes. The callback is now executed verbatim in local Chromium against a synthetic HTTP server; status 200 and parsed JSON body pass. Collector event tests still pass. Syntax and whitespace checks pass. This does not establish candidate-image acceptance.

Reported failed archive SHA-256: 5158d0478257a440d58c1f7d11fd41e76681459033cca4e70ad3f75ecef807e2. Archive not yet transferred here, so its contents/checksum have not been independently verified. Next Mac wrapper requires and verifies it, copying it alongside all three prior archives into the corrective ZIP. Original failures remain; no question recovery tests are repeated. Monitoring traffic still includes one synthetic live answer to populate Gemini metrics. Prompt now labels its actual purpose.

Exact image remains sha256:4e3a0339cb5e1465701f757ca136039c369ab96fa672401a938e3efa0e5467d8. Monitoring-only Mac rerun pending; no access to Mac Docker from here. Acceptance/security approval blocked; 137 ledger entries remain open. No rebuild, merge, publication or deployment.
