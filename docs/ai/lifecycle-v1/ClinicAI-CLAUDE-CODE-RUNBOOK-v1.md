# ClinicAI — CLAUDE CODE RUNBOOK v1

**Mục tiêu:** triển khai Service Lifecycle v1 đúng contract, ít token, ít re-audit, có test gate rõ.  
**Dùng cho:** Claude Code / coding agent trên repo local.  
**Không phải lệnh đã chạy.**

---

# 1. Nguyên tắc tiết kiệm token

Claude không cần đọc lại toàn bộ lịch sử chat.

Cho Claude một lần các file contract:

```text
ClinicAI-CONTEXT-v1.0.md
ClinicAI-LIFECYCLE-INTEGRATION-CHECKPOINT-v1.md
ClinicAI-FINANCE-GATE-v1.md
ClinicAI-ROUTING-v1.md
ClinicAI-EXECUTION-v1.md
```

Selection contract nếu đóng riêng thì thêm file đó; nếu chưa có file riêng, dùng baseline v0.2 + checkpoint.

Sau bootstrap, mỗi slice chỉ yêu cầu đọc:
- master checkpoint;
- spec module liên quan;
- 3–6 file code liên quan;
- test file liên quan.

Không paste lại contract vào mỗi prompt.

Agent phải search **symbol/call-site cụ thể**, không scan toàn repo mỗi lượt.

---

# 2. Prompt bootstrap ngắn

```text
Bạn implement ClinicAI Service Lifecycle v1.

Nguồn quyết định:
1. ClinicAI-LIFECYCLE-INTEGRATION-CHECKPOINT-v1.md
2. module spec tương ứng
3. ClinicAI-DESIGN-BASELINE-v0.2.md
4. current code chỉ là hiện trạng, không tự đúng.

Quy tắc:
- không tự đổi nghiệp vụ;
- nếu contract mâu thuẫn code, làm theo contract và báo impact;
- nếu contract tự mâu thuẫn hoặc chạm OPEN policy, STOP và báo BLOCKER, không đoán;
- additive migration, không rewrite history;
- không deploy;
- không sửa ngoài slice;
- core command state + event + receipt cùng transaction;
- visit-first lock;
- không AI/external API trên fast path;
- sau mỗi slice chạy test được chỉ định và đưa diff summary <=20 dòng.

Không giải thích dài. Đọc file được chỉ định rồi làm trực tiếp.
```

---

# 3. Definition of Done cho một ngày coding

Mục tiêu một ngày hợp lý nhất:

```text
một branch implementation hoàn chỉnh cho lifecycle slice
+ migrations additive
+ backend/API/frontend compatibility tối thiểu
+ targeted DB tests xanh
+ finance/refund regression xanh
+ lifecycle integration tests xanh
+ diff/audit cuối
```

Không coi một ngày là đủ để tự động khẳng định production-safe nếu chưa staging/UAT.

Nếu thiếu thời gian, **không cắt test/idempotency/concurrency**. Cắt UI polish, AI advisor, optional refactor trước.

---

# 4. Thứ tự slice bắt buộc

## Slice 0 — Baseline & guardrail

Chỉ đọc/xác minh:
- branch + HEAD;
- working tree;
- migration head;
- test baseline liên quan.

Chạy baseline targeted tests trước khi sửa.

Output:
```text
BASELINE GREEN
```
hoặc danh sách failure có sẵn.

Không sửa business code ở Slice 0.

---

## Slice 1 — Additive schema foundation

Mục tiêu:
- `selection_status`;
- selection revision state;
- routing state/revision;
- execution revision/state compatibility cần thiết;
- `service_execution_attempt`;
- multi-cycle service payment index/constraint thay đổi;
- DB guards cần thiết.

Quy tắc:
- không semantic-backfill Selection;
- không rewrite historical migrations;
- forward migration mới;
- legacy rows giữ unknown/null theo contract;
- chưa đổi UI.

Tests:
- migration applies on clean test DB;
- legacy representative rows survive;
- constraints;
- tenant/FK;
- attempt uniqueness;
- multi-cycle paid services allowed;
- duplicate live pending service cycle blocked.

