# ClinicAI — EXECUTION v1

**Ngày:** 22/09/2026  
**Trạng thái:** Contract thiết kế để Tuyền chốt trước implementation. Không phải schema/code đã triển khai.  
**Phụ thuộc:** Service Lifecycle v1, Service Selection v1, FinanceGate v1, Routing v1, Extension Architecture v0.1.  
**Không thực hiện trong tài liệu này:** code, migration, test, deploy.

---

## 1. Mục tiêu

Execution trả lời:

```text
dịch vụ đã sẵn sàng chờ làm chưa?
đã thực sự bắt đầu chưa?
attempt nào đang chạy?
đã hoàn thành thật chưa?
chưa bắt đầu nhưng không làm được?
đã bắt đầu nhưng bị gián đoạn?
có được retry bằng attempt mới không?
```

Execution không:
- chọn dịch vụ;
- thu tiền;
- xếp phòng;
- quyết kết quả đã sẵn sàng;
- gọi AI/external API.

Fast path:

```text
Selection
   ↓
FinanceGate
   ↓
Routing
   ↓
Execution
```

---

## 2. Order-level execution states

Execution v1 dùng:

```text
PENDING
WAITING
IN_PROGRESS
COMPLETED
CANCELLED
NOT_PERFORMED
INTERRUPTED
```

### `PENDING`
Official order tồn tại nhưng chưa vào hàng thực hiện.

### `WAITING`
Order đã đủ điều kiện vận hành để chờ thực hiện:
- selected;
- finance ready;
- routing assigned;
- chưa có active attempt.

### `IN_PROGRESS`
Có đúng một execution attempt đang chạy.

### `COMPLETED`
Một attempt đã hoàn thành thành công. Đây là terminal success của execution.

### `CANCELLED`
Quyết định không thực hiện **trước khi bắt đầu** theo cancellation flow.

### `NOT_PERFORMED`
Đã tới bước thực hiện / đang chờ thực hiện nhưng **không có attempt thực sự start**, cuối cùng không làm.

### `INTERRUPTED`
Có attempt đã thực sự start nhưng attempt đó bị dừng trước khi hoàn thành.

`INTERRUPTED` không mặc định là terminal của `service_order`; nó cần resolution:
- retry;
- reschedule;
- close/financial resolution theo policy.

---

## 3. Execution Attempt

Một `service_order` có thể có nhiều attempt.

Ví dụ:

```text
Order SA

Attempt #1
room SA1
10:00 STARTED
10:05 INTERRUPTED
reason = EQUIPMENT_FAILURE

Attempt #2
room SA2
10:18 STARTED
10:35 COMPLETED
```

Invariant:

> Mỗi attempt tối đa có một successful Start và một final outcome.

Không còn invariant:

```text
mỗi service_order chỉ được service.started một lần
```

Mà là:

```text
mỗi attempt chỉ được service.started một lần
```

---

## 4. Persistence concept cho attempt

Đề xuất table:

```text
service_execution_attempt
```

Concept fields:

```text
id
clinic_id
service_order_id
attempt_no

room_id_snapshot
routing_revision_snapshot

status
  IN_PROGRESS
  COMPLETED
  INTERRUPTED

started_by
started_at

completed_by
completed_at

interrupted_by
interrupted_at
interruption_reason_code
interruption_reason_note

created_at
updated_at
```

Constraints đề xuất:

```text
UNIQUE (clinic_id, service_order_id, attempt_no)

at most one IN_PROGRESS attempt per service_order
```

`attempt_no` bắt đầu từ 1 và tăng tuần tự trong transaction.

Không tạo attempt row khi service chưa thực sự Start.

Do đó:

```text
NOT_PERFORMED
```

không sinh execution attempt giả.

---

## 5. Actor semantics — không dùng một `performed_by` để nói mọi thứ

Current code có một `service_order.performed_by`; khi điều dưỡng Start rồi bác sĩ bấm Xong, code có thể overwrite `performed_by` thành bác sĩ.

Execution v1 không coi một field như vậy là đủ để trả lời:
- ai bấm Start;
- ai thao tác thực tế;
- ai hoàn thành trên hệ thống;
- ai chịu trách nhiệm chuyên môn.

Attempt ghi riêng:

```text
started_by
completed_by
interrupted_by
```

Đây là **system action actors**.

