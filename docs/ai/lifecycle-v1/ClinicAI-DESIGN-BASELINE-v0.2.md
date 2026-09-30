# ClinicAI — DESIGN BASELINE v0.2

**Ngày:** 22/09/2026  
**Trạng thái:** Baseline thiết kế đang hiệu lực. **Service Lifecycle v1 đã FREEZE ở mức domain contract**; chưa đồng nghĩa schema/code/runtime đã được migration theo thiết kế này.  
**Mục đích:** Làm nguồn thiết kế chung để Tuyền, ChatGPT, Claude, Grok/Night Shift, Antigravity/Codex và các AI khác cùng hiểu **một target behavior**, thay vì suy từ code hiện tại hoặc lịch sử chat rời rạc.

> Baseline này **không tự thay thế** phê duyệt chuyên môn của bác sĩ, xác nhận phạm vi của PM, hoặc bằng chứng runtime/staging/production.  
> Code hiện tại là **implementation evidence**, không phải business truth.

---

## 0. Cách dùng baseline này

Mọi AI / kỹ sư trước khi thiết kế hoặc sửa code cho phần liên quan phải đọc theo thứ tự:

1. `ClinicAI-DESIGN-BASELINE-v0.2.md` — target behavior đã chốt trong phạm vi tài liệu này.
2. Nguồn yêu cầu liên quan (`ClinicAI-CONTEXT-v1.0.md`, `NGUON-PM-v1.0.0.txt`, tài liệu phòng khám, artifact kỹ thuật nếu cần).
3. ADR / quyết định chi tiết của lát cắt đang làm, nếu đã tồn tại.
4. Code + migration + test hiện tại để xác định implementation đang ở đâu.

Nếu code mâu thuẫn baseline:
- **không tự coi code là đúng**;
- báo mâu thuẫn;
- xác định migration/compatibility plan;
- không silently đổi nghiệp vụ.

Nếu nguồn PM/bác sĩ mâu thuẫn mục **[CHỐT-TUYỀN]**:
- không tự chọn bên thuận tiện;
- đánh dấu conflict;
- cần PM/bác sĩ/Tuyền chốt theo thẩm quyền tương ứng.

### Nhãn thông tin

- **[CHỐT-TUYỀN]**: Tuyền đã chốt trong trao đổi thiết kế; là target behavior hiện tại.
- **[NGUỒN]**: yêu cầu/định hướng lấy từ nguồn đã đọc.
- **[ĐỀ XUẤT]**: phương án thiết kế chưa chốt.
- **[BÁO CÁO-CODE]**: code/audit cho biết hiện trạng; chưa tự đồng nghĩa runtime/prod đang đúng như vậy.
- **[CHƯA XÁC MINH]**: thiếu kiểm chứng code/runtime/nguồn.
- **[CẦN PM/BÁC SĨ]**: cần người có thẩm quyền nghiệp vụ/chuyên môn xác nhận.

---

# 1. Nguyên tắc kiến trúc đang chốt

## 1.1. Kiến trúc tổng thể

**[CHỐT-TUYỀN]**

ClinicAI ưu tiên:

- modular monolith ở quy mô hiện tại;
- synchronous cho invariant/gate sống còn trong cùng giao dịch;
- asynchronous cho side-effect và consumer phụ;
- không tự thêm microservices/Kafka/event sourcing chỉ để “hiện đại”;
- module mới phải cố gắng gắn qua contract công khai thay vì chọc trực tiếp vào nhiều service cũ.

Mục tiêu mở rộng:

```text
Core domain
   │
   ├─ Command API
   ├─ State
   ├─ Domain Event
   └─ Work Item
          │
          ├─ AI
          ├─ Zalo/Notification
          ├─ Analytics
          └─ các module tương lai
```

Module mới không được mặc định có quyền UPDATE trực tiếp core state.

## 1.2. “Lego test”

**[CHỐT-TUYỀN]**

Một capability mới được coi là tương đối “Lego” nếu có thể thêm bằng một hoặc nhiều cách:

- subscribe/read Domain Event;
- đọc projection/API có quyền;
- tạo Recommendation / Work Item;
- gọi Command API chuẩn;

mà **không cần sửa trực tiếp nhiều domain service cũ**.

Nếu muốn thêm AI mà phải chèn `call_ai()` vào booking, vitals, payment, ultrasound, pharmacy... thì kiến trúc chưa đạt mục tiêu Lego.

---

# 2. Domain Event — contract đã chốt

## 2.1. Định nghĩa

**[CHỐT-TUYỀN]**

> Domain Event là một **sự thật nghiệp vụ quan trọng đã thực sự xảy ra**, có ý nghĩa độc lập với UI, và có thể hữu ích cho phần khác của hệ thống.

Event kể chuyện ở **thì quá khứ**.

Ví dụ:

```text
service.ordered
payment.confirmed
service.started
service.completed
result.ready
```

Không phải Domain Event:

```text
StartService        # command
payment.status=PAID # state
button.clicked      # UI telemetry
page.refreshed      # realtime/technical
```

## 2.2. Bảy luật Domain Event

**[CHỐT-TUYỀN]**

### DE-01 — Event là fact, không phải command
Command yêu cầu hệ thống làm một việc. Event chỉ được tạo sau khi việc đó thành công.

### DE-02 — Event là immutable
Event đã xảy ra không bị sửa nghĩa về sau. State có thể thay đổi; event history không rewrite sự thật cũ.

### DE-03 — Chỉ phát event có ý nghĩa nghiệp vụ
Không biến mọi click/autosave/refresh thành Domain Event.

### DE-04 — Domain state + event phải atomic
Nếu một command làm thay đổi state và tạo Domain Event, hai thứ phải cùng transaction hoặc có cơ chế tương đương bảo đảm không xảy ra:
- state thành công nhưng event mất;
- event tồn tại nhưng state rollback.

