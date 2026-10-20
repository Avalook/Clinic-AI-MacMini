# Round 33 — 20/10/2026 07:55, v0.56

Source: exact pinned Git SHA `956ba4f236b1c92f1280d2097018c199e90ce8c7`; only report artifacts changed.

- Added SEC-034: removing the final selected room in an enabled room-scoped lego sends an empty scope, which becomes a clinic-wide capability grant.
- Added SEC-035: a transfer proof hidden with `go_luc` remains readable via an old authenticated GET URL by a user with payment-history scope. Migration explicitly defines this as hide/retain; LOW severity and contract limitation are stated.
- Added CLIN-049: changing doctor at the same slot time leaves the former doctor's advisory hold active for up to ten minutes.
- Extended SEC-027 with the still-registered administrative-profile and CSKH routes; treated as the same missing patient-read capability family.
- Read exact-main UI → BFF → API/service → migration/evaluator/test paths. Test files were read, not run; no app, API, DB, provider, VPS, production, secrets or PHI accessed.
- Coverage hashes and ranges: `blocks/round33.coverage.json`. Whole-source audit remains incomplete; report-only HTML QA passed: 6/6 structural checks; 186 cards; desktop/mobile layout passed. Audit-only ZIP verified: 310 files; CRC and per-file SHA-256 pass; outer hash in MANIFEST-GOI.json.
