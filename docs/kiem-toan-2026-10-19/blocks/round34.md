# Round 34 — 20/10/2026 08:08, source-only

Source pin: exact Git SHA 956ba4f236b1c92f1280d2097018c199e90ce8c7 at /Users/quangdang/.codex/worktrees/audit-main-1910/Dr4Women-MacMini. No app/migration change; no production data, secrets or PHI accessed.

- SEC-027 extended to legacy doctor-board; no active dashboard caller found and the route requires backend service key, so current browser reachability is unconfirmed.
- CLIN-050: patient-wide file cap happens before UI filters to appointment/order; recovery list has a second cap without completeness metadata.
- CLIN-051: simultaneous near-end treatment marker requests can duplicate CSKH history; existing test is sequential.
- CLIN-052: new-booking availability uses staff identity location while create uses selected location; server write validation remains authoritative.
- CLIN-053: schedule update commits before the separate reminder marker; active UI ignores marker failure.
- OPS-010: assignment queue caps each group at 500 while the active page ignores truncation metadata.
- API-007: internal partner-work detail/actions omit target location check; PARTNER role retains intentional multi-location access.
- Tests read, not run. No app, API, DB, provider, VPS, production, secret or PHI use. Full source audit remains incomplete.
