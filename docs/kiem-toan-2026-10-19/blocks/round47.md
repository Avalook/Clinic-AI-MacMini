# Round 47 — exact-main CSKH, settings, workflow, pharmacy and Ops review

Source SHA: `956ba4f236b1c92f1280d2097018c199e90ce8c7`. Evidence was read from immutable Git blobs using `git show`; current checkout WIP was not used as source evidence. This is a targeted static review, not a full repository read. Tests were read only and not run. No ClinicAI application, API, DB, provider, VPS, production, secrets or PHI were accessed.

## Findings

- **Added CLIN-058 LOW:** complaint POST has no stable command receipt. A replay after commit/response loss can insert another complaint and event row. Existing unit tests do not cover retry after commit; no runtime reproduction or production incident is claimed.
- **Added FE-028 LOW:** doctor-rule preview state is keyed by service only. Changing method/month can leave an old number visible while the new preview is pending or failed; Save remains enabled. Backend calculation still uses current parameters.
- **Extended FE-023:** found rejected-request pending-state gaps in complaint, new-user, location-scope and doctor-rule forms. Forms with catch/finally were excluded.
- **Extended FE-026:** history-of-edits panel can stay on “Đang đọc…” after fetch rejection.
- **Extended FE-002:** visit journey refresh keeps stale data unmarked; initial failure hides the panel.
- **Extended CLIN-057:** the fast-reschedule UI is actively mounted by two callers; closing/remounting gives the same intent a new idempotency key. No duplicate appointment was demonstrated.
- **Extended FIN-003:** QuayThuoc BFF add-line route also does not forward an idempotency key; the prior synthetic DB reproduction remains the only reproduced evidence.
- **Extended SEC-011:** procedure-follow-up metadata GET checks identity and clinic, but not the doctor assignment for the requested visit.
- **Extended INF-027:** Ops inventory/rollup/monitoring omit self-hosted Supabase dependencies, while public auth/REST/realtime routes exist and health handlers are static responses. Runtime outage behavior was not tested.

## Held observations

Impossible ISO week dates can display a normalized week; an old external-DB helper has a fixed-name `DROP SCHEMA CASCADE` but no active caller was found; GoTrue wildcard redirect semantics need exact recovery-flow review; sequential room saves lack an established atomicity policy; procedure-selection ambiguous response and appointment-follow-up UI cases were not promoted because duplicate business writes were not shown.

## Coverage and limits

Exact ranges, line counts and SHA-256 values are recorded in `blocks/round47.coverage.json`; new and extended finding excerpts are in `PHAT-HIEN.json`. The fast-reschedule session/remount trace was checked against active callers. Path states are not behavioral coverage. Full source audit remains incomplete.
