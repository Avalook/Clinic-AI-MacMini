# Round 46 — exact-main booking, auth/location and payment review

Source SHA: `956ba4f236b1c92f1280d2097018c199e90ce8c7`. Evidence was read from immutable Git blobs with `git show`; the checkout with user WIP was not used as evidence. Tests were read only, never run. No ClinicAI app, API, DB, provider, VPS, production, secrets, or PHI was accessed.

## Decisions

- **Added FE-027 LOW:** stale `clinicai_location` cookie can block the location selector after the selected location is deactivated. Backend correctly rejects the inactive location; the selector/BFF path does not recover or clear the stale context. Same-clinic availability issue, no authorization bypass.
- **Added CLIN-057 LOW:** replaying a committed PATCH reschedule after response loss can append a target-to-same-target history row, a new event/outbox item, and an operations notification. Appointment final state remains one correct row. Conditional on caller retry; no production incident or DB reproduction claimed.
- **Extended FE-023:** same pending-state cleanup gap exists in forgot/reset-password forms. No authentication bypass was found.
- **Extended SEC-027:** doctor-assignment worklist endpoint returns same-clinic patient contact PII behind identity-only guard; page-level gate is not route authorization. Clinic/location scope remains.
- **Deduplicated payments/refunds:** receipt/replay, rounding, tender and invoice company cases remain in INF-007, FIN-001/004/015/016 and DB-007. Cashier cross-day outstanding backlog remains held because source comments and tests indicate the behavior may be intentional; owner policy is needed before changing FIN-019.
- **Held booking capacity question:** unassigned appointments are rejected by service precheck while trigger comments describe exemption; policy/source-of-truth is unclear, so no finding yet.
- **Shift config:** accepted close time `24:30` is outside normal minute-of-day semantics, but the reviewed path still clips visible booking windows at the shift/day bound; insufficient user-visible impact to promote.

## Coverage and limits

Full files, exact line counts, SHA-256 hashes, targeted ranges and dedupe notes are in `blocks/round46.coverage.json`. Booking service/router and payment/cashier services received full reads; auth/location and shift paths received cross-layer targeted traces. Tests were not run and runtime behavior was not validated. The repository audit remains open; path-level coverage is not semantic or behavioral completeness.