### DE-05 — Mỗi event có định danh + phiên bản contract
Tối thiểu có `event_id` và `event_version`.

### DE-06 — Payload tối thiểu
Không copy toàn bộ bệnh án/PHI vào event nếu consumer có thể đọc qua API/projection đúng quyền.

### DE-07 — Producer không biết consumer
Domain service phát sự thật; không phụ thuộc Telegram/Zalo/AI/Analytics nào đang nghe.

## 2.3. Envelope tối thiểu

**[CHỐT-TUYỀN — mức concept, chưa chốt schema DB]**

```text
event_id
event_type
event_version

clinic_id

aggregate_type
aggregate_id

occurred_at
recorded_at

correlation_id   optional
causation_id     optional

actor_staff_id   optional

payload
```

Giải thích:

- `event_id`: ID duy nhất của event.
- `event_type`: business fact đã xảy ra.
- `event_version`: version của contract event, không phải version row DB.
- `clinic_id`: tenant/phòng khám.
- `aggregate_type` + `aggregate_id`: đối tượng chính của sự kiện.
- `occurred_at`: lúc sự thật xảy ra.
- `recorded_at`: lúc hệ thống ghi nhận.
- `correlation_id`: nhóm nhiều event thuộc cùng một hành trình/command lớn.
- `causation_id`: sự kiện/command trước gây ra event này, nếu có.
- `actor_staff_id`: người gây ra sự kiện nếu có; system event có thể null.
- `payload`: dữ liệu domain tối thiểu.

## 2.4. Không Event Sourcing toàn hệ thống

**[CHỐT-TUYỀN]**

ClinicAI **không** chuyển sang mô hình phải replay toàn bộ event để dựng state mỗi lần.

Các bảng hiện hành vẫn giữ current state, ví dụ:

```text
appointment
visit
service_order
payment
clinical_record
...
```

Domain Event phục vụ integration, AI, analytics, automation, notification và lịch sử nghiệp vụ cần thiết.

---

# 3. Bốn khái niệm phải tách

## 3.1. Domain Event

**[CHỐT-TUYỀN]**

Sự thật nghiệp vụ đã xảy ra.

## 3.2. Audit

**[CHỐT-TUYỀN — nghĩa khái niệm, chưa chốt storage]**

Ai đã làm gì, lúc nào, trên tài nguyên nào, theo quyền/vai nào.

Audit không tự đồng nghĩa Domain Event.

## 3.3. Delivery

**[CHỐT-TUYỀN — nghĩa khái niệm, chưa chốt storage]**

Consumer nào đã xử lý event nào, thành công/thất bại/retry ra sao.

Delivery không phải business fact.

## 3.4. Realtime

**[CHỐT-TUYỀN — nghĩa khái niệm]**

Tín hiệu giúp UI/client biết dữ liệu vừa đổi để refresh/update.

Realtime signal không phải Domain Event.

---

# 4. Lát cắt chuẩn: Bác sĩ chỉ định → khách chọn → thanh toán → thực hiện dịch vụ

Đây là lát cắt tham chiếu đầu tiên để kiểm kiến trúc.

## 4.1. Ý nghĩa nghiệp vụ

**[CHỐT-TUYỀN]**

Bốn chuyện khác nhau, không được coi là một status duy nhất:

```text
Bác sĩ ĐỀ XUẤT dịch vụ
        ↓
Khách CHỌN dịch vụ sẽ làm
        ↓
Dịch vụ được THANH TOÁN / đủ điều kiện tài chính
        ↓
Dịch vụ được THỰC HIỆN
```

Các mệnh đề bắt buộc:

1. Bác sĩ chỉ định **không đồng nghĩa** khách đồng ý làm.
2. Khách đồng ý làm **không đồng nghĩa** đã thanh toán.
3. Đã thanh toán **không đồng nghĩa** đã thực hiện.
4. Thực hiện xong **không đồng nghĩa** kết quả đã sẵn sàng.
5. Kết quả có lifecycle riêng.

---

# 5. State model của `service_order`

## 5.1. Nguyên tắc

**[CHỐT-TUYỀN — Service Lifecycle v1]**

Một `service_order` không dùng một `status` duy nhất để gánh mọi ý nghĩa. Domain nhìn nó theo bốn trục độc lập:

```text
Selection
Billing
Routing
Execution
```

Ngoài ra có hai concept phiên bản/lịch sử cần giữ:

```text
selection_revision
routing_revision
```

và một concept con:

```text
Execution Attempt
```

> Đây là **domain model đã freeze v1**, chưa đồng nghĩa database phải ngay lập tức có đúng các cột/enum/bảng mang tên như tài liệu.

---

## 5.2. Selection

```text
PENDING
SELECTED
NOT_SELECTED
```

- `PENDING`: bác sĩ đã chỉ định; khách chưa xác nhận lựa chọn.
- `SELECTED`: khách hiện xác nhận sẽ thực hiện dịch vụ.
- `NOT_SELECTED`: bác sĩ vẫn đã chỉ định, nhưng khách hiện không chọn thực hiện dịch vụ đó.

**[CHỐT-TUYỀN]**

Không xóa `service_order` chỉ vì khách không chọn làm.

```text
ordered
≠
selected
```

Bác sĩ từng chỉ định là một sự thật cần giữ; lựa chọn của khách là state hiện hành riêng.

### `selection_revision`

Mỗi lần xác nhận lại tập dịch vụ:
- revision tăng;
- event cũ không bị sửa;
- optimistic concurrency phải ngăn hai màn hình ghi đè lẫn nhau.

---

## 5.3. Billing

