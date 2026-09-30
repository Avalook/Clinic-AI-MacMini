# ClinicAI — FINANCE GATE v1

**Ngày:** 22/09/2026  
**Trạng thái:** Đề xuất contract để Tuyền chốt; chưa phải schema/code đã triển khai.  
**Phụ thuộc đã chốt:** Service Lifecycle v1; Selection trước Payment; Multiple Service Payment Cycles theo hướng outstanding-bill + line-level coverage.  
**Không thực hiện trong tài liệu này:** migration, code, test, deploy.

---

## 1. Mục tiêu

FinanceGate trả lời đúng một câu cho `service_order`:

> Về mặt tài chính, order này đã đủ điều kiện để bắt đầu thực hiện chưa?

FinanceGate không:
- thu tiền;
- tạo QR;
- refund;
- route;
- gọi AI;
- quyết Selection;
- quyết Execution state.

`StartService` tổng hợp nhiều gate:

```text
selection == SELECTED
AND finance_gate.financially_ready
AND routing == ASSIGNED
AND execution cho phép start
```

---

## 2. Source of truth

Không thêm `service_order.billing_status` ở v1.

Billing state là **derived state** từ:

```text
service_order.selection_status
service_price
payment_cycle
payment_bill_line
payment_refund
payment_refund_line
```

Nguyên tắc:

```text
financial history đã tồn tại
→ ưu tiên immutable snapshot trong payment_bill_line

chưa có financial footprint
→ dùng service_price hiện hành để biết giá / billing owner
```

Không reinterpret lần thu lịch sử bằng bảng giá mới.

---

## 3. Derived states

FinanceGate v1 dùng các state:

```text
NOT_APPLICABLE
NOT_REQUIRED
DUE
PENDING_VERIFICATION
PAID
REFUND_PENDING
REFUNDED
FINANCIAL_DATA_INCOMPLETE
FINANCIAL_REVIEW_REQUIRED
EXTERNAL_PAYMENT_UNRESOLVED
```

### `NOT_APPLICABLE`

`selection_status != SELECTED`.

Không phải billing state nghiệp vụ chính; là kết quả nội bộ để FinanceGate nói "order này chưa ở bước tài chính".

`financially_ready = false`.

### `NOT_REQUIRED`

Clinic không cần thu tiền và đã có căn cứ chắc chắn để bỏ payment gate, ví dụ dịch vụ Clinic có giá chính thức bằng 0.

`financially_ready = true`.

### `DUE`

Order được `SELECTED`, Clinic thu tiền, giá hợp lệ, chưa có financial footprint đang/đã nhận tiền.

`financially_ready = false`.

### `PENDING_VERIFICATION`

Order nằm trong `payment_bill_line` của `payment_cycle.status = PENDING_VERIFICATION`.

`financially_ready = false`.

Không tạo lần thu thứ hai cho line này.

### `PAID`

Order nằm trong bill-line của một payment cycle đã thực sự nhận tiền:

```text
payment_cycle.paid_at IS NOT NULL
```

và không có refund/review condition chặn.

`financially_ready = true`.

### `REFUND_PENDING`

Có refund line của financial footprint này với parent refund `status = PENDING`.

`financially_ready = false`.

### `REFUNDED`

Số lượng refund `COMPLETED` đã hoàn đủ line dịch vụ.

`financially_ready = false`.

Không tự biến về `DUE`; thu lại cần explicit financial-resolution flow.

### `FINANCIAL_DATA_INCOMPLETE`

Không thể xác định giá/owner một cách chắc chắn:
- thiếu giá Clinic;
- nhiều giá authoritative mâu thuẫn;
- cấu hình billing owner mâu thuẫn.

`financially_ready = false`.

### `FINANCIAL_REVIEW_REQUIRED`

Có lịch sử tiền nhưng ordinary flow không được tự suy:
- service line bị partial refund;
- PAID rồi VOIDED mà chưa có resolution rõ;
- cùng service_order có nhiều financial coverage bất thường;
- payment history tồn tại nhưng allocation không đủ chắc;
- các invariant tài chính lịch sử mâu thuẫn.

`financially_ready = false`.

### `EXTERNAL_PAYMENT_UNRESOLVED`

`billing_owner = EXTERNAL_PARTNER`, nhưng ClinicAI chưa có contract cuối cho:
- có cần xác nhận "đã thanh toán tại đối tác" trước Start không;
- ai xác nhận;
- dữ liệu nào là bằng chứng.

Không tự coi external = free.

`financially_ready = false` ở v1 cho tới khi external-payment policy được chốt.

---

## 4. Precedence

Khi derive state cho một order:

