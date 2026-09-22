# ClinicAI — IMPACT AUDIT: code hiện tại ↔ DESIGN BASELINE v0.2

**Ngày audit:** 22/09/2026  
**Repo:** `Avalook/Clinic-AI-MacMini`  
**Branch audited trên GitHub:** `codex/auto-lot-from-main`  
**HEAD committed audited:** `0209df61a5b97906cb2d3f6b54e170ead3c13ae9`  
**Baseline đích:** `ClinicAI-DESIGN-BASELINE-v0.2.md` — Service Lifecycle v1 frozen ở mức domain contract.

## 0. Giới hạn và độ tin cậy

Audit này là **static read-only audit trên code đã commit ở GitHub**. Không chạy code, không chạy test, không migration, không deploy, không sửa repo.

Night Shift trước đó báo local working tree trên cùng branch/HEAD đang **DIRTY**. GitHub không thấy local uncommitted files/modifications, nên:
- phần dưới là sự thật về **remote committed code @ `0209df61…`**;
- bất kỳ local dirty change nào trên Mac Mini vẫn **chưa xác minh**;
- không được nói “runtime/staging/prod đang đúng y như report này” nếu chưa chạy/đo.

Audit tập trung **toàn bộ lát cắt Service Lifecycle v1** và các dependency trực tiếp:
- service_order schema;
- order/authorize;
- selection;
- billing/payment/refund;
- routing/queue/room;
- service start/complete/fail;
- result seam;
- checkout/readiness;
- frontend của bác sĩ/phòng dịch vụ/thu ngân;
- command proxy/idempotency;
- test contracts khóa hành vi hiện tại;
- legacy order/dispatch rail có thể gây nhầm khi refactor.

Không audit lại các domain không trực tiếp liên quan như booking source, PDF, pharmacy dose, pelvic-floor form.

---

# 1. Kết luận tổng thể

## Verdict

**Không cần rewrite ClinicAI.**  
Nhưng **Service Lifecycle v1 là thay đổi domain đáng kể**, không phải đổi vài label.

Code hiện tại đã có nhiều nền rất tốt để tái sử dụng:

- `service_order` theo từng dịch vụ;
- room/node config;
- queue per service;
- reroute trước lúc đang phục vụ;
- `version` trên `service_order`;
- `command_receipt` + pattern idempotency ở một số command;
- transactional `record_event`;
- `payment_cycle` immutable-ish ledger;
- `payment_bill_line` snapshot theo từng line, có `source_type/source_id`;
- refund theo đúng bill line;
- work-item OCC/dependency/role-gate;
- một frontend proxy tập trung cho luồng `luot-kham`.

Nhưng target v0.2 khác current model ở **5 trục cốt lõi**:

1. code hiện tại dùng **một `exec_status`** để trộn authorization/routing/execution;
2. bác sĩ authorize xong hiện **tự xếp phòng ngay**, chưa có customer selection;
3. thanh toán dịch vụ hiện **chỉ cho sau “khám xong”**, ngược flow mới;
4. `StartService` hiện **không kiểm selection/payment**, chưa có expected version/idempotency/attempt;
5. service đã start rồi “không làm được” hiện bị ghi thành `not_performed`, trong khi v0.2 cần `INTERRUPTED`.

**Mức tác động:** MEDIUM-HIGH ở core service flow, nhưng **localized**, không phải toàn repo.

---

# 2. Gap map theo domain contract v0.2

| Contract v0.2 | Code hiện tại | Kết luận |
|---|---|---|
| `ordered != selected` | `authorize_orders()` tạo/authorize rồi `_tu_xep_phong()` ngay | **GAP HIGH** |
| Selection state + revision | Không có selection axis/revision trong `service_order` | **MISSING** |
| Payment trước execution | Payment bị gate bởi `kham_xong` | **CONFLICT HIGH** |
| Payment allocation tới service | `payment_bill_line.source_type/source_id` đã snapshot từng service | **PHẦN LỚN TÁI DÙNG ĐƯỢC** |
| Refund immutable | `payment_refund` + line đã làm khá đúng | **TÁI DÙNG MẠNH** |
| Routing actor TKYK/Nurse | `dispatch_order` chỉ `TRUONG_CA/MANAGEMENT` | **CONFLICT** |
| Routing revision | chỉ `room_id`, assigned_by/at, version chung | **MISSING** |
| `REASSIGNMENT_REQUIRED` | chưa có | **MISSING** |
| reroute trước start | `_gan_phong()` đã cho đổi room nếu queue chưa called/serving | **TÁI DÙNG** |
| Start payment/selection gate | không có | **MISSING HIGH** |
| Start idempotency/OCC | start không nhận key/version; row lock có | **PARTIAL** |
| Execution Attempt | không có | **MISSING** |
| `INTERRUPTED` | không có | **MISSING** |
| `CANCELLED != NOT_PERFORMED != INTERRUPTED` | schema có cancelled/not_performed, nhưng complete(false) sau start → not_performed | **CONFLICT** |
| `service.completed` event | code emit `service.performed` | **CONTRACT DRIFT** |
| `service.routed` event | code emit `dispatch.assigned` | **CONTRACT DRIFT** |
| `result.ready` riêng | current result flow riêng phần nào, nhưng không có canonical event chuẩn | **PARTIAL** |
| vitals không block | `dispatch_block` trả `VITALS_REQUIRED` | **CONFLICT với khảo sát mới** |