Nếu nghiệp vụ cần:
- responsible clinician;
- operator;
- assistant;
- reviewer;

thì phải có clinical-participant contract riêng. Không suy `completed_by = người thực hiện chuyên môn`.

Trong migration compatibility có thể tiếp tục cập nhật `service_order.performed_by`, nhưng field đó không được coi là source of truth mới cho actor history.

---

## 6. `StartService`

Semantic:

```text
StartService
```

### Input concept

```text
service_order_id
expected_execution_revision
expected_routing_revision
idempotency_key
```

Không để client tự gửi `attempt_no`.

Server tạo attempt mới atomically.

### Hard preconditions

Order:
- thuộc đúng clinic;
- `selection_status = SELECTED`;
- FinanceGate `financially_ready = true`;
- routing `ASSIGNED`;
- execution `WAITING`;
- không có active attempt;
- expected execution/routing revision đúng.

Actor:
- có capability `service.execute.start`;
- actor/node capability hợp lệ theo policy dịch vụ.

Queue:
- có đúng một live SERVICE queue entry của order;
- queue status cho phép start (`waiting` hoặc `called`);
- room của queue khớp authoritative routing room;
- visit không đang `serving` ở nơi khác.

### Success atomic effect

```text
create attempt #N status=IN_PROGRESS
    room snapshot = current room
    routing revision snapshot

service_order.execution_status = IN_PROGRESS
execution_revision += 1

queue_entry.status = serving
queue_entry.serving_at = now

block other queue entries of same visit

record service.started

store command receipt
COMMIT
```

Event payload tối thiểu:

```json
{
  "visit_id": "...",
  "service_order_id": "...",
  "attempt_id": "...",
  "attempt_no": 2,
  "room_id": "...",
  "execution_revision": 7
}
```

Không PHI không cần thiết.

---

## 7. Idempotency của Start

### Same key + same intent

Nếu request đầu đã commit nhưng response mất:

```text
same idempotency key
→ replay same result
→ same attempt_id
→ không attempt thứ hai
→ không event thứ hai
```

### Same key + payload khác

```text
IDEMPOTENCY_KEY_REUSED
```

### Different key, cùng WAITING snapshot

Hai nhân viên cùng bấm Start:

```text
actor A key=A
actor B key=B
```

Do visit/order lock + execution revision:
- một người thắng;
- người còn lại thấy state/revision đã đổi;
- trả conflict;
- không overwrite actor;
- không attempt thứ hai.

---

## 8. Start response

```json
{
  "ok": true,
  "order_id": "...",
  "attempt_id": "...",
  "attempt_no": 2,
  "execution_status": "IN_PROGRESS",
  "execution_revision": 7,
  "started_at": "...",
  "started_by": "...",
  "room_id": "..."
}
```

Retry cùng key trả đúng logical result này.

---

## 9. `CompleteService`

Semantic:

```text
attempt đã thực hiện xong thành công
```

Không dùng `performed=true/false`.

### Input

```text
service_order_id
attempt_id
expected_execution_revision
idempotency_key
```

Không đưa `result_note` vào Execution command v1.

Lý do:

```text
service.completed != result.ready
```

Result fields/media/forms thuộc Result/Form lifecycle riêng.

### Preconditions

- order `IN_PROGRESS`;
- attempt_id là active attempt của đúng order;
- attempt status `IN_PROGRESS`;
- actor có `service.execute.complete`;
- execution revision đúng.

### Success

```text
attempt.status = COMPLETED
attempt.completed_by = actor
attempt.completed_at = now

order.execution_status = COMPLETED
execution_revision += 1

current queue entry → done
release other blocked queues

record service.completed
command receipt
COMMIT
```

`service.completed` aggregate nên là `service_order`.

Không phát `service.performed` cho contract mới.

Historical event cũ giữ nguyên, không rewrite history.

---

## 10. `MarkServiceNotPerformed`

Semantic:

> Service đã tới bước chờ làm nhưng **không có attempt nào bắt đầu** và cuối cùng không làm.

### Input

```text
service_order_id
expected_execution_revision
reason_code
reason_note optional/required theo code
idempotency_key
```

Reason concept:

```text
PATIENT_DECLINED_AT_ROOM
CLINICAL_CONTRAINDICATION_BEFORE_START
EQUIPMENT_UNAVAILABLE_BEFORE_START
STAFF_UNAVAILABLE
OTHER
```