```text
NOT_REQUIRED
DUE
PENDING_VERIFICATION
PAID
REFUND_PENDING
REFUNDED
```

- `NOT_REQUIRED`: dịch vụ không yêu cầu phòng khám thu khoản này.
- `DUE`: có nghĩa vụ thanh toán.
- `PENDING_VERIFICATION`: đang chờ xác minh QR/chuyển khoản/phương thức tương đương.
- `PAID`: khoản thanh toán tương ứng đã được xác nhận.
- `REFUND_PENDING`: đã có yêu cầu/tiến trình hoàn tiền nhưng chưa hoàn tất.
- `REFUNDED`: khoản tương ứng đã được hoàn theo policy.

**[CHỐT-TUYỀN]**

Payment đã xảy ra không bị rewrite thành “chưa từng thanh toán”.

```text
payment transaction = immutable history
refund/adjustment    = transaction mới
```

Payment phải truy được chính xác nó cover những `service_order` nào.

### Payment Allocation

**[CHỐT-TUYỀN — domain concept, chưa chốt schema]**

Cần có khả năng biểu diễn:

```text
Payment
   └── allocation → ServiceOrder
```

để xử lý đúng:
- thanh toán nhiều dịch vụ;
- bỏ một dịch vụ sau khi đã trả tiền;
- hoàn tiền;
- đổi sang service hợp lệ khác;
- thu thêm phần chênh.

Không chỉ lưu tổng tiền theo visit rồi suy ngược.

**[CHƯA CHỐT — policy kinh doanh]**

Phòng khám/PM chưa xác nhận đầy đủ:
- hoàn tiền ngay;
- giữ credit;
- cho phép chuyển allocation;
- cấm đổi sau thanh toán;
- quy tắc chênh lệch tiền.

Kiến trúc phải hỗ trợ các policy này nhưng không tự chọn policy.

---

## 5.4. Routing

```text
UNASSIGNED
ASSIGNED
REASSIGNMENT_REQUIRED
```

- `UNASSIGNED`: chưa có phòng chính thức.
- `ASSIGNED`: đã có room assignment hiện hành.
- `REASSIGNMENT_REQUIRED`: assignment cũ đã mất hiệu lực; cần điều phối lại.

### `routing_revision`

Mỗi quyết định assignment chính thức tăng revision.

Ví dụ:

```text
rev 1: null → SA1
rev 2: SA1 → SA2
```

`service.routed` được phép xuất hiện nhiều lần trong đời một `service_order`.

**[CHỐT-TUYỀN]**

Room suggestion không phải authoritative state.

```text
recommendation = đề xuất
assignment     = business state
```

---

## 5.5. Execution

```text
PENDING
WAITING
IN_PROGRESS
COMPLETED
CANCELLED
NOT_PERFORMED
INTERRUPTED
```

- `PENDING`: chưa vào hàng thực hiện.
- `WAITING`: đang chờ thực hiện tại service/phòng.
- `IN_PROGRESS`: một execution attempt đang chạy.
- `COMPLETED`: service đã hoàn thành thành công.
- `CANCELLED`: bị hủy **trước khi bắt đầu thực hiện**.
- `NOT_PERFORMED`: đã tới bước thực hiện nhưng **chưa bắt đầu**, cuối cùng không thực hiện được.
- `INTERRUPTED`: đã thực sự bắt đầu nhưng attempt bị dừng trước khi hoàn thành.

Ba trạng thái cuối không được trộn:

```text
CANCELLED
= quyết định dừng trước khi start

NOT_PERFORMED
= tới bước làm nhưng không có attempt thực sự bắt đầu

INTERRUPTED
= đã có attempt bắt đầu nhưng không hoàn tất
```

---

## 5.6. Execution Attempt

**[CHỐT-TUYỀN — domain concept]**

Một `service_order` có thể có nhiều lần thử thực hiện.

Ví dụ:

```text
ServiceOrder SA
   │
   ├── Attempt #1
   │     room = SA1
   │     started 10:00
   │     interrupted 10:05
   │     reason = EQUIPMENT_FAILURE
   │
   └── Attempt #2
         room = SA2
         started 10:15
         completed 10:30
```

Do đó invariant chính xác là:

> `StartService` có business effect exactly-once **trên mỗi execution attempt**, không phải exactly-once cho toàn bộ đời `service_order`.

Tên bảng/ID/storage của attempt **chưa chốt**; concept domain đã chốt.

---

## 5.7. Các trạng thái điển hình

### Bác sĩ vừa chỉ định

```text
selection = PENDING
billing   = chưa phát sinh nghĩa vụ
routing   = UNASSIGNED
execution = PENDING
```

### Khách chọn

```text
selection = SELECTED
billing   = DUE hoặc NOT_REQUIRED
routing   = UNASSIGNED
execution = PENDING
```

### Đã thanh toán hợp lệ

```text
selection = SELECTED
billing   = PAID
routing   = UNASSIGNED
execution = PENDING
```

### Đã chốt phòng và vào hàng chờ

```text
selection = SELECTED
billing   = PAID / NOT_REQUIRED
routing   = ASSIGNED
execution = WAITING
```

### Đang làm

```text
execution = IN_PROGRESS
```

### Hoàn thành

```text
execution = COMPLETED
```

### Phòng cũ mất hiệu lực trước khi bắt đầu

```text
routing   = REASSIGNMENT_REQUIRED
execution = WAITING
```

### Đã bắt đầu nhưng bị dừng

```text
execution = INTERRUPTED
```

---

# 6. Command model của Service Lifecycle v1

**[CHỐT-TUYỀN — tên command có thể thay khi map code, semantics không thay]**

## 6.1. `CreateServiceOrders`