---

# 3. File-by-file impact audit

## A. Database / migrations

### 3.1 `supabase/migrations/20260911000001_luot_kham_lat_1.sql`
**Tác động: HIGH — KHÔNG sửa migration cũ; cần migration forward mới.**

Current `service_order` có:
- `exec_status`;
- `authorized_by/at`;
- `room_id`, `assigned_by/at`;
- `performed_by`, `started_at`, `finished_at`;
- `not_performed_reason`;
- `cancelled_by`, `cancel_reason`;
- `version`.

`exec_status` chỉ chấp nhận:

```text
draft
authorized
assigned
in_progress
performed
not_performed
cancelled
```

Đây chính là model một trục mà baseline v0.2 đã freeze là không đủ.

**Cần target mapping, chưa chốt schema implementation:**
- Selection axis;
- Billing/financial eligibility projection;
- Routing state/revision;
- Execution state;
- Execution Attempt;
- có thể giữ `exec_status` tạm để compatibility trong rollout.

**Không nên:** rewrite migration 20260911 trên hệ đã có dữ liệu.

---

### 3.2 `supabase/migrations/20260919000002_tien_thuoc_cp2_payment_cycle.sql`
**Tác động: LOW-MEDIUM — nền tốt, chủ yếu reuse.**

`payment_cycle` đã giữ từng lần thu riêng, có trạng thái chờ xác minh/paid/void, không phải overwrite một lịch sử duy nhất.

Đây gần với rule v0.2:

> payment history immutable; refund/adjustment là transaction mới.

**Gap:** cycle hiện neo theo `visit + kind`; allocation dịch vụ nằm gián tiếp qua snapshot bill lines, chưa trở thành một service-lifecycle gate công khai.

---

### 3.3 `supabase/migrations/20260919000004_tien_thuoc_cp5_hoan_tra.sql`
**Tác động: LOW — reuse mạnh.**

Đã có:
- `payment_refund`;
- `payment_refund_line`;
- FK tới đúng `payment_bill_line`;
- cumulative refund guard;
- immutable transition;
- `PENDING/COMPLETED/FAILED/CANCELLED`.

Đây thực chất đã hiện thực phần lớn concept v0.2 về:
- payment không bị rewrite;
- refund là transaction riêng;
- refund theo line đã thu.

**Mapping:** baseline gọi concept `REFUND_PENDING`; DB hiện dùng refund row `status='PENDING'`. Không bắt buộc đổi tên DB chỉ vì baseline dùng thuật ngữ khác.

---

### 3.4 Legacy migrations `20260801000002_order_services.sql` và dispatch migrations 20260804
**Tác động: LEGACY / COMPATIBILITY — không lấy làm model đích.**

`order_services()` cũ coi work-item payload là order; migration 20260911 sau đó chuyển sang `service_order` mỗi dịch vụ một row.

Các rail legacy nên:
- giữ nếu data/history còn phụ thuộc;
- không mở rộng tiếp cho Service Lifecycle v1;
- test/route retired phải tiếp tục ngăn code mới vô tình gọi lại.

---

## B. Backend core service lifecycle

### 3.5 `src/clinicai/services/luot_kham_service.py`
**Tác động: CRITICAL / HIGH. Đây là file trung tâm phải refactor có kiểm soát.**

File ~4.2k dòng, current runtime slice mới nằm chủ yếu ở đây.

#### `authorize_orders()` (~2377+)
Hiện:
- doctor authorize draft;
- new code có thể insert thẳng `authorized`;
- sau đó gọi `_tu_xep_phong(...)` ngay;
- event `orders.authorized`.