```text
1. selection != SELECTED
   → NOT_APPLICABLE

2. có financial anomaly / ambiguous legacy footprint
   → FINANCIAL_REVIEW_REQUIRED

3. có refund PENDING
   → REFUND_PENDING

4. có refund COMPLETED một phần
   → FINANCIAL_REVIEW_REQUIRED

5. có refund COMPLETED đủ line
   → REFUNDED

6. có cycle từng nhận tiền:
      paid_at != NULL
   nhưng cycle/footprint rơi vào trạng thái cần review (vd VOIDED)
   → FINANCIAL_REVIEW_REQUIRED

7. có cycle PENDING_VERIFICATION
   → PENDING_VERIFICATION

8. có paid coverage sạch
   → PAID

9. chưa footprint:
      billing_owner EXTERNAL_PARTNER
      → EXTERNAL_PAYMENT_UNRESOLVED

10. chưa footprint:
      Clinic price = 0 hợp lệ
      → NOT_REQUIRED

11. chưa footprint:
      Clinic price hợp lệ > 0
      → DUE

12. thiếu/mâu thuẫn cấu hình giá
      → FINANCIAL_DATA_INCOMPLETE
```

Các bước có financial footprint phải đọc snapshot lịch sử trước config hiện tại.

---

## 5. `can_start()` contract

Tên semantic:

```text
FinanceGate.can_start(...)
```

có nghĩa:

> "Về tài chính có được Start hay chưa?"

Không có nghĩa toàn bộ lifecycle đã đủ Start.

Input concept:

```text
clinic_id
service_order_id
```

Khi gọi trong `StartService`, transaction đã lock visit trước.

Output:

```json
{
  "order_id": "...",
  "finance_state": "PAID",
  "payment_required_by_clinic": true,
  "financially_ready": true,
  "reason_code": null,
  "coverage_cycle_id": "...",
  "needs_human_review": false
}
```

Ví dụ DUE:

```json
{
  "order_id": "...",
  "finance_state": "DUE",
  "payment_required_by_clinic": true,
  "financially_ready": false,
  "reason_code": "SERVICE_PAYMENT_REQUIRED",
  "coverage_cycle_id": null,
  "needs_human_review": false
}
```

FinanceGate không trả bill total authoritative cho UI. BillService sở hữu việc đó.

---

## 6. Error/reason codes cho Start

| Finance state | Start reason/error |
|---|---|
| `NOT_APPLICABLE` | `SERVICE_NOT_SELECTED` |
| `DUE` | `SERVICE_PAYMENT_REQUIRED` |
| `PENDING_VERIFICATION` | `SERVICE_PAYMENT_PENDING_VERIFICATION` |
| `PAID` | không lỗi |
| `NOT_REQUIRED` | không lỗi |
| `REFUND_PENDING` | `SERVICE_REFUND_PENDING` |
| `REFUNDED` | `SERVICE_PAYMENT_REFUNDED` |
| `FINANCIAL_DATA_INCOMPLETE` | `SERVICE_FINANCIAL_DATA_INCOMPLETE` |
| `FINANCIAL_REVIEW_REQUIRED` | `SERVICE_FINANCIAL_REVIEW_REQUIRED` |
| `EXTERNAL_PAYMENT_UNRESOLVED` | `SERVICE_EXTERNAL_PAYMENT_UNRESOLVED` |

Finance conflict là 409 khi business state hiện tại chưa cho Start.

---

## 7. Batch query contract

Không query từng order.

Internal contract:

```text
FinanceGate.states_for_orders(
    conn,
    clinic_id,
    order_ids[]
) -> map[order_id, FinanceDecision]
```

Một query/batch cần trả đủ facts cho tất cả order:

```text
service_order:
  id
  visit_id
  selection_status
  service_code

current price config:
  resolved billing_owner
  resolved price
  price/config issue

payment footprint:
  payment_bill_line id
  payment_cycle id/status/paid_at
  billing_owner snapshot
  quantity snapshot

refund aggregate per bill line:
  pending quantity
  completed quantity
```

Pure function:

```text
derive_finance_state(facts)
```

không gọi DB.

`can_start(order_id)` dùng chính batch path với một phần tử, không có logic thứ hai.

Cashier/board có thể batch theo nhiều order/visit và dùng cùng derivation để tránh N+1.

---

## 8. Financial footprint rules

Một service line có footprint khi có:

```text
payment_bill_line.source_type = 'service_order'
payment_bill_line.source_id = service_order.id
```

Cycle `CANCELLED` chưa từng nhận tiền (`paid_at IS NULL`) không giữ financial coverage; line có thể quay lại `DUE`.

Cycle đã từng nhận tiền (`paid_at IS NOT NULL`) là lịch sử tài chính thật, kể cả current status đã thành `VOIDED`.

Không tự cho VOIDED quay lại DUE.

---

## 9. Duplicate coverage

Bình thường một `service_order` chỉ được một payment footprint đang/đã nhận tiền cover.

Nếu batch query thấy nhiều footprint cạnh tranh cho cùng order:

```text
FINANCIAL_REVIEW_REQUIRED
reason = MULTIPLE_SERVICE_COVERAGE
```

Payment write path sau này phải có DB guard chống insert duplicate coverage.

