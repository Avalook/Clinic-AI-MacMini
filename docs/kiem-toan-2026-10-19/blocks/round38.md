# Round 38 — 20/10/2026, exact-main static review

Source pin: `956ba4f236b1c92f1280d2097018c199e90ce8c7`; all source reads use `git show <SHA>:<path>`. Tests are read-only and were not run. No ClinicAI app/API/DB/provider, production, secrets or PHI access. Full source audit remains incomplete. Exact ranges and full-file hashes: `blocks/round38.coverage.json`.

## Booking and clinical ownership

- **CLIN-055 MEDIUM / confirmed_static added:** changing patient/service starts asynchronous history lookup. A null/error response silently returns; there is no pending state in `canBook`, and POST sends the current `patientKind`. The booking service accepts valid `NEW`; `_attach_episode` closes an existing live episode as `new_problem`. A stale NEW from the prior patient/service can therefore close the episode for the newly selected pair if the new lookup is failed or still pending at submit. Conditional static trace only; no fault-injection, runtime or production occurrence. `CLIN-025` is different: it covers invalid enum strings coerced to `None`, whereas this is a stale but valid `NEW`.
- Recommended controls: clear/bind state to exact patient-service pair and request generation, represent lookup as pending/unknown and block submission until fresh confirmation; prefer server-side derivation/validation inside booking transaction.

## Security extension

- **SEC-027 expanded, no duplicate ID:** `/appointments/lich-su-dich-vu` depends on `get_current_identity`; the router declares `_DOC_LICH_GUARD` for appointment/create/check-in/clinical capabilities but this route does not use it. The service returns appointment count and active episode status/opened/last-visit timestamps. Queries are filtered by clinic, patient and service. This supports a same-clinic least-privilege concern; no cross-clinic read or current-browser reachability was established.

## Pharmacy sales versus stock — held

- No finding added. Read traces show cashier supplies recorded in `luot_vat_tu` and service bill/payment lines, while warehouse stock uses separate `vat_tu_phieu` / `vat_tu_txn` and balance triggers. Existing tests verify the two local lifecycles but do not establish whether an extra sale must automatically decrement warehouse stock. The prior audit already holds this exact product-contract question.
- Do not call this a proven inventory mismatch until the owner decides whether a sale is stock-bearing, where it is issued from, and how void/refund/returns avoid double decrement. If linked by policy, require an atomic stock reference and cross-ledger reconciliation; if not, document the separate consumption/issue workflow and expected variance.
- Tests and the operations plan were read but not run. The evidence is static and does not establish production stock accuracy.

## Coverage limits

The service-history route was upgraded from structural scan to targeted semantic trace in `MAIN-PHAM-VI.json`; other large files remain partial. The two pharmacy module-registration reads lack exact ranges in the agent note and are not credited as line-level coverage. Existing count of 2,890 paths is inventory size, not completeness.
