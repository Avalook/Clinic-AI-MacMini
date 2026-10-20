# Round 37 — 20/10/2026, exact-main read-only review

Source pin: 956ba4f236b1c92f1280d2097018c199e90ce8c7. Checkout had moved, so source was read from the immutable Git object via git show. Tests were read, not run. No app/API/DB/provider, production, secret or PHI access.

- **CLIN-054 added (MEDIUM, static):** when V5 probe returns null, print route falls through to legacy summary. Proxy returns null for missing session, non-2xx and network error; service can also validly return form_id=null. UI must distinguish successful absence from failed read. Different trigger from CLIN-037 draft/finalized status.
- **INF-007 expanded:** pharmacy return commits stock/refund/event before router stores idempotency receipt. Not fault-injected; no duplicate or production event claimed.
- **FIN-005 expanded:** service/drug transaction queries share the 1,000-row cap and UI totals the subset; threshold unknown.
- **SEC-017 expanded:** PostgREST is configured to expose public schema. No cross-clinic rows were selected; production provenance remains unverified.
- **API-007 expanded:** active partner board and sample/result/form/collection actions are traced. Concern remains same-clinic location scope; two-location test covers list, not UUID actions.
- **DB-006 reconfirmed:** ordinary runner transaction can be closed by self-COMMIT migration; already represented, no duplicate ID.
- **Held:** refund request date vs completion and VOID→REFUND net-cash need an accounting contract; compose drift overlaps OPS-007; tenant lifecycle needs further tracing before claiming absence.
- Patient search slice showed clinic-scoped parameterized search and explicit UI errors. Deploy/backup/restore reads added no independent issue outside existing INF/DB/OPS families.

Exact paths, hashes and ranges: blocks/round37.coverage.json. Main ledger includes 2,890 paths, mostly inventoried or scanned rather than semantically read. Full source audit remains incomplete.
