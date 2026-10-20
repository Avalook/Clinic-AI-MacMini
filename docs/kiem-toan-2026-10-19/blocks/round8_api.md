# Round 8 — FastAPI permission administration API

Status: complete (read-only). Code evidence is from the pinned exact-main snapshot `956ba4f236b1c92f1280d2097018c199e90ce8c7` at `/tmp/clinicai-audit-main-956ba4f2`; do not substitute the dirty workspace for source evidence.

## Result

No new finding from this slice. The permission/skills route trace independently corroborates existing **SEC-012** in `PHAT-HIEN.json`: `KyNangService.doi` commits the skill assignment first, then reconciles LEGO capabilities through separate service transactions. If that reconciliation fails partway, repeating the same desired toggle returns `already` before reconciliation. The existing registry entry already describes a fault-injected revoke reproduction and acceptance criteria, so this round does not duplicate it. I did not run that probe or any DB test in this slice.

Key source evidence:

- `src/clinicai/services/ky_nang_service.py:205-253` — permission guard, same-clinic target validation, skill-row transaction and the early `already` return; SHA-256 `2c8fe8d9e7e4414522304318fb731f737d678bb023a3df54c871f18a0a0dbd7d`.
- `src/clinicai/services/ky_nang_service.py:251-293` — the later reconciliation loop and success response; same hash.
- `src/clinicai/services/permission_service.py:363-428` and `:254-290` — one LEGO may fan out into separate revoke/grant calls; each grant/revoke has its own transaction and post-commit cache invalidation; SHA-256 `fa4aebab3761bf2487f35c8472611daa97623f46609402a55b81f5a8cb423bc3`.
- `src/clinicai/api/v1/routers/phan_quyen.py:304-331` — the authenticated skill toggle/copy endpoints delegate to `KyNangService`; SHA-256 `bce5882167696d75a7b414217570382e07a2e24a694c235bdf061512c2b748ab`.

## Positive evidence

- Router registration is under `_GUARDED`, and mutation endpoints obtain `StaffIdentity`; the backend service remains the authorization boundary. `KyNangService.doi` checks `permission.manage` inside its transaction and verifies the target has an active membership in the actor's clinic.
- `PermissionService.cap_khoi` / `thu_khoi` also re-check `permission.manage` and same-clinic target membership inside each mutation transaction, record actor/event data, and invalidate permission cache after commit.
- The final-manager safeguard is enforced in Postgres: migration `20260923000016_quyen_khoi_dong.sql:78-95, 124-169` checks for an active clinic-wide `permission.manage` holder and uses a deferred trigger plus clinic-row lock. `permission.manage` is also constrained to clinic scope with no expiry at lines 139-152.
- Existing DB tests cover grant/revoke, target outside clinic, missing `permission.manage`, and audit event (`src/tests/services/test_permission_db.py:139-289`). The pure planner tests cover shared LEGO and room-union behavior (`src/tests/unit/test_ky_nang_ke_hoach.py`, full file).

## Coverage and limits

The exact read levels, line coverage and file hashes are recorded in `round8_api.coverage.json`. The relevant missing regression is a service-level retry/fault-injection test for `KyNangService.doi`; current tests exercise only the pure planner for skills, not the persisted skill-row plus capability reconciliation flow. Static review here confirms the failure/retry path but does not establish production frequency or runtime tenant behavior. The existing SEC-012 registry entry reports a synthetic DB fault-injection run; that result was not re-executed in this round.

Scope exclusions honored: event/health, work-items, patient identity/MPI, CSKH, lab/results and payment. No application or migration files were changed; no database, production system, secrets or PHI were accessed.