Không dùng `EQUIPMENT_FAILURE_AFTER_START`; case đó là Interrupt.

### Preconditions

- execution = `WAITING`;
- không có active/historical started attempt cho current execution cycle;
- actor có `service.execute.not_performed`;
- revision đúng.

### Success

```text
execution = NOT_PERFORMED
execution_revision += 1

live queue → done/non-actionable
release blocked queues

service.not_performed
financial-resolution work item nếu đã có clinic payment
command receipt
COMMIT
```

Không auto-refund.

Nếu service đã PAID:
- financial history giữ nguyên;
- tạo/activate trách nhiệm tài chính;
- refund/credit do financial flow xử lý.

---

## 11. `InterruptService`

Semantic:

> Attempt đã Start nhưng không thể hoàn thành.

### Input

```text
service_order_id
attempt_id
expected_execution_revision
reason_code
reason_note
idempotency_key
```

Reason concept:

```text
EQUIPMENT_FAILURE
PATIENT_REQUEST
CLINICAL_SAFETY
TECHNICAL_FAILURE
STAFF_UNAVAILABLE
OTHER
```

`OTHER` cần note.

### Preconditions

- order `IN_PROGRESS`;
- attempt đúng active attempt;
- actor có `service.execute.interrupt`;
- revision đúng.

### Success

```text
attempt.status = INTERRUPTED
attempt.interrupted_by = actor
attempt.interrupted_at = now
attempt.reason = ...

order.execution_status = INTERRUPTED
execution_revision += 1

current queue → done/non-actionable
release blocked queues

service.interrupted
create/activate interruption-resolution responsibility
command receipt
COMMIT
```

Không:
- auto refund;
- auto mark completed;
- auto create new attempt;
- auto choose new room.

---

## 12. Late command safety

`attempt_id` là bắt buộc cho Complete/Interrupt.

Ví dụ:

```text
Attempt #1 interrupted
→ retry
→ Attempt #2 started

request Complete của Attempt #1 đến muộn
```

Backend thấy:

```text
attempt_id #1 != active attempt #2
```

và reject.

Không được để một request mạng cũ đóng attempt mới.

Error:

```text
EXECUTION_ATTEMPT_NOT_ACTIVE
```

Đây là lý do không chỉ gửi `service_order_id`.

---

## 13. Complete vs Interrupt race

Hai command đồng thời trên cùng attempt:

```text
CompleteService
InterruptService
```

cùng lock visit/order/attempt theo thứ tự.

Một command commit trước.

Command sau thấy:
- attempt không còn IN_PROGRESS;
- execution revision stale.

→ conflict.

Không có trạng thái vừa COMPLETED vừa INTERRUPTED.

---

## 14. Retry sau interruption

Execution v1 cần explicit resolution command:

```text
PrepareServiceRetry
```

Không để `StartService` tự hiểu:

```text
INTERRUPTED → start lại luôn
```

vì retry có thể cần:
- bác sĩ quyết;
- đổi phòng;
- xử lý equipment;
- xác nhận khách;
- xử lý tài chính.

### Input

```text
service_order_id
interrupted_attempt_id
expected_execution_revision
reason / resolution_note
idempotency_key
```

### Preconditions

- execution = `INTERRUPTED`;
- interrupted_attempt_id đúng attempt cuối;
- không active attempt;
- actor có `service.execute.retry`;
- chuyên môn/policy cho phép retry;
- Selection vẫn hợp lệ;
- FinanceGate vẫn không có blocker;
- routing đang `ASSIGNED` tới room hợp lệ hoặc đã được reroute xong.

### Success

```text
execution = WAITING
execution_revision += 1

create/reactivate SERVICE queue entry
(no attempt row yet)

close/complete interruption-resolution responsibility
command receipt
COMMIT
```

Attempt mới chỉ được tạo khi `StartService` thật sự thành công.

### Queue priority của retry

**[CHƯA CHỐT]**

Không tự quyết retry giữ nguyên tuổi chờ hay bắt đầu eligibility mới.

Đây là vận hành thực tế cần clinic/PM chốt:
- thiết bị lỗi do clinic → có thể giữ ưu tiên;
- bệnh nhân chủ động dừng → có thể khác.

Implementation không được tiện tay dùng `now()` hay giữ timestamp cũ mà không có policy.

---

