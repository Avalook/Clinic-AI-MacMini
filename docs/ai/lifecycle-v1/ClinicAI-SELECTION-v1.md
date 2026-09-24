# ClinicAI — SERVICE SELECTION v1

**Ngày:** 22/09/2026  
**Trạng thái:** Frozen core contract cho implementation; các policy được ghi OPEN vẫn không được AI tự suy.  
**Phụ thuộc:** ClinicAI-DESIGN-BASELINE-v0.2, Lifecycle Integration Checkpoint v1.  
**Không thực hiện trong tài liệu này:** code, migration, deploy.

---

## 1. Mục tiêu

Selection trả lời đúng một câu:

> Trong các chỉ định chính thức của bác sĩ mà khách đã được cho quyết định, khách hiện chọn dịch vụ nào để thực hiện?

Selection không:
- xóa chỉ định bác sĩ;
- tính tiền;
- xác nhận đã trả;
- xếp phòng;
- bắt đầu thực hiện.

Ba giá trị domain:

```text
PENDING
SELECTED
NOT_SELECTED
```

`NULL` chỉ là compatibility cho legacy/draft, không phải trạng thái domain thứ tư.

---

## 2. Migration rule

**ADD, DON'T REWRITE HISTORY.**

Không semantic-backfill dữ liệu cũ.

- historical rows: có thể giữ `selection_status = NULL`;
- official orders tạo sau cutover: `PENDING`;
- draft: `NULL`;
- chỉ real customer confirmation mới chuyển `SELECTED` / `NOT_SELECTED`;
- không suy Selection từ payment, room, queue, `exec_status`, performed/not_performed;
- không phát fake historical `service_selection.confirmed`.

---

## 3. Command

```text
ConfirmServiceSelection
```

HTTP target concept:

```http
POST /luot-kham/visits/{visit_id}/service-selection/confirm
Idempotency-Key: <required>
```

Body:

```json
{
  "order_ids_seen": ["uuid-1", "uuid-2", "uuid-3"],
  "selected_order_ids": ["uuid-1", "uuid-3"],
  "expected_selection_revision": 2
}
```

---

## 4. `order_ids_seen` — nghĩa chính xác

`order_ids_seen` là **toàn bộ tập service orders mà UI đã đưa ra cho người dùng quyết định trong snapshot Selection hiện tại**.

Nó không có nghĩa:
- tất cả order từng tồn tại trong visit;
- tất cả order đang visible read-only;
- chỉ các order được chọn.

Backend phải tính `current_decision_order_ids` theo cùng policy Selection và yêu cầu:

```text
set(order_ids_seen) == set(current_decision_order_ids)
```

Nếu không bằng:

```text
SELECTION_ORDER_SET_CHANGED
```

Mục đích: bác sĩ thêm/chỉnh order trong lúc thu ngân đang chọn thì backend không được tự biến order khách chưa từng nhìn thấy thành `NOT_SELECTED`.

Nếu UI sau này hiển thị thêm order locked/read-only, các order đó **không** nằm trong `order_ids_seen`; API/read model phải phân biệt `decision_orders` với `read_only_orders`.

---

## 5. `selected_order_ids`

`selected_order_ids` phải là subset của `order_ids_seen`.

Semantic:

```text
seen ∩ selected
→ SELECTED

seen - selected
→ NOT_SELECTED
```

Danh sách selected rỗng là hợp lệ:

```text
[]
```

→ tất cả decision orders hiện tại thành `NOT_SELECTED`.

Duplicate ID trong input bị reject; không silently dedupe.

---

## 6. Revision

Có một Selection revision theo visit.

Concept table:

```text
service_selection_state
(clinic_id, visit_id, revision, confirmed_by, confirmed_at, ...)
```

Không có row:

```text
revision = 0
```

First real change:

```text
expected 0
→ revision 1
```

Concurrent actors cùng expected revision:
- một người commit;
- người kia `SELECTION_REVISION_CONFLICT`;
- không merge ngầm.

No-op:
- trả 200;
- `changed=false`;
- revision không tăng;
- không event;
- không bump order version;
- receipt vẫn có thể lưu để retry ổn định.

---

## 7. Idempotency

`Idempotency-Key` required:
- length 8..200;
- receipt cùng DB transaction với state + event.

Canonical payload trước khi hash:

```text
visit_id
expected_selection_revision
sorted(order_ids_seen)
sorted(selected_order_ids)
```

List order không tạo business intent mới.

Same key + same payload:
- replay đúng response cũ.

Same key + different payload:
- `IDEMPOTENCY_KEY_REUSED`.

Receipt replay phải được kiểm trước stale-revision check để request thành công nhưng mất response có thể retry đúng.

---

## 8. Decision-order eligibility

Normal Selection v1 chỉ cho những official orders còn ở giai đoạn quyết định của khách.

Target policy:

- official/authorized order;
- chưa started;
- chưa terminal execution;
- chưa routing lock;
- chưa financial commitment;
- selection hiện `NULL/PENDING/SELECTED/NOT_SELECTED` theo compatibility.

Draft không phải decision order.

Legacy assigned rows không được Selection tự gỡ routing/queue; xử lý cutover/reconciliation riêng.

`NOT_SELECTED != CANCELLED`.

---

## 9. Edit locks

Simple Selection edit bị chặn nếu order đã sang concern khác.

### Financial lock
Nếu order đã có exact financial footprint / allocation đang hoặc đã có commitment thì không đổi bằng checkbox.

