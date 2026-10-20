# Round 48 — treatment-plan chip authorization and freshness

Source SHA: `956ba4f236b1c92f1280d2097018c199e90ce8c7`. All source evidence comes from immutable Git blobs via `git show`; no primary-checkout source was used. This is a narrow static review. Related tests were read, not run. No ClinicAI application, API, database, provider, VPS, production, secrets or PHI was accessed.

## Findings

- **Extended SEC-011 (HIGH):** the treatment-plan chip GET accepts a batch of caller-supplied visit IDs. FastAPI checks identity, and the service checks `QUYEN_DOC`, then scopes SQL by clinic and those visit IDs. It returns service, session and prepaid metadata without a patient/doctor-assignment check. The list is capped at 300 and malformed UUIDs are discarded, but neither bounds resource use nor establishes object assignment. This remains a same-clinic static authorization concern; cross-clinic access and production exposure are not claimed.
- **Extended FE-002 (MEDIUM):** the shared hook stores the batch key with the last successful response but returns its data without checking that key against the current batch. A rejected fetch leaves prior state in place and exposes no stale/error marker. The hook is used in doctor queue, service-room and reception screens. Boundary tests check batching/callers, not key changes or rejected refreshes.

## Dedupe and limits

Both observations extend existing findings, so Round 48 adds no new finding ID. The 300-visit cap, clinic filter and UUID validation were retained as controls. Tests were read only, not run; no JWT matrix, React fault injection or production observation was performed. Exact ranges, line counts and source hashes are in `blocks/round48.coverage.json`; relevant excerpts are embedded in `PHAT-HIEN.json`.

Full source audit remains incomplete. These path counters are not a semantic-completion percentage.
