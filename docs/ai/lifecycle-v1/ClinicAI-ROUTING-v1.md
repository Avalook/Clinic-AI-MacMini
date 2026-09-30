# ClinicAI — ROUTING v1

**Ngày:** 22/09/2026  
**Trạng thái:** Contract thiết kế để Tuyền chốt trước implementation. Không phải schema/code đã triển khai.  
**Phụ thuộc:** Service Lifecycle v1, Service Selection v1, FinanceGate v1, Extension Architecture v0.1.  
**Không thực hiện trong tài liệu này:** code, migration, test, deploy.

---

## 1. Mục tiêu

Routing trả lời hai câu khác nhau:

```text
Recommendation
= nên đưa order tới phòng nào?

Assignment
= phòng nào đang là quyết định chính thức?
```

Hai khái niệm không được nhập làm một.

Đường chuẩn:

```text
Eligible Rooms
     ↓
Room Advisor / AI
     ↓
Recommendation
     ↓
Human hoặc policy
     ↓
AssignServiceRoom
     ↓
Backend revalidate
     ↓
Routing State + Queue + Domain Event
```

AI/rule engine không UPDATE `service_order` hoặc `queue_entry` trực tiếp.

---

## 2. State model

Routing v1 dùng:

```text
UNASSIGNED
ASSIGNED
REASSIGNMENT_REQUIRED
```

### `UNASSIGNED`
Chưa có room assignment hợp lệ.

### `ASSIGNED`
Có room assignment hiện hành và room vẫn hợp lệ.

### `REASSIGNMENT_REQUIRED`
Assignment trước đã mất hiệu lực trước khi execution bắt đầu; cần quyết định phòng mới.

Current room authoritative:

```text
ASSIGNED
→ room_id != NULL

UNASSIGNED / REASSIGNMENT_REQUIRED
→ room_id = NULL
```

Room cũ khi invalidated được giữ trong event/history, không để `room_id` tiếp tục trỏ tới một assignment đã vô hiệu.

---

## 3. Revision

Mỗi `service_order` có concept:

```text
routing_revision
```

Khởi đầu:

```text
0
```

Ví dụ:

```text
rev 0: UNASSIGNED
rev 1: null → SA1
rev 2: SA1 → SA2
rev 3: SA2 invalidated
rev 4: null → SA3
```

Revision tăng khi **authoritative routing state thực sự đổi**.

Bấm lại cùng phòng, không đổi state:

```text
changed = false
routing_revision không tăng
không phát service.routed mới
```

---

## 4. `AssignServiceRoom` command

Semantic:

```text
AssignServiceRoom
```

Một command dùng chung cho:
- initial assignment;
- manual reroute;
- accept rule-engine recommendation;
- accept AI recommendation;
- future auto-routing.

Không tạo các command riêng:

```text
SecretaryAssignRoom
NurseAssignRoom
AIAssignRoom
AutoAssignRoom
```

### Input concept

```text
service_order_id
room_id
expected_routing_revision
reason_code
recommendation_ref optional
idempotency_key
```

Reason codes đề xuất:

```text
INITIAL_ASSIGNMENT
LOAD_BALANCE
ROOM_UNAVAILABLE
STAFF_UNAVAILABLE
EQUIPMENT_FAILURE
PATIENT_NEED
MANUAL_CORRECTION
OTHER
```

`OTHER` cần note nếu sau này expose cho người dùng.

`recommendation_ref` chỉ phục vụ trace/harness; không làm recommendation thành authoritative state.

---

## 5. Preconditions của `AssignServiceRoom`

Backend phải đọc lại authoritative state trong transaction.

### Hard gates đã có từ design hiện hành

Order:
- thuộc đúng clinic;
- là official service order;
- `selection_status = SELECTED`;
- FinanceGate trả `financially_ready = true`;
- execution chưa `IN_PROGRESS` và chưa terminal;
- routing revision đúng expected revision.