FinanceGate vẫn có defense-in-depth khi đọc legacy/anomaly.

---

## 10. Refund derivation

Service line quantity v1 là `1`.

Nếu:

```text
refund_completed_qty = 0
```

không ảnh hưởng PAID.

Nếu:

```text
0 < refund_completed_qty < 1
```

→ `FINANCIAL_REVIEW_REQUIRED`.

Nếu:

```text
refund_completed_qty = 1
```

→ `REFUNDED`.

Nếu có bất kỳ refund `PENDING` trên line:

```text
REFUND_PENDING
```

được ưu tiên hơn PAID.

Refund `FAILED/CANCELLED` không làm mất paid coverage.

---

## 11. Pricing / billing owner

Không viết lại một resolver giá thứ hai.

FinanceGate phải dùng cùng pricing semantics với BillService:
- không có giá Clinic → incomplete;
- nhiều giá authoritative khác nhau → incomplete;
- một giá → dùng;
- 0 là giá hợp lệ, không phải missing.

`billing_owner` phải resolve chắc chắn.

Nếu config có nhiều row khiến owner/price mâu thuẫn:

```text
FINANCIAL_DATA_INCOMPLETE
```

không dùng `max()` hoặc "chọn dòng đầu" để đoán.

---

## 12. External partner

Không coi `EXTERNAL_PARTNER` là `NOT_REQUIRED` một cách tự động.

Clinic observation có nhu cầu đối tác tự thu và có thao tác "xác nhận đã thanh toán", nhưng exact contract chưa chốt.

Cho tới khi có External Payment contract:

```text
EXTERNAL_PARTNER
→ EXTERNAL_PAYMENT_UNRESOLVED
→ financially_ready = false
```

Sau này có thể thêm derived state:

```text
EXTERNAL_PAYMENT_CONFIRMED
```

mà không đổi StartService contract; Start chỉ nhìn `financially_ready`.

---

## 13. Performance contract

FinanceGate:
- chỉ DB local;
- không external;
- không AI;
- không network fan-out;
- một batch query cho danh sách order;
- pure derivation sau query.

`StartService` một order không được phát sinh N+1.

Cashier Board nhiều visit không gọi `tinh_hoa_don()` tuần tự từng visit; cần batch/read-model riêng.

SLO `<300ms P95` cho core command vẫn là mục tiêu staging, chưa phải runtime guarantee.

---

## 14. Tests bắt buộc

1. Selected + Clinic price > 0 + no footprint → DUE.
2. Selected + Clinic price 0 → NOT_REQUIRED.
3. Not selected → NOT_APPLICABLE.
4. Pending QR line → PENDING_VERIFICATION.
5. PAID line → PAID.
6. Pending refund → REFUND_PENDING.
7. Full refund completed → REFUNDED.
8. Partial refund → FINANCIAL_REVIEW_REQUIRED.
9. PAID→VOIDED without explicit financial resolution → FINANCIAL_REVIEW_REQUIRED.
10. Cancelled pending cycle, never paid → DUE again.
11. Duplicate historical coverage → FINANCIAL_REVIEW_REQUIRED.
12. Missing price → FINANCIAL_DATA_INCOMPLETE.
13. Conflicting price → FINANCIAL_DATA_INCOMPLETE.
14. External partner → EXTERNAL_PAYMENT_UNRESOLVED.
15. Refund FAILED/CANCELLED does not remove PAID coverage.
16. Batch 30 orders uses one finance-data query, same results as single-order derivation.
17. Config price changes after payment do not reinterpret immutable paid snapshot.
18. StartService accepts PAID/NOT_REQUIRED only from finance perspective and rejects all blocking states with stable error codes.

---

## 15. Boundaries

FinanceGate does not:
- decide customer selection;
- build authoritative payable bill;
- create payment cycles;
- refund;
- reroute;
- start execution;
- call AI;
- call external partner.

Owners:

```text
SelectionService
  → customer intent

BillService
  → outstanding amount / authoritative bill

PaymentService
  → collect / verify / cycle

RefundService
  → return money

FinanceGate
  → derive financial readiness

ExecutionService
  → enforce FinanceGate before Start
```

---

## 16. Chưa chốt

- Exact external-partner payment confirmation contract.
- Business policy for PAID→VOIDED resolution.
- Business policy for full refund then recollect.
- Whether fractional service refunds should be forbidden at write-time.
- Exact DB query/CTE/index after benchmark.
- Permission matrix for financial review/resolution.

---

## 17. Implementation rule for AI

AI implementing FinanceGate must not:
- add `billing_status` column without new design approval;
- duplicate BillService price rules;
- infer paid from `payment.status` alone;
- infer paid from visit-level payment existence;
- auto-rebill VOIDED/REFUNDED service;
- treat external partner as free;
- call external APIs in `can_start`;
- loop one query per order.

Any conflict between current code and this contract must be reported, not silently resolved.

---

**Không có code, migration hoặc deploy nào được thực hiện khi tạo tài liệu này.**
