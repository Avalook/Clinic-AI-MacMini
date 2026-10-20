# Round 35 — 20/10/2026, exact-main static review

Source pin: `956ba4f236b1c92f1280d2097018c199e90ce8c7` at the audit worktree. Read-only source/test review; no app, API, DB, provider, production, secrets or PHI access. Tests were read, not run.

- **FIN-002 expanded, no new ID:** pharmacy receipt history is limited to 100 records per type/location. Active NHAP and KIEM screens render `items` without `has_more`, total or a truncation notice; the helper only logs. Threshold crossing is a conditional static gap; no operating volume proves it has happened.
- **API-002 expanded, no new ID:** active `/clinical/{visit_id}/status` route is reachable from a UI/BFF path, uses generic staff identity and service query scope is clinic+UUID without location/assignment. It returns patient name/code and workflow metadata but not SOAP/form body. This is same-clinic cross-location evidence, not cross-clinic access.
- **Pharmacy held observation:** low-stock badge uses physical quantity per unit while sellability accounts for expiry/reservations/returns. Current code/tests deliberately encode unit behavior, and there is no product contract saying the threshold means available-to-promise. Do not promote until that contract is decided.
- **Worker dedupe:** lease fencing, retry-cap, timer recovery, dead-letter and notification/retry issues overlap INF-005/011/012/017/018/022/023/026, LAB-001 and CLIN-053. No new finding.
- **Worker held observations:** `day-tep` could retain an advisory-lock boolean after DB session loss; supported impact is duplicate IO/work only, with guarded row updates. POS may retry after partner acceptance if DB cannot persist `SENT`; current KiotViet adapter refuses unfinished integration, so idempotency remains a future enablement check.
- Adjacent service-log/sono legacy routes hit retirement guards; MISA export routes require `accounting.finance.full` and remain clinic-scoped in reviewed paths. No independent finding from these slices; incomplete service paths remain marked partial.

Coverage and exact file hashes/ranges: `blocks/round35.coverage.json`. Full source audit remains incomplete; ledger status is not behavior coverage.