Room:
- thuộc đúng clinic;
- active;
- accepting;
- `clinic_room_node` cho biết room phục vụ đúng `node_code`.

Actor:
- có capability `service.route.assign`.

### Clinical/operational hold

Một order có hold chuyên môn/vòng đọc chưa đủ điều kiện thì không được route.

Exact rule phải dùng một policy có tên rõ, không rải `if` trong command.

### Vitals conflict — CHƯA ĐƯỢC TỰ GIẢI QUYẾT

Code hiện tại `dispatch_block()` bắt `VITALS_REQUIRED`.

Khảo sát phòng khám mới lại nói sinh hiệu không phải gate cứng.

Do hai nguồn khác nhau, Routing v1 **không tự chốt** quy tắc này. Trước implementation phải có quyết định PM/phòng khám:

```text
vitals là hard routing gate?
YES / NO
```

Không được giữ code cũ chỉ vì nó đang tồn tại, và cũng không được xoá gate chỉ vì thiết kế mới thuận hơn.

---

## 6. Những thứ KHÔNG phải hard room eligibility ở v1 nếu chưa có policy

Current auto-router ưu tiên room có roster nhưng vẫn có thể chọn room không có roster nếu không còn lựa chọn tốt hơn.

Vì chưa có nguồn chốt rằng "room bắt buộc phải có staff capable on-shift mới được assignment", v1 tách:

```text
HARD ELIGIBILITY
- room active
- accepting
- serves node
- same clinic

RECOMMENDATION SIGNAL
- capable staff on shift
- queue load
- capacity
- equipment state
- patient constraints
```

Nếu sau này clinic chốt staff-on-shift là hard invariant thì đưa vào `RoutingEligibilityPolicy`, không sửa advisor tùy tiện.

---

## 7. Transaction / lock order

Đề xuất thứ tự cố định:

```text
VISIT
  ↓
IDEMPOTENCY RECEIPT
  ↓
SERVICE_ORDER
  ↓
ROUTING REVISION CHECK
  ↓
SELECTION + FINANCE + HOLD CHECKS
  ↓
TARGET ROOM VALIDATION
  ↓
QUEUE ROW
  ↓
UPDATE ROUTING STATE
  ↓
DOMAIN EVENT
  ↓
COMMAND RECEIPT
  ↓
COMMIT
```

Giữ visit-first lock để đồng bộ với Selection/Payment và tránh các command cùng visit quan sát state nửa chừng.

Idempotency receipt phải nằm cùng transaction với routing state + queue + event.

---

## 8. Queue semantics

Assignment chính thức đồng nghĩa service được đưa vào operational room queue.

Queue state vẫn là concern riêng:

```text
waiting
blocked
called
serving
...
```

Routing không tạo một queue-state vocabulary mới.

### Initial assignment

Nếu visit không đang được phục vụ nơi khác:

```text
queue.status = waiting
```

Nếu visit đang ở một chỗ khác:

```text
queue.status = blocked
```

### Reroute trước Start

Reroute phải:
- chỉ có một live SERVICE queue entry cho order;
- đổi room atomically với routing state;
- **không làm mất tuổi chờ của khách**.

Invariant:

> chuyển SA1 → SA2 không được biến người đã chờ 20 phút thành người vừa mới vào hàng.

Exact DB implementation có thể update live row hoặc recreate với preserved `eligible_at`; contract chỉ chốt kết quả này.

### Sau `IN_PROGRESS`

Normal reroute bị từ chối.

Nếu phòng/máy có sự cố sau Start:

```text
InterruptService
```

rồi resolution/retry attempt mới; không dùng `AssignServiceRoom` như thể service chưa bắt đầu.

---

## 9. Reroute

Cùng `AssignServiceRoom`.

### Proactive reroute

SA1 vẫn hợp lệ nhưng điều dưỡng chuyển sang SA2 vì tải:

```text
ASSIGNED(SA1)
→ ASSIGNED(SA2)
```

- revision tăng;
- queue room đổi;
- giữ queue age;
- phát `service.routed`.

Không cần `service.rerouted`.

### Reassignment sau invalidation

```text
REASSIGNMENT_REQUIRED
→ ASSIGNED(SA2)
```

- revision tăng;
- tạo/cập nhật queue;
- đóng trách nhiệm điều phối lại;
- phát `service.routed`.

---

## 10. `InvalidateServiceRouting`

Assignment có thể mất hiệu lực trước Start.

Semantic command:

```text
InvalidateServiceRouting
```

Ví dụ reason:

```text
ROOM_UNAVAILABLE
STAFF_UNAVAILABLE
EQUIPMENT_FAILURE
CONFIG_CHANGED
OTHER
```

Preconditions:
- routing hiện `ASSIGNED`;
- execution chưa `IN_PROGRESS`;
- actor/system có capability phù hợp;
- expected routing revision đúng nếu command nhắm một order.

Effect atomic:

```text
routing_status = REASSIGNMENT_REQUIRED
room_id = NULL
routing_revision += 1
old room queue không còn actionable
create/activate reroute responsibility
service.routing_invalidated
```

Event giữ `from_room_id`.

Không dùng invalidation sau Start; khi đó dùng execution interruption.

---

## 11. Room outage / config change fan-out

Khi một room chuyển:

```text
accepting = false
```

hoặc bị deactivate / equipment outage,

mọi assignment chưa Start tới room đó phải được xét invalidation.

Không được:
- chỉ tắt room config rồi để queue cũ tiếp tục gọi khách;
- dựa hoàn toàn vào consumer async nếu điều đó làm core state sai.

Exact batch implementation chưa chốt, nhưng contract yêu cầu:

```text
room unavailable
→ affected pre-start assignments become non-actionable
→ each unresolved order có operational responsibility
```

Có thể làm batch command trong cùng operational transaction/process.

---

## 12. Work Item / ownership

Nếu invalidation xảy ra mà chưa có room mới ngay:

```text
REASSIGNMENT_REQUIRED
```

phải xuất hiện thành một trách nhiệm vận hành rõ.

Concept:

```text
"Điều phối lại dịch vụ X"
required capability = service.route.assign
```

Không để order nằm im chỉ vì event đã phát.

Exact `work_item` schema/payload/owner mapping dùng hạ tầng hiện có sau impact mapping.

---

## 13. Domain Events

### Official assignment

```text
service.routed
```

Aggregate đề xuất:

```text
aggregate_type = service_order
aggregate_id = service_order_id
```

Payload tối thiểu:

```json
{
  "visit_id": "...",
  "from_room_id": "...",
  "to_room_id": "...",
  "routing_revision": 4,
  "reason_code": "LOAD_BALANCE",
  "recommendation_ref": "optional"
}
```

### Invalidation

```text
service.routing_invalidated
```

Payload:

```json
{
  "visit_id": "...",
  "from_room_id": "...",
  "routing_revision": 3,
  "reason_code": "EQUIPMENT_FAILURE"
}
```

Không phát canonical Domain Event khi AI chỉ thay đổi recommendation.

---

## 14. Recommendation contract

Recommendation không thay business state.

Concept:

```text
RoomAdvisor.recommend(context) -> ranked candidates
```

Backend trước hết dựng **eligible-room set**.

Advisor chỉ được xếp hạng trong tập này.

AI không được tự sáng tạo room ID ngoài tập eligible.

### Input tối thiểu

```text
service_order_id
node_code
eligible_rooms[]
queue/load summary
capacity
staff availability signal
equipment/room operational signal
patient constraints cần thiết
context version / generated_at
```

Không mặc định gửi toàn bệnh án.

### Output