**Conflict lớn với v0.2:**

```text
doctor order
!= customer selection
!= payment
!= routing
```

Target:
- authorize/create official order phải dừng ở “ordered / selection=PENDING”;
- không auto queue/room ngay.

#### `dispatch_order()` (~3247+)
Hiện:
- gate actor = `DISPATCH_ROLES = {TRUONG_CA, MANAGEMENT}`;
- có `expected_version`;
- có command receipt/idempotency;
- gọi `_gan_phong()`.

**Reuse:** version/idempotency pattern tốt.  
**Conflict:** actor mới phải hỗ trợ thư ký/điều dưỡng theo policy.

#### `_gan_phong()` (~3322+)
Hiện:
- kiểm room serves node;
- room active/accepting;
- cập nhật/insert queue;
- cho move room nếu queue chưa `called/serving`;
- set `exec_status='assigned'`;
- emit `dispatch.assigned`.

**Reuse rất đáng kể:**
- room capability validation;
- queue manipulation;
- pre-start reroute;
- queue block/wait semantics.

**Cần đổi:**
- không dùng `exec_status='assigned'` làm cả routing+execution;
- routing revision;
- event canonical `service.routed`;
- state `REASSIGNMENT_REQUIRED`;
- reason code khi reroute/invalidate.

#### `_tu_xep_phong()` (~3426+)
Hiện:
- sau authorize tự chọn room;
- ưu tiên room hợp lệ/roster/queue ngắn;
- tự `_gan_phong`.

**Không bỏ thuật toán.**  
Đây chính là nền **recommender/rule engine** tốt cho baseline v0.2.

Nhưng semantic phải đổi từ:

```text
auto assignment authoritative
```

thành:

```text
room recommendation
→ người/command AssignServiceRoom xác nhận
```

Nếu sau này policy cho auto-route thì chính engine này có thể gọi command chuẩn, không bypass invariant.

#### `start_service()` (~4060+)
Hiện signature thực tế chỉ có:

```text
order_id, identity
```

Không có:
- `expected_version`;
- `idempotency_key`;
- `execution_attempt_id`.

Có row lock, và:
- nếu cùng performer đã `in_progress` thì trả `already=True`;
- actor khác tới sau bị rơi vào lỗi status không assigned;
- set `exec_status='in_progress'`;
- `performed_by`, `started_at`;
- queue → serving;
- emit `service.started`.

**Gap v0.2: HIGH**
- chưa check `Selection=SELECTED`;
- chưa check payment gate;
- chưa exact-once per attempt;
- manual retry sau mất response tạo key mới ở frontend;
- không có attempt history;
- conflict message chưa mô tả rõ competing actor.

**Reuse:**
- row locking;
- visit-busy/queue serialization;
- event trong transaction;
- permission plumbing.

#### `complete_service()` (~4133+)
Hiện body có:

```text
performed: bool
reason
result_note
```

Nếu `performed=False` sau khi service đang `in_progress`:
- set `exec_status='not_performed'`;
- event `service.not_performed`.

Đây **mâu thuẫn trực tiếp** v0.2:

> đã start nhưng không hoàn tất = `INTERRUPTED`, không phải `NOT_PERFORMED`.

Nếu performed true:
- `performed`;
- event `service.performed`;
- result_note có thể set `ket_qua_luc`.

Cần tách command semantics:
- CompleteService;
- MarkServiceNotPerformed (trước start);
- InterruptService (sau start);
- execution attempt.

#### external partner shortcut
`doi_tac_da_lay_mau` có thể nhảy từ authorized/assigned/in_progress thẳng `performed`.

Baseline v0.2 cố ý để external service là **open design**. Không nên ép path này sang internal flow cho tới khi chốt partner payment/routing/sample/result lifecycle.

**Kết luận file:** không viết lại toàn bộ `luot_kham_service.py`, nhưng các method order→route→start→complete là vùng refactor trọng tâm.

---

### 3.6 `src/clinicai/services/luot_kham_rules.py`
**Tác động: HIGH nhưng nhỏ, dễ test.**

`dispatch_block()` lines ~187–220 hiện:
- dispatchable chỉ `authorized/assigned`;
- bắt `authorized_by`;
- bắt `vitals_recorded`;
- nếu chưa sinh hiệu → `VITALS_REQUIRED`.

Hai conflict:
1. rule mới cần selection/payment readiness thay vì chỉ authorization;
2. khảo sát mới nói vitals không block progression.