## 15. Routing consequence sau interruption

Không mọi interruption đều làm room cũ vô hiệu.

Ví dụ:

```text
PATIENT_REQUEST
```

room có thể vẫn tốt.

Nhưng:

```text
EQUIPMENT_FAILURE
```

có thể cần Routing invalidation.

Execution v1 không hard-code mọi reason → routing transition.

Contract:

```text
InterruptionResolutionPolicy
```

quyết:
- room assignment còn dùng được;
- cần `InvalidateServiceRouting`;
- ai phải xử lý.

Nếu room phải đổi:
1. InterruptService;
2. routing invalidation / AssignServiceRoom;
3. PrepareServiceRetry;
4. StartService → attempt mới.

Không cho Start attempt mới với room đã invalid.

---

## 16. Permission / capability

Execution command dùng capability:

```text
service.execute.start
service.execute.complete
service.execute.not_performed
service.execute.interrupt
service.execute.retry
```

Ngoài capability command, actor phải phù hợp node/service policy.

Current code dùng:
- global `PERFORMER_ROLES`;
- `node_definition.actor_roles`;
- nhóm hỗ trợ phòng.

Hướng mới nên tận dụng capability/node config, không copy role set vào từng command.

### Source conflict cần giữ mở

Current test/code đang khóa:
- thủ thuật chỉ DOCTOR;
- một số node actor role cụ thể.

Khảo sát phòng khám mới lại yêu cầu:
- điều dưỡng thủ thuật có thể thao tác đầy đủ;
- điều dưỡng siêu âm có thể thao tác thay bác sĩ siêu âm;
- bác sĩ xem realtime.

Không được chọn một bên theo code cũ hoặc theo tiện triển khai.

Trước implementation cần permission checkpoint với PM/phòng khám/bác sĩ cho từng node.

---

## 17. Clinical actor vs system actor

Execution v1 chỉ chốt actor của command.

Ví dụ:

```text
Nurse started attempt
Doctor viewed/reviewed result
```

không có nghĩa:
- nurse là responsible clinician;
- doctor là operator;
- người bấm Complete là performer chuyên môn.

Nếu hồ sơ pháp lý cần clinical responsibility, thiết kế riêng:

```text
service participants / professional responsibility
```

và có phê duyệt chuyên môn.

Không suy từ nút bấm.

---

## 18. Queue effects

### Start
Current live service queue:

```text
waiting/called → serving
```

các queue khác của visit:

```text
waiting/called → blocked
```

### Complete
Current queue:

```text
serving → done
```

sau đó release blocked queues theo policy hàng chờ.

### NotPerformed
Current waiting/called queue:

```text
→ done/non-actionable
```

không có serving interval.

### Interrupt
Current serving queue:

```text
→ done/non-actionable
```

Retry sau này tạo một live SERVICE queue entry mới cho cùng order.

Unique-live constraint hiện tại cho phép lịch sử nhiều queue entries miễn chỉ một live row.

---

## 19. Work Item / unresolved responsibility

### Interrupted
Không được để:

```text
execution = INTERRUPTED
```

mà không có owner.

Trong cùng core transaction phải create/activate trách nhiệm:

```text
Resolve interrupted service
```

Outcome:
- retry;
- reschedule;
- close;
- financial resolution;
- clinical decision.

### NotPerformed + đã thu tiền
Create/activate:

```text
Financial resolution required
```

Không dựa duy nhất vào async consumer để tránh tiền khách bị quên.

Exact generic work_item payload/owner mapping cần impact map trước implementation.

---

## 20. Domain Events

Canonical v1:

```text
service.started
service.completed
service.not_performed
service.interrupted
```

Aggregate:

```text
service_order
```

### `service.started`

```json
{
  "visit_id": "...",
  "attempt_id": "...",
  "attempt_no": 2,
  "room_id": "...",
  "execution_revision": 7
}
```

### `service.completed`

```json
{
  "visit_id": "...",
  "attempt_id": "...",
  "attempt_no": 2,
  "execution_revision": 8
}
```

### `service.interrupted`

```json
{
  "visit_id": "...",
  "attempt_id": "...",
  "attempt_no": 1,
  "reason_code": "EQUIPMENT_FAILURE",
  "execution_revision": 5
}
```

### `service.not_performed`

Không có `attempt_id`, vì không attempt nào start.

Không phát event cho failed command/conflict.

