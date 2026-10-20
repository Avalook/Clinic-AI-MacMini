# Round 49 — payment method-change ledger guard

Source SHA: `956ba4f236b1c92f1280d2097018c199e90ce8c7`. Review used immutable Git blobs via `git show`. Tests were read only and not run. No ClinicAI app, API, DB, provider, VPS, production, secrets or PHI was accessed.

## Finding

- **Added FIN-020 LOW:** the split-payment CHECK can evaluate to SQL `UNKNOWN` for a one-sided NULL row; PostgreSQL accepts a CHECK result that is not false. The trigger checks the total only when `tien_mat` is non-NULL, and a NULL transfer leg makes the sum comparison unknown too. The effective-payment reader can then surface a NULL/zero transfer leg or interpret the row as a single tender. The table grants INSERT to `service_role`, so the database guard does not fully enforce the intended invariant for privileged writers.
- The reviewed HTTP route calls `doc_chia`, which requires both legs positive before INSERT. No current user/API path to malformed rows was found, and no DB reproduction or production issue is claimed. Severity is LOW because the defect is at the privileged-writer/defense-in-depth boundary.
- This shares PostgreSQL NULL-in-CHECK mechanics with FIN-010 but protects a distinct tender-breakdown invariant and requires a separate migration/test, so it remains a separate record.

## Dedupe and limits

The method-change transaction locks the payment cycle, checks current effective tender/refund/status, and records the event and audit row in the same transaction. Existing tests cover valid split writes, replay of the current tender, stale method, void/refund guards and clinic scope. Tests were read-not-run. Fractional VND rounding is held because both UI and service round whole-dong input and no material loss was established. Full source audit remains incomplete.

Exact code ranges, hashes and test coverage are in `blocks/round49.coverage.json`; the main finding includes excerpts in `PHAT-HIEN.json`.