Đây là file tốt để đặt pure-domain rules mới thay vì nhét điều kiện rải rác trong service.

**Nên reuse pattern:** pure functions + tests.

---

### 3.7 `src/clinicai/api/v1/routers/luot_kham.py`
**Tác động: HIGH.**

Current:
- dispatch body có `room_id`, `expected_version`;
- dispatch cần Idempotency-Key;
- start endpoint không body version/key;
- complete dùng `performed/reason/result_note`;
- dispatch guard hiện shift-lead/management.

Cần API contract mới/compatibility:
- selection confirm;
- start expected version + retry key;
- interrupt;
- not-performed semantic;
- routing actor policy;
- có thể execution attempt id.

Không nhất thiết phá đường URL hiện tại nếu giữ backward-compatible request shape trong rollout.

---

### 3.8 `src/clinicai/services/work_item_service.py`
**Tác động: LOW-MEDIUM — chủ yếu reuse pattern, không biến WorkItem thành ServiceOrder.**

Có:
- command `start/complete/skip/cancel`;
- role gate;
- dependency gate;
- OCC version;
- row lock;
- work_item + work_item_event atomic.

Đây là pattern tham khảo rất tốt cho command/OCC.

**Không nên:** ép execution attempts của service vào generic work_item statuses chỉ để “reuse”. Domain semantics khác nhau.

---

## C. Payment / Billing / Refund

### 3.9 `src/clinicai/services/payment_service.py`
**Tác động: HIGH.**

Current critical gate (~175–226):
- service/payment chỉ được thu khi `kham_xong`;
- nếu chưa, lỗi “Bác sĩ chưa khám xong lượt này — chưa thể thu tiền.”

Đây là conflict lớn nhất với target clinic:

```text
doctor orders
→ customer selects subset
→ reception pays
→ services performed
```

Phần **không nên bỏ**:
- server authoritative bill;
- `payment_cycle`;
- QR/transfer pending verification;
- bill revision;
- row locking;
- cycle idempotency;
- POS outbox;
- immutable payment history.

`_ghi_anh_hoa_don()` (~1076+) snapshot từng line:
- `source_type`;
- `source_id`;
- quantity;
- unit_price;
- line_total;
- billing_owner.

Với service line, `source_id = service_order.id`.

**Điều quan trọng:** phần lớn “Payment Allocation tới service_order” mà baseline tưởng còn thiếu **thực ra đã có dữ liệu lineage thông qua `payment_bill_line`**. Có thể dùng nó làm payment allocation record hoặc projection, thay vì tạo ngay một bảng allocation mới.

Event current khi paid:
- `payment.recorded`, không phải `payment.confirmed`.

Cần quyết định alias/contract migration, không nhất thiết rename lịch sử.

---

### 3.10 `src/clinicai/services/bill_service.py`
**Tác động: HIGH, code thay đổi không quá lớn nhưng luật cực quan trọng.**

Current service invoice query lines ~321–338:

```sql
o.exec_status NOT IN ('draft', 'cancelled', 'not_performed')
```

Nghĩa là:
- `authorized`;
- `assigned`;
- `in_progress`;
- `performed`

đều vào hóa đơn.

Target v0.2 yêu cầu hóa đơn dịch vụ dựa vào **customer selection**, không chỉ doctor authorization.

Cần sửa bill eligibility:
- chỉ selected/current selection;
- không tự tính order bác sĩ đề nghị mà khách chưa chọn;
- preserve external billing_owner exclusion.

**Reuse hoàn toàn:** price resolution, server-side total, revision hash, service-order line identity.

---

### 3.11 `src/clinicai/services/cashier_board_service.py`
**Tác động: HIGH.**

Current:
- board chỉ hiện visit sau `moc_kham_xong`;
- service list cũng dựa vào exec_status not draft/cancelled/not_performed.

Target:
- khách phải xuất hiện ở quầy ngay sau doctor ordering/selection stage, trước service execution;
- board phải phân biệt ordered vs selected;
- cashier phải chọn/xác nhận subset (hoặc một màn reception trước cashier nhưng state vẫn phải tồn tại).

Nền transaction history/refund display giữ được.

---

### 3.12 `src/clinicai/services/hoan_tien_service.py`
**Tác động: LOW-MEDIUM — bất ngờ là rất gần baseline v0.2.**

Current code:
- không sửa payment/payment_cycle gốc;
- refund đúng `payment_bill_line`;
- partial quantity;
- PENDING/COMPLETED;
- không vượt số đã thu;
- event financial riêng.