---

## 21. Result lifecycle separation

Current `complete_service()` có thể:
- ghi `result_note`;
- set `ket_qua_luc`;
- khiến result flow đi tiếp.

Execution v1 tách điều này.

```text
CompleteService
→ execution completed

Result/Form command
→ result data / media / readiness
```

Không mặc định:

```text
service.completed = result.ready
```

Một service có thể:
- completed nhưng result đến sau;
- completed và không có result;
- result được upload/amend sau đó.

Backward compatibility adapter có thể còn tồn tại trong rollout, nhưng target contract không trộn hai concern.

---

## 22. External partner boundary

Current code có shortcut đối tác lấy mẫu có thể:

```text
authorized / assigned / in_progress
→ performed
```

và tự điền started/finished timestamps.

Execution v1 **không ép** shortcut này vào internal attempt model trước khi external lifecycle được chốt.

External partner còn các câu hỏi mở:
- sample collection là execution attempt hay external milestone?
- payment confirmation ở đâu?
- có internal routing không?
- result ready sau bao lâu?

Không silent map external shortcut thành `COMPLETED` v1 khi chưa có contract.

---

## 23. Order-level revision

Đề xuất concept:

```text
execution_revision
```

tách khỏi:
- selection revision;
- routing revision;
- generic legacy `version`.

Lý do:

```text
routing đổi
không nên tự làm stale một CompleteService
nếu active attempt không đổi
```

Start/Complete/Interrupt/NotPerformed/Retry dùng `expected_execution_revision`.

Exact physical column/schema chưa chốt trong tài liệu này.

---

## 24. Transaction / lock order

Giữ thứ tự nhất quán:

```text
VISIT
  ↓
COMMAND RECEIPT / IDEMPOTENCY
  ↓
SERVICE_ORDER
  ↓
ACTIVE / TARGET ATTEMPT
  ↓
EXECUTION REVISION CHECK
  ↓
SELECTION / FINANCE / ROUTING GATES nếu command cần
  ↓
QUEUE ROW
  ↓
UPDATE ATTEMPT + ORDER
  ↓
WORK ITEM nếu cần
  ↓
DOMAIN EVENT
  ↓
COMMAND RECEIPT
  ↓
COMMIT
```

Receipt phải cùng transaction.

Không dùng router-level cache ngoài transaction làm correctness duy nhất cho Start/Complete/Interrupt.

---

## 25. Error codes

Stable proposal:

```text
SERVICE_NOT_SELECTED
SERVICE_FINANCE_NOT_READY
SERVICE_NOT_ROUTED
SERVICE_ROUTING_STALE

EXECUTION_NOT_WAITING
EXECUTION_ALREADY_IN_PROGRESS
EXECUTION_TERMINAL
EXECUTION_REVISION_CONFLICT

EXECUTION_ATTEMPT_NOT_FOUND
EXECUTION_ATTEMPT_NOT_ACTIVE
EXECUTION_ATTEMPT_ALREADY_FINISHED

PATIENT_BUSY
QUEUE_NOT_READY

SERVICE_NOT_PERFORMABLE
SERVICE_RETRY_NOT_ALLOWED
SERVICE_RETRY_ROUTING_REQUIRED
SERVICE_RETRY_FINANCIAL_BLOCKED

EXECUTION_REASON_REQUIRED
EXECUTION_PERMISSION_DENIED

IDEMPOTENCY_KEY_REUSED
```

FinanceGate reason detail có thể trả kèm:

```text
finance_reason_code
```

không copy lại finance logic.

---

## 26. Response contracts

### Start

```json
{
  "ok": true,
  "order_id": "...",
  "attempt_id": "...",
  "attempt_no": 1,
  "execution_status": "IN_PROGRESS",
  "execution_revision": 3,
  "room_id": "...",
  "started_at": "...",
  "started_by": "..."
}
```

### Complete

```json
{
  "ok": true,
  "order_id": "...",
  "attempt_id": "...",
  "execution_status": "COMPLETED",
  "execution_revision": 4,
  "completed_at": "..."
}
```

### Interrupt

```json
{
  "ok": true,
  "order_id": "...",
  "attempt_id": "...",
  "execution_status": "INTERRUPTED",
  "execution_revision": 4,
  "reason_code": "EQUIPMENT_FAILURE",
  "resolution_required": true
}
```

