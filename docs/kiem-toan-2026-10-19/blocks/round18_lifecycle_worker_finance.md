# Round 18 — clinical correction, worker recovery, and mixed-tender refund

Snapshot: exact-main `956ba4f236b1c92f1280d2097018c199e90ce8c7`. Every cited range and SHA-256 is regenerated from that checkout by `integrate_round18.py`. This round contains targeted cross-layer rereads; it does not claim new full-file reads.

## CLIN-036 — revoke after a recorded send has no corrective owner

An external result file can be `HOP_LE`, marked as sent by staff, then revoked before review starts. The revoke path does not select or check `gui_luc`; it changes the file to `THU_HOI`, emits `result_file.revoked`, and the active-file list stops showing it. The event is subscribed to by the timeline and review consumer, not `CHUONG`. The timeline keeps a revoke label, so the finding is not a missing audit event.

If the patient actually received the earlier file, the code reviewed here does not create a correction call-back, owner, deadline, or replacement link. `gui_luc` is a staff confirmation of manual sending, not proof of delivery. This remains a `design_gap` until the clinic defines whether a post-send revoke must open a correction workflow or be blocked in favor of one.

This is distinct from CLIN-019: that finding concerns the partner's result marker and H7 follow-up before the clinician reads a revoked file; this one concerns patient-facing correction after staff marked a file as sent. Existing tests cover revoke before sending and blocking a later send, but not send-then-revoke.

## INF-022 — terminal workers lack per-record recovery in the application

An event callback can end in `DEAD`, and an older unfinished delivery blocks later versions of that aggregate. Timers can end in `CHET`. Ops exposes aggregate counts by consumer; the error endpoint groups scrubbed errors. Event failures can create role notifications when an actor exists, and timer failures can notify when `chi_tiet.nguoi_goi` exists. Those signals do not provide an in-product row-level view, owner assignment, or safe retry/reconcile action. Projection replay explicitly leaves `event_delivery` unchanged.

The finding is about the recovery capability after the alert, not a claim that no alerts exist. It is separate from INF-017 (an old DEAD counter can age out of health) and INF-018 (lease reclaim can bypass the retry ceiling). No runtime failure or production incident was tested.

## FIN-016 — mixed-tender excess refund uses one scalar method

A cycle can retain both tender parts, but the excess-refund query reads the cycle's scalar effective method. The scalar rule treats a cycle as `TRANSFER` whenever any part is transfer. When the refund request omits a method, the refund service assigns the entire excess on that cycle to this scalar method. A 100,000 VND cash + 50,000 VND transfer cycle can therefore be presented and recorded as 150,000 VND transfer for an all-excess refund.

This is a tender-attribution and reconciliation gap. No incorrect total, lost money, duplicate refund, or production transaction is established. The nearby DB test verifies mixed tender collection, while default refund tests cover one tender at a time.

## Coverage and limits

The three reviews covered 25 exact-main source/test paths. They were already in the source ledger; three paths previously marked `scanned` now have targeted `traced` coverage. No path was promoted to a full read in this round. Current ledger totals are 2,890 paths: 704 read, 343 traced, 1,305 scanned, 530 inventoried, and 8 excluded. The three findings are supported by exact source ranges and hashes; no ClinicAI app tests, DB, API, browser, production, secrets, or patient data were used.

Next: run bounded tests on a disposable database for mixed-tender refund attribution, send-then-revoke correction handoff, and event/timer dead-letter recovery. Confirm the post-send correction policy with the clinic before converting CLIN-036 into a code acceptance rule. Continue semantic reads on the paths still only scanned or inventoried; the full source audit remains incomplete.