Đây đã giải quyết phần khó của “paid rồi bỏ service”.

**Gap còn lại:** orchestration giữa:
- `service.cancelled`;
- refund request;
- credit/reallocation policy.

Quyền refund đang tạm chỉ MANAGEMENT và comment rõ “HOLD J4”; chưa phải business rule cuối.

---

### 3.13 `src/dashboard/app/(dashboard)/thu-ngan/QuayThuNgan.tsx`
**Tác động: MEDIUM-HIGH.**

Current UI lines ~243–249 nói:
> khách ở đây sau khi bác sĩ khám xong.

Nhóm dịch vụ line ~267 còn label:
> “Dịch vụ đã khám”.

Target mới là:
> dịch vụ khách **chọn để làm**, thu trước khi thực hiện.

Payment UI/server-authoritative bill pattern nên giữ.

---

## D. Routing / queue / room

### 3.14 `src/clinicai/services/dispatch_service.py` + `src/clinicai/api/v1/routers/dispatch.py`
**Tác động: MEDIUM / LEGACY BOUNDARY.**

Có một rail dispatch visit/work-item cũ, actor thiên về TRUONG_CA/MANAGEMENT.

Service Lifecycle v1 hiện thực tế dùng per-order `_gan_phong()` trong `luot_kham_service`.

Cần tránh sửa cả hai rail như thể chúng là cùng một domain:
- xác định path nào còn UI/runtime thật;
- service routing mới phải có một owner;
- rail cũ giữ compatibility nếu còn chức năng điều phối visit-level.

---

### 3.15 `src/dashboard/app/(dashboard)/truong-ca/QueuesClient.tsx`
**Tác động: LOW cho write path.**

File này hiện chủ yếu read-only hiển thị queue theo room/load.

Đây là dữ liệu rất phù hợp dùng cho:
- rule-engine recommendation;
- AI routing recommendation sau này.

Không thấy write routing trong file đã đọc.

---

## E. Frontend clinical/service flow

### 3.16 `src/dashboard/app/(dashboard)/ban-kham/BanKham.tsx`
**Tác động: HIGH.**

Current comments + UI lock hành vi cũ:
- `draft → authorized → assigned → in_progress → performed`;
- bác sĩ “Duyệt chỉ định”;
- text: **“Duyệt xong khách tự vào hàng chờ phòng làm dịch vụ.”**
- active service detection dựa `authorized/assigned/in_progress`.

Target phải thay semantic:
- bác sĩ order xong chỉ là ordered;
- customer selection/reception/payment ở giữa;
- status chip phải biểu diễn ít nhất selection/billing/routing/execution theo cách người dùng hiểu;
- không tự queue ngay.

**Reuse:**
- service catalog picker;
- doctor vs secretary draft path nếu governance vẫn giữ;
- central `ChiDinhPanel`;
- refresh/data path.

---

### 3.17 `src/dashboard/app/(dashboard)/phong/[ma]/PhongDichVu.tsx`
**Tác động: HIGH nhưng UI khá dễ giữ khung.**

Khung hiện đã đúng kiểu:
- danh sách chờ;
- Bắt đầu;
- ghi kết quả/tệp;
- Xong.

Đây phù hợp flow mới.

Conflict:
- “Không làm được…” chỉ xuất hiện **sau khi đã start** (`dangLam`);
- gửi `xong-dich-vu {performed:false}` → backend ghi `not_performed`.

Target:
- đang IN_PROGRESS mà dừng = `INTERRUPTED`;
- NOT_PERFORMED phải là path trước start;
- UI cần action/wording khác cho “gián đoạn/dừng giữa chừng”;
- start phải gửi stable idempotency key + expected version/attempt.

---

### 3.18 `src/dashboard/app/(dashboard)/_lam-viec/api.ts`
**Tác động: MEDIUM-HIGH.**

Điểm tốt:
- một data/write seam tập trung `/api/luot-kham`;
- frontend không tự enforce business law.

Điểm cần sửa:
`guiThaoTac()` tạo `Idempotency-Key` **mới mỗi lần gọi**:

```ts
khoaGuiLai()
```

Điều này chỉ giúp mỗi HTTP call có key; nó **không đủ** cho UX retry cùng business intent sau timeout, vì click lại tạo key mới.

Với `StartService` v0.2, UI phải giữ/reuse key của cùng attempt/intent cho tới khi biết kết quả.

---

### 3.19 `src/dashboard/app/api/luot-kham/route.ts`
**Tác động: MEDIUM.**

