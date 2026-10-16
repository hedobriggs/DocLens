# Current review handoff: reliability and MVP foundation proposal

Local branch: `fix/ingestion-reliability`.
Base: `00fada211a0a663e053132fa2559a896abe9036f`.
Implementation: `7baee9de9246b00cd4023d7cdc8a2f3783320e29`.
Final review head additionally commits evidence/docs only; use `git rev-parse HEAD`.
Nothing from this branch is published. The earlier public
`improve/uploads-monitoring` branch is unchanged.

Start with `docs/RELIABILITY-REVIEW.md` for exact commands, results and limitations.
Review process serialization AND SQLite cross-thread configuration, staged writes,
publication authority, legacy visibility, failed replacements, restart visibility,
counts, and optional pricing/metric handling. Provider/filename log privacy is
covered. Raw/selected evidence is in `validation/reliability-*.txt`.

Then review the proposed ADR, four milestones and evaluation plan in `docs/`.
No tenant/workspace/job/report foundation has been implemented yet; the 20 scenarios
need professional expected findings and thresholds before tuning. Do not mistake
this repair for multi-firm isolation, durable ingestion or production readiness.

Return prioritized findings with acceptance checks. Do not publish, push, deploy
or merge without the client's explicit approval.
