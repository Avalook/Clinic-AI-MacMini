# Audit follow-up: revoke partner result vs H7

- **Target source:** pinned `main` SHA `956ba4f236b1c92f1280d2097018c199e90ce8c7`.
- **Scope:** read-only source audit plus synthetic disposable-DB probe. No app code changed.
- **Candidate disposition:** retain as a separate, conditional lifecycle finding; it is not CLIN-001 (false inference that a doctor read a result) or CLIN-012 (H7 not scheduled for internal partner samples).

## Evidence

- `src/clinicai/services/doi_tac_service.py:802-840` requires an active file, READY form, or text result when the partner presses “Trả kết quả”; `:846-865` sets `ket_qua_luc` and emits `partner.result_returned`. The partner can later undo that marker separately (`:868-913`), while its docstring says files/forms remain.
- `src/clinicai/services/tep_ket_qua_service.py:541-560` defines marker recalculation, but intentionally excludes partner work (`:551-555`). `thu_hoi_tep` changes the sole file to `THU_HOI` at `:1210-1223` and emits the revoke event at `:1225-1234`, without clearing the order marker.
- `src/clinicai/events/consumers/hanh_trinh.py:343-363` schedules H7 only when `ket_qua_luc IS NULL`; `:366-376` treats a non-null marker as complete, so the overdue handler returns false and the timer is consumed without a CSKH reminder.
- SQL active-result view omits revoked files (`supabase/migrations/20260930700000_xoa_mem_tep.sql:147-152`).

**Observed state transition:** with a synthetic external order containing only one active partner PDF, partner return sets `ket_qua_luc`; revoking that PDF leaves `ket_qua_luc` non-null while the active-result view becomes empty. H7 then ends in `BO_QUA`, and no overdue `thong_bao` is created. This requires that no other active file, completed form, or result note remains. The implementation documents that the partner-return marker is cleared through the explicit undo action; that design intent makes the product policy/expected recovery path a point to validate, rather than evidence of a production incident.

## Probe

- Disposable DB: `chung_test_db` (`running=true`, local port `127.0.0.1:55600`); synthetic fixtures only.
- Command: `DATABASE_URL= PYTHONPATH=src scripts/test-nhanh.sh /tmp/probe_revoked_result_h7.py -q -s`
- Captured result: `1 passed` (~0.27 s). The raw stdout and temporary probe source are no longer saved; the probe file was removed after the run.
- Probe invoked the real upload, `DoiTacService.tra_ket_qua`, `TepKetQuaService.thu_hoi_tep`, result-event handling and H7 timer processing. The test runner reported applying 42 missing migrations to this disposable DB only.

## Related candidates and limits

- **`not_performed` after H7 scheduling:** not confirmed as a reachable normal transition. `src/clinicai/services/service_execution_service.py:689-705` permits `NOT_PERFORMED` only before execution starts and rejects an existing execution attempt. No probe was needed for the static guard; malformed/legacy DB states remain untested.
- **Undo partner return after H7 has already been consumed:** a separate conditional re-arm gap may exist; it was not probed and is not included in this finding. If undo occurs before the timer is due, the pending timer can still alert.
- No production DB, secrets, real patient data, or external notification delivery was accessed. This probe verifies the service/event/timer state path, not whether production data contains the state or whether a delivery channel succeeds.

## Source file SHA-256 (pinned worktree)

- `doi_tac_service.py`: `fb6ac3744877fb211de8638e950bfea3910f62cac2b867ccfea195828a0529ae`
- `tep_ket_qua_service.py`: `319301ae8f945fae34257672dc0f9777c44ff40a5f07abb8b3bf8718056ee226`
- `hanh_trinh.py`: `c3ed581ec935e8034f04f3725b02cb2a4047b05987016f7936fffc6ee1854bed`
- `service_execution_service.py`: `3abcc1358aaa0291b718144b1cc29866efd735da52916cf31a008329088abcad`
- `20260930700000_xoa_mem_tep.sql`: `15bb9553b633f31203d28d273d37d2c345d7f4177d327f4e86076fbdb5780b3b`
