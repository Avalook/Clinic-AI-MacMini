# Round 51 — concurrent appointment reschedule

Source SHA: `956ba4f236b1c92f1280d2097018c199e90ce8c7`. Review used immutable Git blobs via `git show`. Tests were read only and not run. No ClinicAI application, API, DB, provider, VPS, production, secrets or PHI was accessed.

## Finding

- **Added CLIN-059 MEDIUM:** the appointment transition reads an appointment without locking it, builds a reschedule patch from that snapshot, and updates with a predicate that checks only appointment ID, clinic and allowed status. Two concurrent reschedules to different target slots can both start from `CONFIRMED`/`SCHEDULED`; because the status stays eligible, the later UPDATE can overwrite the earlier one.
- Both transactions write `appointment_doi_lich` and `appointment.rescheduled` using the original in-memory `appt` snapshot. The second history row may therefore say old slot → target B even though target A was already committed before B. The quick-reschedule UI's idempotency key includes the chosen target, so different targets do not share one key.
- This is distinct from CLIN-057's same-intent replay after a lost response. A stable receipt prevents duplicate execution of one command; it does not detect two different commands based on the same stale appointment version. No database interleaving or production occurrence was reproduced.

## Recommendation and validation

Return an appointment version or `updated_at` with the GET projection and require it on reschedule. Under a row lock or compare-and-swap predicate, reject a stale expected version with 409 before writing. Build the from→to history and event from the locked/current row. A deterministic two-connection test should race two different targets, assert one wins and one gets 409, then verify the current appointment, contiguous history and single accepted event. Keep same-key replay covered separately.

Exact source ranges, hashes and read coverage are in `blocks/round51.coverage.json` and `PHAT-HIEN.json`. Tests were read-not-run. Full source audit remains incomplete.
