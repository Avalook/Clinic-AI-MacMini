# Round 36 — 20/10/2026, exact-main static review

Source pin: `956ba4f236b1c92f1280d2097018c199e90ce8c7` at `/Users/quangdang/.codex/worktrees/audit-main-1910/Dr4Women-MacMini`. Read-only semantic review. Tests were read, not run; no app/API/DB/provider, production, secrets or PHI access.

- **FIN-003 expanded:** adding billable material can be retried after an uncertain response; frontend creates per-call idempotency value, endpoint does not consume it, and service increments the existing pending quantity. This reinforces the existing duplicate-add finding; no new ID or production occurrence claim.
- **FIN-005 expanded:** cashier transaction list has a separate `LIMIT 1000`; response lacks completeness metadata and UI totals the returned subset. Threshold occurrence is unknown.
- **FE-023 expanded:** result-file delete/restore and checkout may show a definite failure and stale UI after a lost response. Backend already-state branches make these retries safe in the inspected paths; no duplicate effect or runtime reproduction is claimed. More consequential duplicate-write examples remain in LAB-001, PHAR-004 and FIN-003.
- **INF-021 expanded:** create_room commits the room before inserting the audit event on a separate connection. If audit insertion fails, the API may return an error while the room exists; the UI keeps the form open after an error. Retrying with the same display name could create another row because the reviewed migration declares uniqueness on clinic/code and the service generates a random code. That duplicate is a conditional inference, not a reproduced or observed incident.
- **Held:** inactive permission preset is excluded by active-only lookup, then built-in defaults are used. UI shows “đã tắt” without defining fallback semantics; management action is gated, so this is not an unprivileged auth bypass. Clarify product contract before severity/finding promotion. Concurrent preset overwrite remains an unvalidated race candidate.
- Settings paths reviewed did not show a new authorization bypass; API derives clinic from identity and checks `config.clinic.manage` on the booking-policy route.

Exact ranges/hashes and remaining gaps: `blocks/round36.coverage.json`. Ledger includes 2,890 source paths but status counts are not behavioral coverage. **Full source audit remains incomplete.**