Điểm tốt:
- whitelist action → backend path;
- forward Idempotency-Key;
- không copy permission rules vào Next.

Cần thêm/mapping:
- ConfirmServiceSelection;
- interrupt/not-performed path;
- request bodies mới;
- có thể keep old action aliases trong migration window.

---

## F. Result / checkout

### 3.20 `src/clinicai/services/tep_ket_qua_service.py`
**Tác động: MEDIUM, nhưng không nên trộn vào migration service-state đầu tiên quá sâu.**

Current:
- result file gắn `service_order_id`;
- external file có confirm state;
- upload cập nhật `service_order.ket_qua_luc`;
- internal result có thể trigger `sau_khi_co_ket_qua`;
- notification `bao_ket_qua_ve` imperative.

Baseline v0.2 chỉ freeze:

```text
service.completed != result.ready
```

Current code thực tế đã có separation phần nào, nhưng:
- chưa canonical `result.ready`;
- `ket_qua_luc` đôi khi được set từ result note/upload;
- event seam chưa chuẩn.

**Khuyến nghị impact:** giữ result lifecycle thành slice sau; chỉ bảo đảm migration execution không tiếp tục coi `completed` = ready.

---

### 3.21 `src/clinicai/services/checkout_service.py`
**Tác động: MEDIUM-HIGH.**

Current readiness:
- `svc_open` = service_order exec_status in `authorized/assigned/in_progress`;
- paid_service = có một payment kind dịch vụ PAID;
- timeline map performed/not_performed từ `exec_status`.

Khi tách axes/attempt:
- blocker query phải đọc new execution semantics;
- `NOT_SELECTED/CANCELLED` không được block;
- `INTERRUPTED` cần policy: còn work item/retry/resolve thì block hay incomplete close;
- paid-service không thể chỉ là “có payment kind” nếu selected services có allocation khác nhau.

Đây là downstream reader dễ bị bỏ sót nếu chỉ sửa write path.

---

# 4. Current test contracts đang khóa hành vi cũ

## 4.1 `src/tests/services/test_luot_kham_service_db.py`
**Tác động: VERY HIGH — test chính của rail mới.**

Current tests lock các hành vi sẽ đổi:

- after `authorize_orders`, assert mọi order thành `assigned`;
- comment/assert bác sĩ duyệt xong tự vào hàng chờ phòng;
- event sequence mong `dispatch.assigned` trong cùng lệnh authorize;
- dispatch bằng trưởng ca;
- start/complete không có selection/payment;
- event `service.performed`;
- test secretary/nurse dispatch boundaries theo luật cũ.

Đây không phải “test bị hỏng vô ích”; test đang chứng minh **contract cũ**. Khi đổi contract phải rewrite assertions có chủ đích.

---

## 4.2 `src/tests/services/test_slice1_rail_db.py`
**Tác động: HIGH.**

Helper `_lam()` hiện:
- nếu authorized thì dispatch;
- start;
- complete(performed bool).

`performed=False` hiện đại diện not-performed sau start — phải đổi vì v0.2 coi đó là interrupted.

Round/result tests cần map execution outcomes mới.

---

## 4.3 `src/tests/services/test_tien_thuoc_cp4_moc_kham_xong_db.py`
**Tác động: HIGH.**

Test này khóa:
> chưa `exam_completed_at` thì PaymentService không thu và CashierBoard không hiện.

Đây **trực tiếp ngược** flow mới thanh toán ancillary services trước thực hiện.

Có thể cần tách:
- tiền dịch vụ ancillary;
- tiền thuốc/final checkout;
- tiền khám.

Không nên đơn giản xóa mọi `kham_xong` gate cho mọi kind.

---

## 4.4 `src/tests/services/test_tien_thuoc_cp1_db.py` + CP2/CP5
**Tác động: LOW-MEDIUM, phần lớn giữ.**

Các contract đáng giữ:
- server computes total;
- bill revision;
- immutable snapshot;
- one collection cycle;
- exact refund line;
- concurrent financial safety.

Các test selection eligibility cần thêm, không phá những invariants tài chính này.

---

## 4.5 Dashboard boundary tests
Các test như:
- `ban-kham-kham-xong-gate-boundary.test.mts`;
- `quay-thu-ngan-boundary.test.mts`

đang lock text/status cũ và sẽ cần update khi UI semantics đổi.

---

# 5. Những thứ KHÔNG cần viết lại

