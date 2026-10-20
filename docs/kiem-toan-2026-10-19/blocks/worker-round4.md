# Worker/outbox audit — round 4 (exact-main static slice)

Reference: `956ba4f236b1c92f1280d2097018c199e90ce8c7`. All source paths and line numbers below were read from the detached exact-main worktree. No production, secret, or patient data was accessed. No application files were changed.

## Candidate design gap: POS dead letters have no human-facing recovery path

`pos_outbox` is written transactionally with payments and the relay serializes invoice/void delivery with advisory locks. The adapter contract also requires a repeated `clinic_reference` to be idempotent; I found no new duplicate-send defect in this narrow POS slice.

There is still no operator path to see or recover a `DEAD` POS row. `build_adapter` defaults to `none`; a disabled/misconfigured adapter is converted to `NullPosAdapter`, and `_deliver` immediately marks the row `DEAD`. `_dead_letter` only updates the database and writes an error log. Searches of the exact-main API and dashboard source found no `pos_outbox` consumer. The event health query aggregates `event_delivery` and `hen_gio`, not POS deliveries. Thus an operator cannot identify the affected payment, assign an owner, repair configuration, or safely replay the row from the app. The existing unit test asserts disabled POS becomes `DEAD`, but does not verify operator visibility or recovery.

- `src/clinicai/services/pos_config.py:42-50,62-69,77-98`, SHA-256 `6cc4f96c34fb98fb73fcbb7fe6f5079984a988c54aa0e3e8e0884d4c8a9ece12`: default adapter is `none`; absent credentials/unknown adapter resolve to `NullPosAdapter`.
- `src/clinicai/services/pos_relay.py:105-113,192-216`, SHA-256 `d9f07f1ad4e00410f260f3997c63c284d575adfe279682e839686e56e14d7344`: disabled adapter goes straight to `DEAD`; DLQ action is DB update + log.
- `src/clinicai/api/v1/health.py:68-105`, SHA-256 `02ed67509c1ba55560dd6287976c74eba626f2887b7104d165d78266dc82d86f`: operational health counts event deliveries and timers only.
- `docker-compose.yml:260-284`, SHA-256 `d45163c3d4ee2f689a8d13bac0d884c9d0943150e20dd39b637ebb3ebe8f8839`: POS relay is opt-in under profile `pos`.
- `src/tests/test_pos_relay.py:194-205`, SHA-256 `746358e28ba6a2c8e3fbe2b8516d00735f6c247ac472664723ea710ad2d693bf`: existing test covers the `NullPosAdapter` dead-letter result only.
- `supabase/migrations/20260730000007_pos_outbox.sql:17-52`, SHA-256 `28fa706b9c58a3a411232943b98b6fe61520179be54fd8511dc41c992c3ab22b`: rows have durable `PENDING/SENT/DEAD`, attempts and errors, but no operator/replay schema.

Classification: candidate `design_gap`, conditional on selling/enabling POS delivery. The integration is explicitly documented as unfinished/opt-in, so this is not evidence of a current production POS failure. Before enabling it for a customer, add an authorized per-clinic view, owner/action state, safe retry/replay controls, and an alert/SLO for DEAD deliveries. A synthetic DB/HTTP test of such an operator flow has not been run.

## INF-005 scope extension: timer jobs share the stale-lease/fencing weakness

This is the same failure class as INF-005; do not create another finding ID. `lam_mot_hen` claims a timer by setting `DANG_LAM` and `thue_den`, then runs its callback after the claim transaction. After the 120-second lease expires, `thu_hoi_hen_treo` sets it back to `CHO`; there is no claim token/worker identity. The old callback then finishes with an unconditional `UPDATE ... WHERE id = ...` (or its exception path does the same), so a reclaimed callback can overlap and an older worker can overwrite the current timer state. This is static evidence; this round did not force a slow handler in DB.

- `src/clinicai/events/hen_gio.py:129-167`, SHA-256 `bc7043474aae3693211ba52ce3c0135cf433c18163eb986ed7d3a5e878d3b868`: lease is claimed, callback runs after commit, completion update is fenced only by ID.
- `src/clinicai/events/hen_gio.py:227-238`, same SHA: stale `DANG_LAM` timers are reclaimed without a claim-generation check.
- `src/clinicai/events/worker.py:139-194,283-293`, SHA-256 `e48c44c90133bd604d03b45bd446bb37005580c928ccc3c0de7b72228bfdf363`: existing `event_delivery` lease pattern that INF-005 already covers.
- Example callback `src/clinicai/events/consumers/nhac_tai_kham.py:40-87`, SHA-256 `f87d84db9df4c911cc7450c433d4c74d8c51a5835b22aacf409088254c91037a`.

Suggested acceptance: inject a callback exceeding lease duration, reclaim with worker B, and prove worker A cannot finalize/retry worker B's claim; callback side effects remain deduplicated.

## Delivery semantics observed

`notification_relay.poll_and_deliver` holds an advisory lock around external Telegram send and then marks `event_log.event_published`. A process/DB failure after provider acceptance but before this update can cause a duplicate on retry; Telegram requests have no idempotency key in the local caller. The code explicitly tolerates rare duplicates when one configured chat accepts but a later chat fails. This is an at-least-once design tradeoff, not a separate finding in this round; if patient-facing channels use this path later, use a per-channel delivery record/provider idempotency where available and display delivery state.

`pos_relay.poll_and_push` similarly calls the adapter under a session advisory lock; the port contract requires idempotency by `clinic_reference`. The current KiotViet adapter is intentionally a refusal stub, so end-to-end external delivery was not tested.

## Coverage and limits

Reviewed the event worker claim/retry/DEAD path, timer worker claim/reclaim path, event upcasting and projection replay outline, POS outbox/relay/config/port and its Docker profile, notification relay/provider delivery boundary, and legacy RabbitMQ consumer wiring. No full worker test suite, long-running concurrency drill, production data, real provider, load test, or recovery drill was run. This remains a selected path trace, not a complete audit of every consumer or worker module.