Commit/checkpoint riêng.

---

## Slice 2 — Selection

Files trọng tâm:
```text
luot_kham_service.py / service lifecycle package
luot_kham router
dashboard proxy/API
cashier UI
```

Implement:
- `ConfirmServiceSelection`;
- visit-level revision;
- `order_ids_seen`;
- transactional receipt;
- no-op behavior;
- financial/routing/execution edit locks.

Không implement payment trong slice này.

Tests bắt buộc:
- first confirm;
- stale revision;
- doctor adds order race;
- same-key replay;
- key reused with different payload;
- two-actor conflict;
- paid/routed/start lock;
- no-op no event/revision increment.

---

## Slice 3 — Outstanding Bill + Multi-cycle Payment + FinanceGate

Đây là slice tài chính, không chia nhỏ giữa nhiều agent đồng thời.

Implement:
- bill only selected + lifecycle-chargeable + outstanding lines;
- exam line coverage;
- multiple PAID `dich_vu` cycles;
- one pending verification cycle;
- line-level duplicate coverage guard;
- payment transactional receipt;
- FinanceGate batch derivation;
- current `payment` compatibility projection only;
- keep refund ledger semantics.

Không sửa refund business policy chưa chốt.

Tests bắt buộc:
- SA paid, add XN, second cycle charges only XN;
- exam not charged twice;
- two collectors concurrency;
- retry payment after lost response;
- pending QR blocks second collection;
- cancel pending allows DUE again;
- VOIDED does not auto DUE;
- refund pending/full/partial derivation;
- current finance/refund regression suite.

**Không được bỏ các test tài chính cũ chỉ vì contract mới. Chỉ sửa assertion nào thật sự bị business contract thay thế và ghi lý do.**

---

## Slice 4 — Routing

Implement:
- `AssignServiceRoom`;
- routing revision;
- recommendation separated from assignment;
- preserve queue age on reroute;
- invalidation → reassignment responsibility;
- rule-based advisor extracted from current `_tu_xep_phong`;
- no LLM.

OPEN policies:
- vitals;
- exact role mapping;
- staff-on-shift hard/soft.

Đặt sau policy seam/compatibility; không tự chốt.

Tests:
- assign;
- stale revision;
- same-room no-op;
- reroute keeps wait age;
- invalid room;
- invalidation;
- AI/recommendation stale room cannot bypass command;
- no N+1 candidate query.

---

## Slice 5 — Execution Attempt

Implement:
- StartService attempt creation;
- CompleteService;
- MarkServiceNotPerformed;
- InterruptService;
- CancelService;
- PrepareServiceRetry;
- transactional receipt;
- attempt-targeted Complete/Interrupt;
- result decoupling.

Tests:
- concurrent Start exactly one winner;
- same-key retry same attempt;
- complete vs interrupt race;
- late command for old attempt;
- NotPerformed only pre-start;
- interrupted retry produces new attempt;
- paid cancel/notperformed/interrupted do not auto-refund;
- queue state/block/release;
- event names.

---

## Slice 6 — Compatibility readers + integration rail

Update only necessary readers:
- cashier board;
- service room;
- checkout/readiness;
- review requirements;
- timeline/event adapter;
- dashboard API/proxy.

Do not rewrite all screens.

Golden integration tests:
```text
Order
→ Select
→ Pay #1
→ Route
→ Start attempt #1
→ Complete

Add second order
→ Select
→ Pay #2
→ Route
→ Start
→ Complete
```

Failure rail:
```text
Select
→ Pay
→ Route
→ Start
→ Interrupt
→ reroute
→ PrepareRetry
→ Start attempt #2
→ Complete
```

Cancellation rail:
```text
Select
→ Pay
→ Cancel before Start
→ financial responsibility exists
→ no auto refund
```

---

# 5. Test gate — không thương lượng để tiết kiệm thời gian

Mỗi slice:
1. targeted new tests;
2. directly affected regression tests;
3. no known new failure.

Cuối sprint:
- all lifecycle service DB tests;
- all payment/finance/refund tests;
- API tests affected;
- frontend typecheck/tests for touched screens;
- migration test/rehearsal;
- ideally full backend suite nếu thời gian cho phép.