1. **Room/node configuration** — giữ.
2. **Queue primitive** — giữ, chỉ đổi thời điểm service được enqueue.
3. **Rule chọn room hiện tại** trong `_tu_xep_phong` — giữ làm recommender.
4. **Server-side billing + revision** — giữ.
5. **payment_cycle** — giữ.
6. **payment_bill_line** — giữ và tận dụng như service allocation lineage.
7. **refund subsystem** — giữ phần lớn.
8. **POS outbox** — không liên quan phải phá.
9. **work-item kernel** — giữ.
10. **Result file storage** — giữ; chỉ làm seam/lifecycle sau.
11. **Frontend room workspace layout** — giữ khung, đổi actions/contracts.
12. **Central `/api/luot-kham` proxy pattern** — giữ.

---

# 6. Những thứ bắt buộc phải thay nếu thực hiện v0.2

## Core P0 domain migration
1. Có representation cho Selection + revision.
2. Có representation cho Routing state/revision.
3. Có Execution state mới, đặc biệt `INTERRUPTED`.
4. Có Execution Attempt hoặc representation tương đương.
5. Start command có payment/selection gate.
6. Start có stable idempotency + expected version.
7. Doctor order không auto-route.
8. Customer selection trước billing.
9. Bill eligibility theo selected services.
10. Cashier/payment không bị gate “exam complete” đối với ancillary service flow.
11. Routing actor policy mở theo target.
12. Complete/NotPerformed/Interrupted tách semantics.

## Downstream readers
13. Board/status labels.
14. Checkout blockers.
15. Result/review requirements mapping.
16. Event names/contracts/projections.

---

# 7. Migration strategy an toàn — KHÔNG big-bang

Đề xuất để implementation sau này kiểm:

### Phase A — Additive schema
- thêm state/revision/attempt structures;
- không xóa `exec_status`;
- không sửa migration lịch sử;
- backfill mapping rõ ràng.

### Phase B — New commands + dual projection
- official order ghi selection=PENDING;
- selection confirm;
- payment gate;
- routing;
- attempts;
- đồng thời duy trì legacy fields cần cho UI/readers chưa chuyển.

### Phase C — Switch readers
- bill/cashier;
- BanKham;
- PhongDichVu;
- checkout;
- result round logic.

### Phase D — remove legacy semantics
Chỉ sau khi:
- test mới xanh;
- smoke staging;
- không còn read/write path phụ thuộc status cũ.

---

# 8. File impact classification

## Nhóm chắc chắn phải sửa / thêm khi implement Service Lifecycle v1
- new forward migration(s)
- `src/clinicai/services/luot_kham_service.py`
- `src/clinicai/services/luot_kham_rules.py`
- `src/clinicai/api/v1/routers/luot_kham.py`
- `src/clinicai/services/payment_service.py`
- `src/clinicai/services/bill_service.py`
- `src/clinicai/services/cashier_board_service.py`
- `src/clinicai/services/checkout_service.py`
- `src/dashboard/app/(dashboard)/ban-kham/BanKham.tsx`
- `src/dashboard/app/(dashboard)/phong/[ma]/PhongDichVu.tsx`
- `src/dashboard/app/(dashboard)/thu-ngan/QuayThuNgan.tsx`
- `src/dashboard/app/(dashboard)/_lam-viec/api.ts`
- `src/dashboard/app/api/luot-kham/route.ts`
- primary DB/integration tests for these flows

## Nhóm nhiều khả năng chỉnh nhỏ / adapter
- `src/clinicai/services/hoan_tien_service.py`
- result/review readers in `luot_kham_service.py`
- `src/clinicai/services/tep_ket_qua_service.py`
- dashboard types/status chips
- audit/event label mapping

## Nhóm giữ nguyên làm nền
- work-item kernel/service
- clinic room/node config
- POS outbox
- refund DB guards
- payment-cycle history
- media storage
- realtime plumbing

## Nhóm legacy cần khóa, không mở rộng
- old `order_services()` work-item order rail
- older visit-level dispatch path, trừ khi runtime audit chứng minh vẫn có use-case độc lập.

---

# 9. Mức sửa thực tế

**Không phải “sửa cả hệ thống”.**

Đây là thay đổi **một vertical slice lớn** với khoảng:
- ~12–15 production files lõi có sửa đáng kể;
- 1–3 forward migrations tùy schema lựa chọn;
- một cụm tests hiện tại phải rewrite/thêm;
- một số readers/labels phụ phải adapt.

