# ClinicAI — LIFECYCLE INTEGRATION CHECKPOINT v1

**Ngày:** 22/09/2026  
**Phạm vi:** Ghép Selection + Finance/Payment + Routing + Execution thành một contract end-to-end.  
**Kết luận:** **GO để đóng gói implementation**, với các chỉnh hợp nhất dưới đây. Chưa phải phê duyệt production.  
**Không thực hiện:** code, migration, test, deploy.

---

## 1. Golden path đã khớp

```text
Official Service Order
  ↓
Selection = PENDING
  ↓ ConfirmServiceSelection
Selection = SELECTED
  ↓
Outstanding Bill
  ↓ Confirm Payment
Finance = PAID / NOT_REQUIRED
  ↓ AssignServiceRoom
Routing = ASSIGNED
  ↓
Effective Execution Readiness = WAITING
  ↓ StartService
Attempt #N = IN_PROGRESS
  ↓
CompleteService
Execution = COMPLETED
  ↓
Result lifecycle riêng
```

Không có bước nào cần AI/LLM/external API trên core fast path.

---

## 2. Chỉnh hợp nhất #1 — WAITING là effective state trước Start

Bốn module độc lập tạo một vấn đề nếu bắt Routing hoặc Payment phải trực tiếp ghi execution state.

Chốt integration:

```text
Effective WAITING
=
selection == SELECTED
AND FinanceGate financially_ready
AND routing == ASSIGNED
AND không active attempt
AND execution chưa terminal/interrupted
```

`WAITING` có thể được expose ở API/read model mà không bắt buộc phải là một cột được nhiều module cùng ghi.

Khi Start thành công mới có durable execution fact:

```text
attempt IN_PROGRESS
execution IN_PROGRESS
```

`PrepareServiceRetry` đưa order trở lại trạng thái có thể đánh giá readiness; attempt mới chỉ sinh khi Start thành công.

Mục đích: tránh Payment/Router cùng sở hữu `execution_status`.

---

## 3. Chỉnh hợp nhất #2 — Bill eligibility không chỉ nhìn Selection

Câu cũ:

```text
SELECTED => billable
```

chưa đủ.

Outstanding Bill v1 phải là:

```text
SELECTED
AND chưa bị execution/cancellation chặn
AND Clinic chargeable
AND chưa financially covered
```

Không đưa vào ordinary outstanding bill:
- `CANCELLED`;
- `NOT_PERFORMED`;
- `INTERRUPTED` đang/chưa được resolution;
- line đã có financial footprint cần review;
- line đã PAID/REFUND_PENDING/REFUNDED.

`IN_PROGRESS`/`COMPLETED` mà không có paid coverage ở Clinic là anomaly, không phải khoản để cashier tự thu bù; trả financial review.

---

## 4. Chỉnh hợp nhất #3 — cần `CancelService`

Lifecycle đã có state/event `CANCELLED` nhưng trước checkpoint chưa có command rõ.

Thêm semantic command:

```text
CancelService
```

Dùng khi có quyết định không thực hiện **trước Start**, sau khi order đã là official/selected.

Không dùng để thay thế:
- khách đổi lựa chọn trước financial commitment → Selection;
- không làm được tại phòng nhưng chưa Start → MarkServiceNotPerformed;
- đã Start rồi dừng → InterruptService.

Nếu đã có financial footprint:
- không xóa/đảo payment;
- execution = CANCELLED;
- tạo financial-resolution responsibility;
- refund/credit là command tài chính riêng.

Event:

```text
service.cancelled
```

---

## 5. Chỉnh hợp nhất #4 — một cơ chế idempotency cho core lifecycle

Target:

```text
command state
+ domain event
+ command receipt
```

cùng một DB transaction.

Áp cho:
- ConfirmServiceSelection;
- service payment command mới;
- Assign/Invalidate Routing;
- Start/Complete/NotPerformed/Interrupt/Cancel/PrepareRetry.

Router-level `IdempotencyGuard` hiện tại không được là correctness mechanism duy nhất cho payment multi-cycle vì receipt được save sau business transaction.

Compatibility có thể tồn tại, nhưng core correctness dùng transactional receipt.

---

## 6. Chỉnh hợp nhất #5 — canonical event names + compatibility

Canonical target:

```text
service_selection.confirmed
payment.confirmed
service.routed
service.routing_invalidated
service.started
service.completed
service.cancelled
service.not_performed
service.interrupted
result.ready
```

Current code còn:

```text
payment.recorded
dispatch.assigned
service.performed
```

Không rewrite lịch sử.

Implementation phải:
1. audit consumer của tên cũ;
2. chuyển producer/consumer có chủ đích;
3. nếu cần dùng compatibility adapter/dual observation trong rollout;
4. không phát hai business facts khác nghĩa chỉ để "cho xanh test".

---

## 7. Chỉnh hợp nhất #6 — `service_order.exec_status` là compatibility concern

Target đã tách:
- Selection;
- Finance derived state;
- Routing;
- Execution.

`exec_status` cũ đang gộp nhiều concern.

Không dùng nó làm source of truth mới.

Rollout cần compatibility projection/adapter cho reader cũ cho tới khi reader được chuyển.

Đặc biệt `INTERRUPTED` không được map âm thầm thành `NOT_PERFORMED`.

---

## 8. Cross-axis invariants

