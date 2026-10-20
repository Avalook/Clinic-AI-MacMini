# Round 43 — 20/10/2026, exact-main read-only review

Source snapshot: `956ba4f236b1c92f1280d2097018c199e90ce8c7`. Evidence was read from immutable Git blobs in the audit worktree. The primary checkout is not evidence. No application source or migration was modified; tests were read, not run.

## New/extended risk records

- **OPS-011 (MEDIUM, conditional):** “Dọn dữ liệu khách thử” can select an ordinary clinic patient. The UI labels the workflow as test-data cleanup, but the day list includes clinic patients without a test marker; the service gates on `permission.manage`, correct clinic, typed `XOA`, row lock and open-visit check, then calls SQL that archives and deletes selected records. The database checks clinic membership, not test status. The preview, explicit confirmation and manual archive are real mitigations; this is not an authorization bypass or proof of production harm. Independent security review agreed with MEDIUM severity, conditional on use with real clinic data.
- **CLIN-053 extended:** the schedule PATCH and reminder POST are separate. The POST has no idempotency key and failures are ignored; the BFF forwards a key only if sent, while the backend allows the legacy path without it. A retry after an ambiguous response can duplicate a reminder marker. No automatic retry, duplicate incident or missed patient visit was demonstrated.

## Reviewed and deduplicated

- Telegram bot, notification templates/tests and relay: no new finding; keep INF-012, INF-023 and INF-025.
- Appointment quote BFF and parameter tests: no separate finding.
- ThaiKy/clinical BFF, disabled legacy routes and historical Notion: no new bypass; route shutdown and service-layer checks hold. Upload concerns remain LAB-001/SEC-003.
- Operations/finance BFF: pharmacy row retry deduplicates FIN-003; other assigned access/shift/report paths yielded no independent finding.
- Tests were read only, not executed. No ClinicAI runtime/API/DB/provider/VPS/production/secrets/PHI access.

Coverage ranges and immutable hashes: `blocks/round43.coverage.json`. Full source audit remains incomplete. Current path ledger: 862 read, 516 partially traced, 1,001 scanned, 503 inventoried, 8 excluded out of 2,890; these are inspection stages, not behavioral coverage.