Phần khó không nằm ở số dòng gõ, mà ở:
- migration dữ liệu cũ;
- compatibility `exec_status`;
- payment eligibility;
- concurrency/idempotency;
- không phá checkout/result/external partner.

Nếu AI code nhanh, typing có thể rất nhanh; nhưng migration/test/staging vẫn là phần quyết định an toàn.

---

# 10. Các phát hiện làm estimate NHẸ hơn dự kiến ban đầu

Audit kỹ cho thấy 3 thứ baseline tưởng có thể phải xây mới, thực ra code đã có nền:

### 10.1 Payment allocation gần như đã tồn tại
`payment_bill_line` snapshot:
- `source_type='service_order'`
- `source_id=service_order.id`

=> Có thể dùng chính lineage này để biết payment cycle đã cover service nào.

### 10.2 Refund subsystem đã rất đầy đủ
Không cần xây refund ledger từ số 0.

### 10.3 Routing recommender đã tồn tại
`_tu_xep_phong` đã biết:
- phòng nào phục vụ node;
- active/accepting;
- roster;
- queue load.

Cần đổi nó từ **auto-authoritative assignment** thành **recommendation / command path** chứ không viết lại thuật toán chọn phòng.

---

# 11. Các phát hiện làm estimate NẶNG hơn dự kiến

### 11.1 Auto-route nằm ngay trong authorize command
Không chỉ UI text; domain transaction hiện nối order→room trực tiếp.

### 11.2 Payment gate cũ được khóa ở nhiều tầng
- PaymentService;
- CashierBoard;
- tests CP4;
- UI text.

### 11.3 `not_performed` hiện là outcome sau start
Phải migration semantic cẩn thận nếu dữ liệu lịch sử đã có row như vậy; không thể assume mọi historical `not_performed` đều “chưa từng start”.

Có thể backfill dựa:
- `started_at`;
- `finished_at`;
- event history.

Nhưng cần đo data trước migration, chưa được đoán.

### 11.4 `StartService` idempotency hiện chưa đạt baseline
Row lock có nhưng command contract chưa đủ.

---

# 12. Những điều chưa được phép kết luận

1. Chưa biết **local dirty branch** có vá sẵn một số gap hay không.
2. Chưa chạy DB tests trên branch này.
3. Chưa đo production data distribution của `exec_status`, nhất là historical `not_performed`.
4. Chưa quyết exact schema implementation của four-axis model.
5. Chưa chốt refund/credit/reallocation business policy.
6. Chưa chốt external partner lifecycle.
7. Chưa chốt permission matrix cuối.
8. Chưa khẳng định mọi legacy dispatch/order route hoàn toàn unused ở production chỉ bằng static code.

---

# 13. Trình tự implementation hợp lý sau khi quyết định làm

Không code trong audit này. Nếu giao AI sau này, thứ tự ít rủi ro nhất:

1. **Data audit** hiện trạng `service_order/payment_bill_line/payment_cycle/refund`.
2. **ADR implementation mapping** v0.2 → schema cụ thể.
3. Additive migration + backfill rules.
4. Selection command/state.
5. Bill/payment eligibility theo selection.
6. Routing command/recommender split.
7. Execution Attempt + idempotent Start.
8. Complete / NotPerformed / Interrupted.
9. Update boards/UI.
10. Update checkout/result readers.
11. Rewrite/add DB tests.
12. CI.
13. staging migration.
14. end-to-end smoke/UAT.
15. production rollout.

---

# 14. Kết luận để Tuyền ra quyết định

**Baseline v0.2 không “lệch code đến mức phải làm lại ClinicAI”.**

Nó yêu cầu **refactor sâu đúng một trục trung tâm — service lifecycle**, trong khi nhiều infrastructure tốt hiện có được giữ.

Điểm đáng mừng nhất:
- money/refund infrastructure mạnh hơn tưởng tượng;
- routing algorithm đã có;
- queue/room/work-item/event transaction patterns đã có.

Điểm phải thận trọng nhất:
- doctor authorize hiện auto-route;
- payment hiện đặt sau exam completion;
- single `exec_status` đang là assumption của nhiều reader/test;
- historical `not_performed` có semantics khác v0.2.

Do đó strategy đúng là **forward migration + compatibility slices**, không rewrite/big-bang.

---

## Audit completion note

Đã đọc trực tiếp code committed trên branch/HEAD nêu trên cho các file/lát cắt được liệt kê.  
**Không chạy test và không kiểm runtime.**  
**Không sửa application, migration hoặc deploy.**