```json
{
  "advisor": "rule-v1",
  "generated_at": "...",
  "candidates": [
    {
      "room_id": "...",
      "rank": 1,
      "reason_codes": ["LOW_QUEUE", "CAPABLE_STAFF_ON_SHIFT"],
      "confidence": null
    }
  ]
}
```

`confidence` optional; rule engine không cần bịa confidence.

---

## 15. Rule-based advisor trước, AI advisor sau

Code hiện tại `_tu_xep_phong()` đã có hạt giống advisor:
- room serves node;
- active/accepting;
- ưu tiên room có roster;
- ưu tiên queue ngắn.

Target không vứt logic này.

Tách thành:

```text
EligibleRoomQuery
        ↓
RuleBasedRoomAdvisor
```

thay vì:

```text
authorize order
→ _tu_xep_phong()
→ tự ghi room
```

Sau này thêm:

```text
AIRoomAdvisor
```

mà không đổi `AssignServiceRoom`.

---

## 16. AI / auto-routing

### Mặc định

AI có capability:

```text
service.route.recommend
```

AI chỉ tạo recommendation.

### Future autonomous mode

Nếu clinic/policy cho phép auto-route một scope cụ thể, service principal/AI agent được cấp:

```text
service.route.assign
```

và vẫn gọi:

```text
AssignServiceRoom
```

Không có privileged DB write path.

Command vẫn revalidate:
- Selection;
- FinanceGate;
- room eligibility;
- routing revision;
- execution state.

### Decision trace

Nếu assignment bắt nguồn từ recommendation, lưu trace đủ cho harness:

```text
advisor/model/version
recommendation_ref
recommended room
selected room
accepted/overridden
actor
command/event ref
latency
```

Không cần private chain-of-thought.

Không tạo staff giả để đại diện AI. Exact system/AI principal persistence chưa chốt; current human `assigned_by` field vẫn dùng trong giai đoạn human-routing.

---

## 17. Permission model

Contract capability:

```text
service.route.recommend
service.route.assign
service.route.invalidate
```

Yêu cầu thực tế mới nói thư ký hoặc điều dưỡng có thể điều phối theo tải, không cần trưởng ca cho mọi lần.

Code hiện tại lại chỉ cho:

```text
TRUONG_CA
MANAGEMENT
```

ở `dispatch_order`.

Vì vậy đây là code gap thật.

Exact account-role → capability mapping vẫn cần chốt:
- `TKYK`?
- `NURSE_ULTRASOUND`?
- `RECEPTION`?
- `TRUONG_CA` / `MANAGEMENT` override?

Không hard-code role mới vào RoutingService trước permission checkpoint.

---

## 18. Error codes

Đề xuất stable errors:

```text
ROUTING_REVISION_CONFLICT
SERVICE_NOT_SELECTED
SERVICE_FINANCE_NOT_READY
SERVICE_ROUTING_NOT_ALLOWED
SERVICE_ALREADY_IN_PROGRESS
SERVICE_EXECUTION_TERMINAL

ROOM_NOT_FOUND
ROOM_INACTIVE
ROOM_NOT_ACCEPTING
ROOM_NOT_SERVING_SERVICE

ROUTING_ALREADY_INVALIDATED
ROUTING_NOT_ASSIGNED

ROUTING_PERMISSION_DENIED
IDEMPOTENCY_KEY_REUSED
```

`FinanceGate` giữ reason chi tiết của nó; Routing có thể trả kèm finance reason thay vì copy logic.

---

## 19. Response contract

Success:

```json
{
  "ok": true,
  "order_id": "...",
  "changed": true,
  "routing_status": "ASSIGNED",
  "room_id": "...",
  "routing_revision": 4,
  "queue_status": "waiting",
  "recommendation_ref": "optional"
}
```

No-op cùng room:

```json
{
  "ok": true,
  "order_id": "...",
  "changed": false,
  "routing_status": "ASSIGNED",
  "room_id": "...",
  "routing_revision": 4,
  "queue_status": "waiting"
}
```