Người khởi tạo: bác sĩ theo policy chuyên môn.

Tác dụng:
- tạo một hoặc nhiều `service_order`;
- không tự coi khách đã chọn;
- không tự coi đã thanh toán;
- không tự đưa vào phòng.

Sau thành công:

```text
service.ordered
```

Mỗi order có event riêng; một thao tác tạo nhiều order có thể dùng cùng `correlation_id`.

---

## 6.2. `ConfirmServiceSelection`

UI có thể tick/un-tick trước khi xác nhận mà không tạo Domain Event.

Input concept:

```text
visit_id
selected_order_ids
expected_selection_revision
idempotency_key
```

Backend phải kiểm tối thiểu:
- các order thuộc đúng visit;
- order thật sự tồn tại từ chỉ định hợp lệ;
- chưa đi vào trạng thái execution không cho phép sửa selection;
- chưa có payment confirmed khiến việc bỏ service phải đi flow tài chính riêng;
- revision không stale.

Sau thành công:
- selected → `SELECTED`;
- còn lại trong tập chỉ định hiện hành → `NOT_SELECTED`;
- tăng `selection_revision`.

Phát:

```text
service_selection.confirmed
```

**[CHỐT-TUYỀN]**

Trước payment có thể xác nhận lại lựa chọn.

Sau payment, bỏ service **không** dùng flow selection đơn giản nữa.

---

## 6.3. `ConfirmPayment`

Backend phải kiểm:
- đúng visit/patient;
- đúng service/order được thanh toán;
- giá/bill authoritative;
- phương thức;
- verification nếu cần;
- idempotency/double-process;
- allocation tới từng `service_order`.

Sau thành công:

```text
payment.confirmed
```

Payment command phải commit state đủ nhất quán để gate execution kiểm ngay được; không chờ consumer async mới mở quyền bắt đầu dịch vụ.

---

## 6.4. `CancelPaidService` / financial-resolution command

**[CHỐT-TUYỀN — semantics; tên command cuối chưa chốt]**

Khi service đã `PAID` nhưng khách bỏ trước khi start:
- không undo payment cũ;
- không dùng `ConfirmServiceSelection` như thể chưa từng thanh toán;
- service có thể chuyển `CANCELLED` nếu policy cho phép;
- tài chính đi flow refund/credit/reallocation riêng.

Các event đã nhận diện:

```text
service.cancelled
payment.refund_requested
payment.refunded
```

**[CHƯA CHỐT]**

Policy cụ thể refund/credit/reallocation cần PM/phòng khám xác nhận.

---

## 6.5. `AssignServiceRoom`

Thư ký **hoặc** điều dưỡng có thể dùng cùng command nếu policy/ca hiện hành cho phép.

Backend kiểm:
- quyền điều phối;
- phòng active;
- phòng phục vụ được service;
- nhân sự/điều kiện cần thiết nếu rule yêu cầu;
- service đủ điều kiện đi làm;
- service chưa `IN_PROGRESS`;
- expected version/revision không stale.

Sau thành công:
- `routing = ASSIGNED`;
- `room_id` hiện hành được thay đổi;
- tăng `routing_revision`;
- nếu gate đủ thì execution ở `WAITING`.

Phát:

```text
service.routed
```

Event có thể mang:

```text
from_room_id
to_room_id
routing_revision
reason_code
```

`service.routed` có thể xuất hiện nhiều lần.

---

## 6.6. Invalidate routing

Khi assignment hiện tại không còn hợp lệ trước khi execution bắt đầu, ví dụ:
- phòng đóng;
- máy hỏng;
- không còn nhân sự phù hợp;

state:

```text
routing = REASSIGNMENT_REQUIRED
```

phát:

```text
service.routing_invalidated
```

Reason code concept:

```text
ROOM_UNAVAILABLE
STAFF_UNAVAILABLE
EQUIPMENT_FAILURE
LOAD_BALANCE
PATIENT_NEED
MANUAL_CORRECTION
OTHER
```

Nếu chưa có assignment thay thế ngay, phải có Work Item/trách nhiệm điều phối lại.

---

## 6.7. `StartService`

Input concept:

```text
service_order_id
execution_attempt_id
expected_version
idempotency_key
```

Backend kiểm tối thiểu:
- selection = `SELECTED`;
- payment gate thỏa (`PAID` hoặc `NOT_REQUIRED`);
- routing hợp lệ nếu service cần phòng;
- actor có quyền;
- attempt chưa được start;
- version hiện hành đúng.

Sau thành công:
- attempt → `IN_PROGRESS`;
- order execution phản ánh `IN_PROGRESS`;
- ghi `started_at`, `started_by`;
- tăng version.

Phát đúng một canonical event cho attempt đó:

```text
service.started
```

### Idempotency + concurrency

**[CHỐT-TUYỀN]**

Retry cùng `idempotency_key`:
- không chạy side effect lần hai;
- trả lại cùng logical result của command đầu.

Hai command khác key cùng cạnh tranh:
- chỉ một command được thắng;
- command thua nhận `409 Conflict` hoặc semantics tương đương;
- không silently coi command mới là cùng retry.

UI disable button chỉ là UX; backend vẫn là nơi bảo vệ invariant.

Row lock/transaction serialization và `expected_version` giải quyết hai vấn đề khác nhau và có thể cùng tồn tại:
- server-side race;
- client stale snapshot.

---

## 6.8. `CompleteService`

Chỉ hợp lệ khi execution attempt hiện hành đang `IN_PROGRESS`.

Sau thành công:
- attempt hoàn thành;
- order `execution = COMPLETED`;
- ghi thời gian/người thực hiện.

Phát:

```text
service.completed
```

`service.completed` luôn có nghĩa service đã thực hiện xong; không dùng `completed + performed=false`.

