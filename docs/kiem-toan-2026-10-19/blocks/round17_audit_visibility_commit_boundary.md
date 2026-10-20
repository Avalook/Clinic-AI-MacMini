# Round 17 — audit visibility, transaction boundary, and status BFF

Snapshot: pinned main `956ba4f236b1c92f1280d2097018c199e90ce8c7`. Coverage fingerprints are in `round17_audit_visibility_commit_boundary.coverage.json`.

## SEC-026 — permission history is outside the consolidated audit page

`PermissionService` writes typed `capability.granted` and `capability.revoked` events into `domain_event` in the permission transaction. The protected `/api/v1/audit/events` endpoint calls `AuditLogService`, whose SQL combines `v_audit_log` and `work_item_event`; the dashboard page consumes only that endpoint. The event and grant history remain durable. The finding is the operator discoverability gap in `/audit-log`, not missing storage or a tenant bypass.

Recommendation: add a minimal, clinic-scoped projection for selected security events, with actor, target, capability, scope and time. Keep clinical event payloads outside the operations view. No DB/API/UI integration test or production data was used.

## INF-021 — floor mutation commits before its audit append

`create`, `rename`, `set_active` and `reorder` update state, then call `_audit`. `_audit` acquires a different pooled connection, while `record_event` documents that it relies on the caller transaction. An event insert failure can therefore leave committed configuration with an API error and no matching audit row. This is confirmed by source layout only; no fault injection or production occurrence is claimed.

Existing floor DB tests cover successful mutation and validation, not audit-writer failure. Acceptance should inject event insert failure for each command and prove all-or-nothing behavior.

## FE-018 — status read failure becomes success-shaped JSON

The clinical status BFF returns `{error}` with default HTTP 200 when `fetchFromBackend` returns `null`. `HoSoHoanTatPanel` trusts `response.ok`, casts the body to `Status`, and dereferences an absent label entry. The nearest dashboard error boundary limits the likely failure to the current route segment. This is LOW, static only; no render/BFF runtime test was run.

## Limits and next work

Eight files received full semantic reads and two related test files were traced. No ClinicAI tests, database, Auth provider, production, secrets or patient data were touched in this slice. The three additions are `confirmed_static`; the complete source audit remains incomplete. Next inspect clinical-result lifecycle, worker recovery and finance reconciliation, then use a disposable database for targeted failure injection.