Không tăng revision/event ở no-op.

---

## 20. Performance

`AssignServiceRoom` là core fast path:
- DB local only;
- không gọi AI;
- không gọi external API;
- không synchronous fan-out.

Recommendation:
- rule advisor có thể chạy local nhanh;
- AI advisor nên precompute/async khi có thể;
- UI không chờ AI để thao tác tay.

Candidate-room query phải batch queue/load trong một query/read model; không loop từng room gọi DB.

Nếu AI down:

```text
manual room assignment vẫn hoạt động
rule-based recommendation vẫn có thể hoạt động
```

---

## 21. Current-code impact

**[BÁO CÁO-CODE]**

Current committed `main`:
- `dispatch_order()` đã có visit lock, expected version, idempotency receipt;
- `_gan_phong()` kiểm room active/accepting + `clinic_room_node`;
- reroute trước `called/serving` đã có;
- queue live uniqueness đã có;
- `_tu_xep_phong()` đang vừa recommend vừa authoritative assign;
- event hiện là `dispatch.assigned` aggregate `visit`;
- dispatch permission hiện `TRUONG_CA/MANAGEMENT`;
- `dispatch_block()` vẫn có `VITALS_REQUIRED`;
- `clinic_room_node`, `staff_node`, roster và room config là nền tốt để build advisor.

Do đó implementation target là tách responsibility, không rewrite queue/config.

---

## 22. Tests bắt buộc

1. Initial assignment eligible → ASSIGNED + queue + one `service.routed`.
2. Retry cùng idempotency key → replay, không duplicate queue/event/revision.
3. Same room với key mới → changed=false.
4. Two actors same routing revision → một thắng, một revision conflict.
5. Room không serve node → reject.
6. Room inactive/accepting=false → reject.
7. SELECTED nhưng finance chưa ready → reject.
8. NOT_SELECTED → reject.
9. Reroute SA1→SA2 trước Start → success, queue age preserved.
10. Reroute sau called/serving/IN_PROGRESS → reject theo execution/routing rule.
11. Invalidate assigned pre-start → REASSIGNMENT_REQUIRED + no actionable old-room queue + event + responsibility.
12. Reassign after invalidation → ASSIGNED new room + revision mới.
13. AI recommendation room đã stale/inactive trước click → command revalidate và reject; recommendation không bypass.
14. Advisor chỉ rank eligible room set.
15. AI unavailable → manual AssignServiceRoom vẫn chạy.
16. Batch room candidates không N+1.
17. Assignment event payload không chứa PHI không cần thiết.
18. Current wait age không reset khi reroute.

---

## 23. Chưa chốt

- Vitals có còn là hard routing gate hay không — nguồn đang mâu thuẫn.
- Exact role/capability matrix.
- Staff-on-shift là hard eligibility hay chỉ recommendation factor.
- Exact schema fields cho `routing_status` / `routing_revision`.
- Exact queue-row strategy khi invalidation để vừa non-actionable vừa giữ wait age.
- Persistence model cho AI/system actor khi future auto-routing.
- External-partner routing/payment contract.

---

## 24. Implementation rules cho AI

AI coding Routing v1 không được:
- cho advisor ghi DB;
- tạo một auto-route API riêng bypass command;
- hard-code room theo service name;
- hard-code role mới khi permission chưa chốt;
- reset queue age khi reroute;
- dùng `exec_status` làm routing state dài hạn;
- giữ `VITALS_REQUIRED` hay xoá nó mà không báo source conflict;
- tạo event cho mỗi lần recommendation refresh;
- gọi LLM trong `AssignServiceRoom`;
- query từng room trong loop.

Mọi conflict với current code phải được report trước khi sửa.

---

**Không có code, migration hoặc deploy nào được thực hiện khi tạo tài liệu này.**