---

## 6.9. `MarkServiceNotPerformed`

**[CHỐT-TUYỀN — semantics; tên command cuối có thể đổi]**

Dùng khi khách đã tới bước thực hiện nhưng **không có attempt nào thực sự bắt đầu** và cuối cùng không làm được.

Sau thành công:

```text
execution = NOT_PERFORMED
```

phát:

```text
service.not_performed
```

Reason phải được lưu theo contract phù hợp.

---

## 6.10. `InterruptService`

Dùng khi attempt đã `IN_PROGRESS` nhưng không thể hoàn thành.

Input concept:

```text
service_order_id
execution_attempt_id
expected_version
idempotency_key
reason_code
reason_note optional
```

Reason code concept:

```text
EQUIPMENT_FAILURE
PATIENT_REQUEST
CLINICAL_SAFETY
TECHNICAL_FAILURE
STAFF_UNAVAILABLE
OTHER
```

`OTHER` cần note.

Sau thành công:
- attempt → interrupted;
- order execution phản ánh `INTERRUPTED`;
- ghi thời gian/lý do.

Phát:

```text
service.interrupted
```

Interruption **không tự đồng nghĩa refund**.

Sau interruption có thể:
- reroute + retry attempt;
- reschedule;
- financial resolution;
- close theo quyết định hợp lệ.

Nếu lý do mang tính chuyên môn, quyền quyết định tiếp tục/dừng cần bác sĩ/PM xác nhận; baseline không tự mở quyền cho role vận hành.

---

# 7. Domain Event catalogue — Service Lifecycle v1

**[CHỐT-TUYỀN]**

## 7.1. Happy path

```text
service.ordered
service_selection.confirmed
payment.confirmed
service.routed
service.started
service.completed
```

## 7.2. Routing / exception path

```text
service.routing_invalidated
service.routed
```

`service.routed` có thể xuất hiện nhiều lần theo revision.

## 7.3. Cancel / không thực hiện

```text
service.cancelled
service.not_performed
```

## 7.4. Interruption / retry

```text
service.started
service.interrupted

# sau xử lý
service.routed        # nếu cần đổi phòng
service.started       # attempt mới
service.completed     # nếu retry thành công
```

## 7.5. Financial resolution đã nhận diện

```text
payment.refund_requested
payment.refunded
```

Policy sinh các event này chưa hoàn toàn chốt.

## 7.6. Result lifecycle riêng

```text
result.ready
```

**[CHỐT-TUYỀN]**

```text
service.completed != result.ready
```

**[CHƯA CHỐT]**

Không tự thêm toàn bộ các mốc sau cho mọi service:

```text
result.received
result.validated
result.released
result.sent
result.amended
```

Phải chốt theo nghiệp vụ từng loại kết quả.

---

# 8. Routing: người, rule engine và AI

## 8.1. Recommendation không phải authoritative state

**[CHỐT-TUYỀN]**

Hệ thống có thể gợi ý phòng dựa trên:
- service capability;
- trạng thái phòng;
- nhân sự;
- queue/load;
- patient constraints;
- policy.

Gợi ý có thể thay đổi nên không phải business state.

```text
suggestion ≠ assignment
```

Không tạo canonical Domain Event cho mỗi lần suggestion thay đổi.

## 8.2. Người xác nhận

Hiện tại:
- thư ký có thể điều phối;
- điều dưỡng có thể điều phối;
- tất cả qua cùng `AssignServiceRoom`;
- backend policy quyết quyền thật.

## 8.3. AI sau này

AI/rule engine là recommender:

```text
input:
  service
  eligible rooms
  queue/load
  staff availability
  expected duration
  patient constraints

output:
  recommended room
  reason
  confidence
```

AI không UPDATE state trực tiếp.

Nếu tương lai cho auto-routing, system/policy vẫn gọi `AssignServiceRoom` chuẩn và chịu cùng invariant.

---

# 9. Invariants — Service Lifecycle v1

**[CHỐT-TUYỀN]**

### INV-01 — Order khác Selection
`service.ordered` không đồng nghĩa khách sẽ làm.

### INV-02 — Không xóa chỉ định khi khách không chọn
`NOT_SELECTED` không làm mất lịch sử bác sĩ đã chỉ định.

### INV-03 — Selection trước payment có thể xác nhận lại
Mỗi lần xác nhận tạo revision mới; optimistic concurrency ngăn ghi đè stale state.

### INV-04 — Sau payment không còn là “sửa checkbox”
Bỏ service đã `PAID` phải đi flow cancellation/financial resolution.

### INV-05 — Payment history immutable
Không rewrite payment cũ thành chưa từng tồn tại; refund/adjustment là transaction mới.

### INV-06 — Payment phải có allocation
Hệ thống phải truy được khoản nào cover service/order nào.

### INV-07 — Payment gate synchronous
Service cần phòng khám thu tiền không được `StartService` trước khi payment gate thỏa. `NOT_REQUIRED` được bỏ qua gate này.

### INV-08 — Suggestion không thay state
Chỉ assignment chính thức mới thay routing và phát `service.routed`.

### INV-09 — Routing có revision
Assignment cũ không bị silent overwrite khỏi lịch sử.

### INV-10 — Routing invalid phải có trách nhiệm xử lý
Nếu room assignment mất hiệu lực và chưa có room mới ngay, phải có Work Item/owner phù hợp để tránh bệnh nhân bị bỏ quên.

### INV-11 — Không reroute bằng luồng bình thường khi đã IN_PROGRESS
Sau khi attempt bắt đầu, room problem là execution interruption, không còn là đổi queue đơn giản.

### INV-12 — Start exactly-once per attempt
Mỗi execution attempt tối đa có một successful `StartService` và một canonical `service.started`.