Không dùng:
```text
"tests chắc ổn"
"chỉ lint"
"manual smoke thay concurrency test"
```

Concurrency/idempotency phải có DB integration test.

---

# 6. Test files hiện biết là quan trọng

Ít nhất:
```text
src/tests/services/test_luot_kham_service_db.py
src/tests/services/test_slice1_rail_db.py
src/tests/services/test_dich_vu_rail_moi_db.py
src/tests/test_payment_service.py
```

Ngoài ra agent phải discover và chạy toàn bộ test có pattern:
```text
tien_thuoc
payment
refund / hoan
checkout
cashier
service_order
```

Không đoán tên file; dùng repo search một lần.

---

# 7. Cách dùng Claude ít token

Sau bootstrap, prompt slice có format cố định:

```text
SLICE N.

Đọc:
- <1 master spec>
- <1 module spec>
- <các file code cụ thể>
- <test file cụ thể>

Làm đúng checklist:
1...
2...
3...

Không làm:
- ngoài slice
- refactor thẩm mỹ
- rename diện rộng
- docs dài
- AI/external

Nếu BLOCKER do OPEN policy: dừng trước chỗ đó, hoàn thành phần độc lập, báo đúng 1 blocker.

Chạy:
<target tests>

Trả:
- files changed
- migrations
- tests run/result
- blockers
- next slice
<=20 dòng.
```

Không hỏi Claude “hãy phân tích toàn hệ thống” ở mỗi turn.

---

# 8. Token budget tactics

Ưu tiên:
- exact file paths;
- exact symbols/method names;
- exact acceptance tests;
- one slice/turn;
- reuse previous working tree context;
- commit after slice để diff nhỏ.

Tránh:
- paste 4.000 dòng service;
- paste toàn bộ chat;
- yêu cầu "audit toàn repo" lặp lại;
- yêu cầu 3 phương án trước khi code khi contract đã frozen;
- giải thích kiến trúc dài sau mỗi edit.

Nếu agent bắt đầu lan scope:
```text
STOP. Chỉ implement checklist của slice. Báo dependency thay vì sửa dependency.
```

---

# 9. Không dùng nhiều coding agent song song trên cùng invariant

Có thể song song các việc độc lập:
- frontend view;
- pure unit tests;
- docs.

Không song song writer trên:
- payment ledger;
- lifecycle migration;
- execution attempt;
- queue/routing state.

Các vùng này dễ tạo hai source of truth hoặc migration xung đột.

---

# 10. Review gate sau mỗi slice

Yêu cầu agent tự trả:

```text
1. Contract clauses implemented
2. Contract clauses intentionally deferred
3. Schema/state/event changed
4. Old behavior removed or compatibility-kept
5. Tests proving concurrency/idempotency
6. Any reader still depending on old exec_status/payment assumption
```

Nếu câu 6 còn reader critical, chưa sang production.

---

# 11. Một-ngày ưu tiên

Nếu hết thời gian, thứ tự không được hy sinh:

```text
Correct DB invariants
> transactional idempotency
> financial correctness
> execution concurrency
> integration tests
> compatibility readers
> UI polish
> AI recommendation
```

AI recommendation thật để sau. Rule advisor + command seam là đủ cho lifecycle v1.

---

# 12. Những blocker không để Claude tự quyết

```text
vitals hard routing gate?
exact role/capability matrix?
procedure nurse clinical authority?
external partner payment/execution?
retry queue priority?
partial service refund?
direct-arrival service-order creation?
```

Agent phải đưa `BLOCKER` thay vì chọn hộ.

---

# 13. Trạng thái kết thúc coding sprint

Một sprint tốt phải trả được:

```text
commit/SHA
working tree
migrations added
tests run + counts
known skipped/open policies
old readers remaining
rollback/rehearsal notes
```

Không chấp nhận câu:
```text
"implementation complete"
```
nếu không kèm test evidence.

---

**Tài liệu này là runbook; chưa có code/migration/deploy nào được thực hiện khi tạo nó.**
