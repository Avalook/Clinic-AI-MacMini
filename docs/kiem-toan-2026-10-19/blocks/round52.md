# Round 52 — phí khám mặc định sau khi đổi dịch vụ trong hồ sơ

Source SHA 956ba4f236b1c92f1280d2097018c199e90ce8c7. Review used immutable Git blobs via git show. Tests read only and not run. No ClinicAI application, API, DB, provider, VPS, production, secrets or PHI was accessed.

## Finding

- Added CLIN-060 MEDIUM: the in-chart switch permits a visit with a prior exam payment. When no child exam service is selected, billing derives the fallback from the current service type gia_mac_dinh, but emits stable source exam-{visit_id}. The outstanding-bill path marks that source covered by an existing paid/pending line and removes it without comparing the old snapshot amount to the newly computed fee or recording a debit/credit adjustment.
- Changing from a lower default fee to a higher one can hide the difference from the receivable; changing to a lower one can leave an overpayment without a corresponding credit/refund adjustment. Static inference only; no payment result or production occurrence was reproduced.
- CLIN-010 concerns appointment/visit type divergence via reschedule after check-in. CLIN-060 follows the dedicated chart path that updates both rows. Explicit child exam sources are outside this finding.

## Recommendation and validation

Define fee policy after a paid visit changes service type. Keep original payment and fee snapshot immutable; if the new type changes the obligation, write a traceable debit/credit adjustment for the difference. If policy retains the original fee, continue billing from that snapshot. A synthetic DB test should collect 100,000đ, switch to a 150,000đ default, then to 50,000đ and assert exact receivable/credit under the chosen rule, with no duplicate collection and complete history.

Exact source ranges, hashes and read coverage are in blocks/round52.coverage.json and PHAT-HIEN.json. Tests read-not-run. Full source audit remains incomplete.