### INV-13 — Idempotency khác concurrency
Retry cùng key trả cùng logical result; hai command khác key cạnh tranh thì chỉ một thắng.

### INV-14 — `CANCELLED`, `NOT_PERFORMED`, `INTERRUPTED` khác nghĩa
Không dùng một state để thay cho ba tình huống này.

### INV-15 — Interruption không tự refund
Execution outcome và financial resolution là hai concern tách nhau.

### INV-16 — Service order có thể retry bằng attempt mới
Một order có thể có attempt #1 interrupted và attempt #2 completed.

### INV-17 — `service.completed` là hoàn thành thật
Không dùng completed để biểu diễn fail/không thực hiện.

### INV-18 — Result lifecycle riêng
`service.completed` không tự tạo nghĩa `result.ready`.

### INV-19 — Core gate synchronous/transactional
Không đợi consumer async mới mở quyền cho bước nghiệp vụ sống còn.

### INV-20 — AI/recommender không bypass Command API
AI không có đường ghi domain state riêng.

---

# 10. State, Event, Work Item, Recommendation — ranh giới

**[CHỐT-TUYỀN]**

```text
STATE
= tình trạng hiện tại
VD: billing=PAID

DOMAIN EVENT
= sự thật đã xảy ra
VD: payment.confirmed

WORK ITEM
= việc có người/role phải chịu trách nhiệm xử lý
VD: "Điều phối lại khách vì phòng SA1 hỏng"

RECOMMENDATION
= đề xuất; chưa tạo business truth
VD: "Nên xếp SA2"

EXECUTION ATTEMPT
= một lần thực tế thử thực hiện service
VD: SA1 start rồi interrupted; SA2 retry rồi completed
```

Không dùng Recommendation như State.  
Không dùng Notification như Domain Event.  
Không dùng Event để thay Work Item ownership.

---

# 11. Service Lifecycle v1 — FREEZE

## 11.1. Phạm vi freeze

**[CHỐT-TUYỀN]**

Từ baseline v0.2, contract domain sau được coi là **Service Lifecycle v1 đã freeze**:

```text
Doctor Order
   ↓
Customer Selection
   ↓
Financial Eligibility
   ↓
Routing
   ↓
Execution Attempt(s)
   ↓
Execution Outcome
   ↓
Result Lifecycle (separate)
```

Bốn trục state:

```text
Selection
Billing
Routing
Execution
```

và các concept:
- selection revision;
- routing revision;
- payment allocation;
- execution attempt;
- command idempotency + optimistic concurrency;
- Work Item khi cần owner xử lý ngoại lệ.

## 11.2. Freeze có nghĩa gì

Freeze nghĩa là:
- AI/kỹ sư **không tự đổi semantics** của các state/event/invariant trên khi implement;
- nếu code hiện tại khác, phải báo impact/conflict;
- thay đổi domain contract cần quyết định mới và tăng version baseline/ADR.

Freeze **không** có nghĩa:
- schema DB đã chốt;
- tên cột/bảng đã chốt;
- migration đã viết;
- API path đã chốt;
- quyền chi tiết đã hoàn tất;
- refund policy đã được PM duyệt;
- runtime/prod đã chạy theo v1.

## 11.3. Năm edge-case đã dùng để kiểm freeze

### Edge 1 — Khách đổi lựa chọn trước thanh toán

**[CHỐT]**
- được xác nhận lại selection;
- giữ nguyên bác sĩ order;
- `NOT_SELECTED` thay cho `DECLINED`;
- tăng `selection_revision`;
- dùng OCC/idempotency.

### Edge 2 — Đã PAID rồi bỏ dịch vụ

**[CHỐT]**
- không rewrite payment;
- service có thể `CANCELLED` nếu chưa start và policy cho phép;
- tài chính đi flow riêng;
- không mutate order cũ thành một service khác;
- payment allocation phải truy được.

**[CÒN MỞ]**
- refund vs credit vs reallocation policy.

### Edge 3 — Phòng assigned bị hỏng/đóng/hết nhân sự

**[CHỐT]**
- `REASSIGNMENT_REQUIRED`;
- `service.routing_invalidated`;
- `AssignServiceRoom` tạo revision mới;
- reroute được trước `IN_PROGRESS`;
- nếu chưa có room mới phải có Work Item/owner.

### Edge 4 — Double-click / hai người cùng Start

**[CHỐT]**
- idempotency key cho retry cùng ý định;
- optimistic version cho stale/concurrent command;
- một successful start per execution attempt;
- loser của command cạnh tranh nhận conflict;
- UI disable không phải safety control.

### Edge 5 — Đã start nhưng không hoàn thành

**[CHỐT]**
- thêm `INTERRUPTED`;
- thêm `Execution Attempt`;
- `service.interrupted`;
- retry bằng attempt mới;
- interruption không tự refund;
- nếu lý do clinical safety, quyết định tiếp theo cần đúng thẩm quyền chuyên môn.

## 11.4. State transition tóm tắt

```text
Selection
PENDING ──confirm──> SELECTED
   └────confirm────> NOT_SELECTED
SELECTED <──────────> NOT_SELECTED
        (chỉ qua flow selection đơn giản khi chưa payment confirmed)

Billing
NOT_REQUIRED
DUE → PENDING_VERIFICATION → PAID
PAID → REFUND_PENDING → REFUNDED
(policy financial resolution còn mở)

Routing
UNASSIGNED → ASSIGNED
ASSIGNED → ASSIGNED                # reroute hợp lệ trước start
ASSIGNED → REASSIGNMENT_REQUIRED
REASSIGNMENT_REQUIRED → ASSIGNED

Execution
PENDING → WAITING
WAITING → IN_PROGRESS → COMPLETED
WAITING → CANCELLED
WAITING → NOT_PERFORMED
IN_PROGRESS → INTERRUPTED

INTERRUPTED
  → resolve/re-route
  → new Execution Attempt
  → IN_PROGRESS
  → COMPLETED
```