### Selection
- official order không bị xóa chỉ vì khách không chọn;
- sau financial commitment không quay lại simple checkbox edit;
- selection revision theo visit set.

### Finance
- server-authoritative outstanding bill;
- multi-cycle service payment;
- line-level immutable coverage;
- không auto re-bill VOIDED/REFUNDED;
- payment history không sửa.

### Routing
- authoritative assignment chỉ sau selected + finance ready;
- recommendation không phải state;
- reroute trước Start giữ tuổi chờ;
- invalidation trước Start → reassignment required;
- sau Start không normal reroute.

### Execution
- attempt chỉ sinh khi Start thành công;
- complete/interrupt target attempt cụ thể;
- after-start failure = INTERRUPTED, không NOT_PERFORMED;
- no-start failure = NOT_PERFORMED;
- cancellation trước Start = CANCELLED;
- no automatic refund.

---

## 9. Lock order end-to-end

Core commands trên cùng visit phải giữ hướng chung:

```text
VISIT
  ↓
TRANSACTIONAL RECEIPT LOCK
  ↓
SERVICE_ORDER / PAYMENT / ATTEMPT theo command
  ↓
QUEUE / WORK ITEM
  ↓
STATE
  ↓
EVENT
  ↓
RECEIPT
  ↓
COMMIT
```

Mục tiêu:
- Selection vs Payment serialize;
- Payment vs Start serialize;
- Routing vs Start serialize;
- Complete vs Interrupt serialize;
- two-actor Start chỉ một người thắng.

---

## 10. Work-item rule

Không tạo Work Item cho happy path.

Phải có responsibility rõ cho unresolved conditions:
- `REASSIGNMENT_REQUIRED`;
- `INTERRUPTED`;
- paid `CANCELLED`;
- paid `NOT_PERFORMED`;
- financial review/anomaly.

Async notification có thể đến sau; core transaction không được để unresolved money/work chỉ tồn tại dưới dạng một event rồi hy vọng consumer xử lý.

---

## 11. Review/result integration

`PERFORMED` requirement cũ phải chuyển ý nghĩa sang:

```text
Execution COMPLETED
```

Không thỏa khi:
- NOT_PERFORMED;
- INTERRUPTED chưa resolution/stop decision;
- CANCELLED.

`VALID_RESULT` tiếp tục thuộc result lifecycle.

Invariant:

```text
service.completed != result.ready
```

---

## 12. Các flow bất thường đã khớp

### Khách đổi ý trước payment
```text
SELECTED → NOT_SELECTED
```
Selection command, nếu chưa financial/routing/start lock.

### Đã trả rồi muốn bỏ
```text
CancelService
→ financial resolution
```
Không sửa history payment.

### Room hỏng trước Start
```text
ASSIGNED
→ routing invalidated
→ REASSIGNMENT_REQUIRED
→ AssignServiceRoom
```

### Máy hỏng sau Start
```text
IN_PROGRESS
→ InterruptService
→ INTERRUPTED
→ resolution
→ reroute nếu cần
→ PrepareServiceRetry
→ Start attempt mới
```

### Không làm được nhưng chưa Start
```text
WAITING
→ MarkServiceNotPerformed
```

### Response Start bị mất
```text
same Idempotency-Key
→ same attempt/result
```

### Complete attempt cũ đến muộn
```text
attempt_id mismatch
→ reject
```

---

## 13. Những gì KHÔNG block freeze core

Các policy sau phải nằm ở seam riêng, không để chúng kéo toàn lifecycle tiếp tục mở:
- vitals có là hard routing gate không;
- exact role/capability matrix;
- staff-on-shift hard/soft;
- external partner payment/execution;
- retry queue priority;
- partial service refund;
- PAID→VOIDED resolution;
- clinical participant/responsible clinician.

Có thể code architecture/core với policy seam và compatibility behavior, nhưng **production behavior của các policy này chưa được tự coi là phê duyệt**.

---

## 14. Một dependency ngoài lifecycle cần ghi rõ

Direct procedure/pelvic-floor arrival có thể đi thẳng từ check-in tới dịch vụ theo nguồn onsite.

Schema hiện tại yêu cầu `service_order.consultation_id`.

Lifecycle v1 bắt đầu từ lúc đã có **official service_order**.

Cách tạo official order cho direct-arrival là một work item/order-entry design riêng; không được bịa bằng consultation giả trong implementation lifecycle.

Điểm này không block freeze lifecycle, nhưng block rollout direct-arrival nếu chưa giải quyết.

---

## 15. GO / NO-GO

### GO
- đóng gói cho Claude Code;
- viết additive migration plan;
- implement theo vertical slices;
- viết targeted + integration tests;
- giữ unresolved policy sau interface/policy seam.

### Chưa GO production chỉ vì tài liệu này
Cần:
- tests green;
- runtime DB fingerprint/migration rehearsal;
- policy/permission sign-off tương ứng;
- staging smoke/UAT;
- rollback/monitoring.

---

## 16. Frozen core sau checkpoint

Nếu Tuyền chốt checkpoint này, Service Lifecycle v1 được coi là **FROZEN về contract lõi**:

```text
Selection
→ Outstanding Finance
→ Authoritative Routing
→ Execution Attempt
→ Result lifecycle riêng
```

Mọi implementation deviation phải báo lại, không được AI tự đổi nghiệp vụ.
