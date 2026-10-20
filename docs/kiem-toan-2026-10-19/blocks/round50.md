# Round 50 — roster-history ordering under concurrent writes

Source SHA: `956ba4f236b1c92f1280d2097018c199e90ce8c7`. Review used immutable Git blobs via `git show`. Tests were read only and not run. No ClinicAI application, API, DB, provider, VPS, production, secrets or PHI was accessed.

## Finding

- **Added OPS-013 LOW:** roster history replays whole-week snapshots and row changes by `txid_current()` ascending. PostgreSQL assigns an xid when a transaction first writes; that value does not establish commit order. `apply_week` snapshots `work_roster`, while row writers record trigger deltas in separate transactions, and the reviewed paths do not acquire one shared per-clinic/week lock before reading or writing.
- If a row edit receives the lower xid but remains uncommitted while a concurrent reapply snapshots the old visible row and commits first, replay applies the edit and then the older snapshot. The latest history can therefore disagree with the current `work_roster` state. This is a static concurrency inference; no DB interleaving was run and no production occurrence is claimed.
- Existing DB history cases are sequential; the examined tests contain no concurrent snapshot/edit ordering case. Tests were read-not-run.

## Recommendation and validation

Serialize every edit/add/remove/reassignment and apply/reapply operation with one transaction-level lock keyed by clinic and week, acquired before the roster read/write and snapshot. Alternatively use a version sequence whose allocation and mutation are protected by that same lock. Add a deterministic two-connection test with barriers, then assert the latest reconstructed state equals `work_roster` across every commit ordering.

PostgreSQL reference: [Transactions and Identifiers](https://www.postgresql.org/docs/17/transaction-id.html) documents that xids are allocated at first write and that lower xids indicate an earlier first write. Exact code ranges, hashes and read coverage are in `blocks/round50.coverage.json` and `PHAT-HIEN.json`. Full source audit remains incomplete.