Không phải mọi transition trên đều là API trực tiếp; implementation phải đi qua business command + permission + invariant.

---

# 12. Những gì code hiện tại đang khác target

## 12.1. Baseline audit

**[BÁO CÁO-CODE]**

Audit read-only `CLINICAI ARCHITECTURE AUDIT 01` chạy trên:

```text
branch: codex/auto-lot-from-main
HEAD:   0209df61a5b97906cb2d3f6b54e170ead3c13ae9
working tree: DIRTY
```

Do working tree dirty, báo cáo phản ánh filesystem lúc audit, không được coi toàn bộ nội dung là bằng chứng chỉ thuộc đúng commit trên.

## 12.2. Event architecture hiện tại

**[BÁO CÁO-CODE]**

Audit kết luận:
- hệ hiện `event-aware / outbox-lite`;
- `work_item` command + gate + optimistic version + `work_item_event` atomic là nền tốt;
- `record_event(conn, ...)` được dùng transactional trong nhiều flow;
- `event_log` đang mixed concern giữa audit và notification/outbox semantics;
- một boolean `event_published` không phù hợp multi-consumer;
- RabbitMQ path là stub/unused trong prod path được audit;
- AI/Zalo/Analytics hiện mới `PARTLY_COUPLED`, chưa pure subscribe;
- result path còn imperative coupling.

**[CHƯA CHỐT]**

Không refactor event storage/delivery chỉ dựa trên report này. Cần ADR riêng sau khi chốt Domain Event/Audit/Delivery/Realtime model đầy đủ.

## 12.3. Service-order hiện tại

**[BÁO CÁO-CODE]**

Code hiện tại có lifecycle thiên về một trục như:

```text
draft
authorized
assigned
in_progress
performed / not_performed
```

Target v0.2 tách:

```text
Selection
Billing
Routing
Execution
+ Execution Attempt
+ revisions
+ payment allocation
```

Đây là khác biệt domain đáng kể.

**[ĐỀ XUẤT — chưa phải plan triển khai đã duyệt]**

Không big-bang rewrite. Khi implementation:
- giữ entity `service_order` nếu audit không chứng minh cần bỏ;
- thêm/chuẩn hóa state cần thiết;
- map legacy state;
- chuyển read/write path theo slice;
- giữ compatibility trong rollout nếu cần;
- chỉ bỏ legacy field khi read/write/test đã chuyển và migration an toàn.

---

# 13. Những gì CHƯA CHỐT — không được AI tự quyết

## 13.1. External service / đối tác

**[CHƯA CHỐT]**

Cần thiết kế riêng:
- ai thu tiền;
- clinic payment vs partner payment;
- có routing nội bộ không;
- “đã lấy mẫu” khác `service.completed` thế nào;
- kết quả đến sau không được block patient journey ra sao.

Không ép mọi external service vào đúng cùng payment/routing workflow nếu nghiệp vụ không phù hợp.

## 13.2. Refund / credit / reallocation policy

**[CẦN PM/PHÒNG KHÁM]**

Domain đã hỗ trợ financial resolution nhưng chưa chốt:
- hoàn tiền ngay;
- credit khách hàng;
- chuyển sang service khác;
- partial refund;
- ai có quyền approve.

## 13.3. Result lifecycle

**[CHƯA CHỐT]**

Phải quyết định theo từng service:
- received;
- validated;
- ready;
- released;
- sent;
- amended.

Không tự coi mọi service cần tất cả mốc.

## 13.4. Storage của Domain Event / Audit / Delivery

**[CHƯA CHỐT]**

Chưa quyết định:
- tận dụng `event_log` thế nào;
- canonical domain event storage;
- audit storage;
- per-consumer delivery state/cursor/inbox;
- broker có cần hay không.

Định hướng hiện tại:
- Postgres transactional event/outbox trước;
- không cần RabbitMQ/Kafka chỉ để gọi là event-driven.

## 13.5. Schema DB cụ thể

**[CHƯA CHỐT]**

Freeze là domain contract, chưa chọn:
- 4 cột state riêng;
- bảng phụ;
- derived projection;
- execution_attempt table;
- payment allocation table;
- compatibility với legacy `exec_status`;
- migration/backfill.

Cần impact audit usage thật của `service_order`, payment, queue, room, result trước.

## 13.6. Quyền chi tiết

**[CHƯA CHỐT/CẦN PM/BÁC SĨ tùy trường hợp]**

Đã chốt:
- thư ký và điều dưỡng dùng cùng cơ chế điều phối theo policy;
- backend enforce;
- AI không bypass.

Chưa chốt matrix theo:
- vai tài khoản;
- vai vị trí trong ca;
- loại service;
- clinic/room;
- override;
- ai được cancel/refund/retry sau `CLINICAL_SAFETY`.

---

# 14. Coding rules cho AI trong phạm vi baseline

**[CHỐT-TUYỀN]**

1. Không tạo abstraction/framework mới nếu chưa chứng minh có duplicate/responsibility problem thật.
2. Shared mechanism, domain logic tách:
   - PDF renderer dùng chung; document template riêng.
   - reporting primitives dùng chung; business metric definition riêng.