Trả:
```text
SELECTION_FINANCIAL_LOCKED
```

Nếu legacy payment tồn tại nhưng không thể xác định allocation order-level:
```text
SELECTION_PAYMENT_ALLOCATION_UNKNOWN
```

Không đoán.

### Routing lock
Order đã authoritative routed:
```text
SELECTION_ROUTING_LOCKED
```

### Execution lock
Order đã started / terminal:
```text
SELECTION_EXECUTION_LOCKED
```

Resolution phải đi command của Finance/Router/Execution tương ứng.

---

## 10. Transaction / lock order

```text
BEGIN
↓
lock visit
↓
transactional receipt/advisory lock + replay check
↓
lock/read selection state
↓
check expected selection revision
↓
lock service_order rows deterministic ORDER BY id
↓
validate order-by-order
↓
financial/routing/execution guards
↓
calculate new Selection
↓
bulk update changed rows
↓
increment selection revision only if real change
↓
record service_selection.confirmed only if real change
↓
store receipt
↓
COMMIT
```

Visit-first lock phải tương thích với Payment/Router/Execution.

---

## 11. Event

Chỉ phát khi state thực sự đổi:

```text
service_selection.confirmed
```

Aggregate:

```text
visit
```

Minimal payload:

```json
{
  "selection_revision": 5,
  "selected_order_ids": ["..."],
  "not_selected_order_ids": ["..."],
  "changed_order_ids": ["..."]
}
```

Không PHI/prices không cần thiết.

Không phát failure/conflict thành domain event.

---

## 12. Response

```json
{
  "ok": true,
  "visit_id": "...",
  "changed": true,
  "selection_revision": 5,
  "selected_order_ids": ["order-a", "order-c"],
  "not_selected_order_ids": ["order-b"],
  "changed_order_ids": ["order-b", "order-c"],
  "order_versions": {
    "order-a": 3,
    "order-b": 4,
    "order-c": 2
  },
  "confirmed_at": "...",
  "confirmed_by": "staff-uuid"
}
```

No-op:
- same shape;
- `changed=false`;
- `changed_order_ids=[]`;
- revision unchanged.

Không trả bill, room recommendation hay AI output trong response này.

---

## 13. Stable errors

```text
IDEMPOTENCY_KEY_REQUIRED
IDEMPOTENCY_KEY_REUSED

SELECTION_DUPLICATE_ORDER_ID
SELECTION_SELECTED_NOT_IN_SEEN
SELECTION_REVISION_CONFLICT
SELECTION_ORDER_SET_CHANGED

SELECTION_FINANCIAL_LOCKED
SELECTION_PAYMENT_ALLOCATION_UNKNOWN
SELECTION_ROUTING_LOCKED
SELECTION_EXECUTION_LOCKED

NO_SELECTABLE_ORDERS
VISIT_INCOMPLETE
VISIT_CLOSED
```

Tenant/not-found/permission errors giữ convention chung của API.

---

## 14. Permission

Business capability target:

```text
service.selection.confirm
```

Router outer guard + service inner capability check.

**OPEN:** exact role → capability mapping.

Implementation không được tự hard-code role cuối cùng khi chưa có permission checkpoint.

---

## 15. Frontend retry rule

Một click / một business intent:
- tạo một idempotency key;
- giữ key cho tới khi request có kết quả xác định.

Timeout/network unknown:
```text
retry SAME key
```

User refresh/change Selection sau explicit conflict:
```text
new intent → new key
```

Không tạo idempotency key mới cho mỗi HTTP retry của cùng intent.

---

## 16. Acceptance tests

1. PENDING/PENDING → SELECTED/NOT_SELECTED, rev0→1, one event.
2. same key retry → same response, no duplicate revision/event.
3. same key different payload → `IDEMPOTENCY_KEY_REUSED`.
4. concurrent same revision → one succeeds, one revision conflict.
5. doctor adds order after UI snapshot → `SELECTION_ORDER_SET_CHANGED`; unseen order untouched.
6. SELECTED→NOT_SELECTED before financial/routing/execution lock succeeds.
7. financial commitment → blocked.
8. legacy paid visit without exact allocation → allocation unknown.
9. routed order → blocked.
10. started/terminal order → blocked.
11. same state + new key → no-op, no revision/event increment.
12. empty selected list valid.
13. order ID from another visit/clinic never modified.
14. failure after update before receipt → full rollback.
15. Selection vs Payment concurrent requests serialize by visit lock.
16. canonical list ordering gives same payload hash/business intent.
17. max batch limit enforced without N+1.

---

## 17. OPEN / cutover

Still open:
- exact role mapping;
- exact handling of active legacy `assigned + selection NULL`;
- exact cutover UI wording for legacy rows;
- final finance-resolution policy after commitment.

These OPEN items must not cause semantic backfill or silent inference.

---

## 18. Implementation rules for AI

AI must not:
- infer historical Selection;
- delete physician orders for `NOT_SELECTED`;
- mutate payment/routing/execution to make Selection succeed;
- silently dedupe duplicate IDs;
- auto-select newly added unseen orders;
- use list order as a different business intent;
- generate new idempotency key on network retry;
- hard-code final role mapping;
- treat legacy NULL as `NOT_SELECTED`.

Any contract/code conflict must be reported, not guessed.

---

**Không có code, migration hoặc deploy nào được thực hiện khi tạo tài liệu này.**