### NotPerformed

```json
{
  "ok": true,
  "order_id": "...",
  "execution_status": "NOT_PERFORMED",
  "execution_revision": 4,
  "reason_code": "PATIENT_DECLINED_AT_ROOM"
}
```

---

## 27. Performance

Core execution commands:
- DB local;
- FinanceGate local/batch query;
- không AI;
- không external API;
- không result upload;
- không notification synchronous.

`StartService` không được gọi LLM để quyết có Start hay không.

AI có thể:
- dự báo thời gian;
- đề xuất next action;
- cảnh báo interruption risk;

nhưng output không nằm trên hard fast path.

Target staging:

```text
simple execution command P95 < 300ms backend
```

là SLO đề xuất, phải benchmark.

---

## 28. Current-code impact

**[BÁO CÁO-CODE]**

Current `main`:
- `start_service()` đã lock visit + order;
- queue `waiting/called → serving`;
- `uq_queue_entry_one_serving` bảo vệ một người chỉ serving một chỗ;
- concurrent-start DB test đã có và chứng minh một actor thắng;
- `complete_service(performed=False)` hiện chạy **sau Start** nhưng ghi `not_performed`;
- current success event là `service.performed`, không phải `service.completed`;
- current completion có `result_note` và set `ket_qua_luc`;
- chỉ có một `performed_by`, có logic overwrite khi doctor bấm Xong;
- không có idempotency/expected version ở Start/Complete;
- không có Execution Attempt;
- external partner có shortcut sang performed;
- current tests đang khóa semantics cũ và phải đổi có chủ đích.

Đây là refactor trọng tâm, không phải rewrite queue/result/payment.

---

## 29. Tests bắt buộc

1. WAITING + all gates ready → Start creates attempt #1 + one `service.started`.
2. Same Start key retry → same attempt, no duplicate event.
3. Two actors different keys same revision → exactly one successful Start.
4. Start without SELECTED → reject.
5. Start FinanceGate DUE/PENDING/refund/review → reject.
6. Start routing stale/unassigned → reject.
7. Start while visit serving elsewhere → PATIENT_BUSY.
8. Complete active attempt → COMPLETED + one event + queue done.
9. Interrupt active attempt → INTERRUPTED + resolution responsibility.
10. Complete vs Interrupt concurrent → exactly one final outcome.
11. Late Complete attempt #1 after attempt #2 started → reject.
12. MarkNotPerformed from WAITING with no started attempt → success, no attempt row.
13. MarkNotPerformed after attempt started → reject.
14. Paid NotPerformed → no auto refund; financial-resolution responsibility exists.
15. Retry Interrupted with valid policy/routing/finance → WAITING; no attempt row until Start.
16. Start after retry → attempt_no increments.
17. Equipment interruption requiring reroute cannot restart with invalid room.
18. Result data not automatically marked ready by CompleteService.
19. `service.completed` event contains attempt identity, no unnecessary PHI.
20. Command failure rolls back order/attempt/queue/event/work item/receipt atomically.
21. Current queue live uniqueness holds across retry.
22. Batch/fast path contains no external/AI calls.

---

## 30. Chưa chốt

- Exact execution-attempt table DDL/indexes.
- Exact physical `execution_status` / `execution_revision` columns and legacy dual-write.
- Retry queue-priority policy.
- Reason → routing invalidation policy.
- Exact actor/capability matrix per service node.
- Clinical responsibility/participant data model.
- Procedure nurse vs doctor authority conflict.
- External partner execution contract.
- Service-specific completion prerequisites, if any.

---

## 31. Implementation rules cho AI

AI coding Execution v1 không được:
- giữ `performed: bool` làm API target;
- map `performed=false` sau Start thành NOT_PERFORMED;
- tạo attempt trước khi Start thực sự thành công;
- cho Complete/Interrupt chỉ target order mà không target attempt;
- auto refund khi interrupted/not-performed;
- trộn result payload vào CompleteService target contract;
- suy clinical performer từ người bấm nút;
- bypass FinanceGate/Router;
- gọi AI/external trong execution transaction;
- hard-code procedure/nurse role khi permission conflict chưa chốt;
- rewrite historical event `service.performed`.

Mọi conflict với current code phải báo trước khi sửa.

---

**Không có code, migration hoặc deploy nào được thực hiện khi tạo tài liệu này.**