3. Comment ưu tiên **WHY / invariant**, không kể dài lịch sử thay đổi.
4. Lịch sử quyết định dài chuyển vào ADR/docs; code có thể link ADR.
5. Một business rule phải có một implementation authoritative hoặc contract rõ.
6. Không để frontend là nơi duy nhất enforce quyền/invariant.
7. Không để AI tool bypass Command API.
8. Không coi class/file tồn tại là capability production-ready; phải trace runtime.
9. Không sửa code/migration/deploy chỉ vì baseline mô tả target; mỗi slice cần impact audit + plan + test.
10. Khi code khác baseline, báo conflict trước; không silent “fix” business.
11. Service Lifecycle v1 đã freeze: implementation không tự đổi nghĩa `CANCELLED / NOT_PERFORMED / INTERRUPTED`.
12. Không collapse `Selection / Billing / Routing / Execution` thành một status mới chỉ để code ngắn hơn.
13. Retry command phải tách idempotency khỏi concurrency semantics.
14. Recommendation của AI/rule engine không phải authoritative state.

---

# 15. Definition of Done cho một lát cắt thiết kế

Một slice chỉ đủ để giao implementation khi có:

1. **Business truth** — người dùng thực tế muốn gì.
2. **User / screen / button** — ai thao tác ở đâu.
3. **Input / conditions / output**.
4. **State model**.
5. **Commands**.
6. **Domain Events**.
7. **Work Item / owner** nếu có trách nhiệm con người.
8. **Permissions**.
9. **Errors / retry / concurrency**.
10. **Impact map code/data**.
11. **Acceptance tests**.
12. **Rollout/migration** nếu thay data contract.

---

# 16. Source register

Baseline này được tạo/cập nhật từ:

## Nguồn bàn giao / nguyên tắc
- `ClinicAI-CONTEXT-v1.0.md`
  - design-before-code;
  - synchronous cho invariant giao dịch, asynchronous cho việc phụ;
  - transaction + optimistic version + outbox + consumer chống trùng;
  - code hiện tại không tự là business truth.

## Nguồn kiến trúc draft của Quang
- `NGUON-ARTIFACT-QUANG.md`
  - Event là sự thật đã xảy ra, không phải command/status/notification;
  - tách Event / State / Work Item;
  - event-driven có giá trị cho quan sát/phối hợp/học;
  - đây là draft/định hướng, không tự là yêu cầu PM đã duyệt.

## Nguồn review kỹ thuật
- `NGUON-REVIEW-KY-THUAT.md`
  - state/domain event/audit/work item là các khái niệm khác nhau;
  - state + event/outbox cần cùng transaction;
  - retry/consumer cần chống trùng;
  - code/runtime phải kiểm riêng.

## Audit code mới
- `clinicai-architecture-audit-01.md`
  - branch `codex/auto-lot-from-main`;
  - HEAD `0209df61a5b97906cb2d3f6b54e170ead3c13ae9`;
  - working tree DIRTY;
  - event-aware/outbox-lite;
  - `event_log` mixed concern;
  - `event_published` không đủ multi-consumer;
  - work-item command kernel là nền tốt;
  - RabbitMQ path stub/unused theo audit;
  - Lego tests còn partly coupled.

## Quyết định trực tiếp của Tuyền trong phiên thiết kế 22/09/2026
- Chốt 7 luật Domain Event.
- Chốt không Event Source toàn hệ thống.
- Chốt tách Domain Event / Audit / Delivery / Realtime.
- Chốt service flow order → selection → payment → routing → execution.
- Chốt state domain theo Selection / Billing / Routing / Execution.
- Chốt `NOT_SELECTED` thay `DECLINED` cho lựa chọn khách.
- Chốt selection có revision/OCC.
- Chốt payment history immutable và cần allocation tới service/order.
- Chốt thư ký và điều dưỡng dùng cùng command điều phối theo policy.
- Chốt rule engine/AI là recommender; assignment qua Command API.
- Chốt `REASSIGNMENT_REQUIRED` và `service.routing_invalidated`.
- Chốt StartService idempotency + concurrency; exactly-once per execution attempt.
- Chốt `INTERRUPTED` và Execution Attempt.
- Chốt `CANCELLED != NOT_PERFORMED != INTERRUPTED`.
- Chốt interruption không tự refund.
- Chốt `service.completed != result.ready`.
- Chốt Service Lifecycle v1 được freeze ở mức domain contract trong baseline v0.2.

---

# 17. Change log

## v0.2 — 22/09/2026

Nâng từ v0.1 sau khi kiểm state model bằng năm nhóm edge case:

1. Khách đổi lựa chọn trước thanh toán.
2. Khách bỏ service sau khi đã thanh toán.
3. Room assignment mất hiệu lực / reroute.
4. Double-click / retry / concurrent `StartService`.
5. Service đã bắt đầu nhưng bị gián đoạn.

Thay đổi chính:

```text
Selection:
DECLINED → NOT_SELECTED
+ selection_revision

Billing:
+ REFUND_PENDING
+ Payment Allocation concept

Routing:
+ REASSIGNMENT_REQUIRED
+ routing_revision
+ service.routing_invalidated

Execution:
+ INTERRUPTED
+ Execution Attempt
+ service.interrupted

Concurrency:
Start exactly-once per Execution Attempt
+ idempotency
+ optimistic concurrency
```

**Service Lifecycle v1 được FREEZE ở mức domain contract.**

Bước tiếp theo sau baseline này là **impact audit code hiện tại ↔ baseline v0.2**, chưa phải tự động refactor.

## v0.1 — 22/09/2026

Tạo baseline đầu tiên để:
- ngừng phụ thuộc vào lịch sử chat rời rạc;
- làm source of truth thiết kế cho nhiều AI;
- đóng Domain Event contract;
- đóng service lifecycle target ở mức domain;
- ghi rõ các điểm còn mở trước khi code.

---

**Không có code ứng dụng, migration hoặc deploy nào được thực hiện bởi việc tạo/cập nhật tài liệu này.**
