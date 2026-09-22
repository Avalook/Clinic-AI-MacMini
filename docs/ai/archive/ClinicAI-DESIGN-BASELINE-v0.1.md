# ClinicAI — DESIGN BASELINE v0.1

**Ngày:** 22/09/2026  
**Trạng thái:** Baseline thiết kế đang hiệu lực cho các mục đã đánh dấu **[CHỐT-TUYỀN]**.  
**Mục đích:** Làm nguồn thiết kế chung để Tuyền, ChatGPT, Claude, Grok/Night Shift, Antigravity/Codex và các AI khác cùng hiểu **một target behavior**, thay vì suy từ code hiện tại hoặc lịch sử chat rời rạc.

> Baseline này **không tự thay thế** phê duyệt chuyên môn của bác sĩ, xác nhận phạm vi của PM, hoặc bằng chứng runtime/staging/production.  
> Code hiện tại là **implementation evidence**, không phải business truth.

---

## 0. Cách dùng baseline này

Mọi AI / kỹ sư trước khi thiết kế hoặc sửa code cho phần liên quan phải đọc theo thứ tự:

1. `ClinicAI-DESIGN-BASELINE-v0.1.md` — target behavior đã chốt trong phạm vi tài liệu này.
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

## 5.1. Không ép vào một status duy nhất

**[CHỐT-TUYỀN — domain model]**

Một `service_order` được nhìn theo bốn trục độc lập:

### A. Selection

```text
PENDING
SELECTED
DECLINED
```

- `PENDING`: bác sĩ đã chỉ định; khách chưa xác nhận.
- `SELECTED`: khách đồng ý thực hiện.
- `DECLINED`: khách không/chưa thực hiện dịch vụ đó trong lựa chọn hiện tại.

### B. Billing

```text
NOT_REQUIRED
DUE
PENDING_VERIFICATION
PAID
REFUNDED
```

- `NOT_REQUIRED`: phòng khám không cần thu khoản này.
- `DUE`: cần thanh toán.
- `PENDING_VERIFICATION`: QR/chuyển khoản đang chờ xác minh.
- `PAID`: thanh toán đã được xác nhận.
- `REFUNDED`: khoản tương ứng đã được hoàn.

### C. Routing

```text
UNASSIGNED
ASSIGNED
```

- `UNASSIGNED`: chưa chốt phòng.
- `ASSIGNED`: đã chốt phòng thực hiện.

### D. Execution

```text
PENDING
WAITING
IN_PROGRESS
COMPLETED
NOT_PERFORMED
CANCELLED
```

- `PENDING`: chưa vào hàng thực hiện.
- `WAITING`: đang chờ tại service/phòng.
- `IN_PROGRESS`: đang thực hiện.
- `COMPLETED`: đã thực hiện xong.
- `NOT_PERFORMED`: đã tới bước thực hiện nhưng không làm được.
- `CANCELLED`: dịch vụ bị hủy trước khi thực hiện.

> Đây là **domain model**, chưa đồng nghĩa database phải ngay lập tức có đúng 4 cột enum này.

## 5.2. Trạng thái điển hình

### Sau khi bác sĩ chỉ định

```text
selection = PENDING
billing   = chưa phát sinh nghĩa vụ
routing   = UNASSIGNED
execution = PENDING
```

### Sau khi khách chọn

```text
selection = SELECTED
billing   = DUE hoặc NOT_REQUIRED
routing   = UNASSIGNED
execution = PENDING
```

### Sau khi thanh toán hợp lệ

```text
selection = SELECTED
billing   = PAID
routing   = UNASSIGNED
execution = PENDING
```

### Sau khi chốt phòng

```text
selection = SELECTED
billing   = PAID / NOT_REQUIRED
routing   = ASSIGNED
execution = WAITING
```

### Khi bắt đầu dịch vụ

```text
execution = IN_PROGRESS
```

### Khi kết thúc

```text
execution = COMPLETED
```

hoặc:

```text
execution = NOT_PERFORMED
```

---

# 6. Command model của lát cắt

**[CHỐT-TUYỀN — tên command có thể thay khi map code, semantics không thay]**

## 6.1. `CreateServiceOrders`

Người khởi tạo: bác sĩ theo policy chuyên môn.

Tác dụng:
- tạo một hoặc nhiều `service_order`;
- không tự coi khách đã chọn;
- không tự coi đã thanh toán;
- không tự đưa vào phòng.

Sau thành công phát:

```text
service.ordered
```

Mỗi `service_order` có event riêng. Nhiều order từ một thao tác có thể dùng cùng `correlation_id`.

## 6.2. `ConfirmServiceSelection`

Người thao tác: nhân sự phù hợp ghi nhận quyết định khách; quyền chi tiết còn cần map với vận hành thực tế.

UI có thể tick/un-tick thoải mái trước khi xác nhận; draft UI không phát Domain Event.

Sau xác nhận:
- order được chọn → `SELECTED`;
- order không chọn → `DECLINED` hoặc trạng thái tương đương theo migration cuối cùng.

Phát:

```text
service_selection.confirmed
```

Một event đại diện cho **một lần khách xác nhận lựa chọn**, có thể mang danh sách selected/not-selected order IDs.

## 6.3. `ConfirmPayment`

Người thao tác: actor có quyền thu/xác minh thanh toán.

Backend phải xác minh:
- đúng visit/patient;
- đúng tập dịch vụ;
- bill/current pricing;
- phương thức;
- điều kiện xác minh chuyển khoản/QR;
- chống double-process.

Sau thành công phát:

```text
payment.confirmed
```

**[CHỐT-TUYỀN]** Payment phải truy được chính xác những `service_order` nào được khoản thanh toán đó cover. Không chỉ lưu tổng tiền theo visit rồi suy ngược.

## 6.4. `AssignServiceRoom`

**[CHỐT-TUYỀN]**

Thư ký **hoặc** điều dưỡng có thể dùng cùng một command điều phối nếu policy/ca làm việc hiện hành cho phép.

Không tạo hai đường backend khác nhau theo role.

Backend phải kiểm:
- actor có quyền điều phối;
- phòng active;
- phòng làm được service đó;
- service đã đủ điều kiện để đi làm;
- service chưa `IN_PROGRESS`;
- các invariant liên quan khác.

Sau thành công:
- `routing = ASSIGNED`;
- có `room_id`;
- execution đi vào `WAITING` khi các gate đã thỏa.

Phát:

```text
service.routed
```

## 6.5. `StartService`

Backend kiểm tối thiểu:
- khách đã `SELECTED`;
- payment gate thỏa (`PAID` hoặc `NOT_REQUIRED`);
- room/routing hợp lệ nếu service cần phòng;
- actor có quyền;
- không đã bắt đầu/xong.

Sau thành công:
- `execution = IN_PROGRESS`;
- ghi `started_at`, actor thực hiện.

Phát:

```text
service.started
```

## 6.6. `CompleteService`

Sau thành công:
- `execution = COMPLETED`;
- ghi thời gian/người thực hiện theo contract.

Phát:

```text
service.completed
```

Nếu không làm được, không dùng `completed + performed=false`. Dùng business path riêng:

```text
service.not_performed
```

---

# 7. Domain Event catalogue đang chốt cho lát cắt

**[CHỐT-TUYỀN]**

Happy path:

```text
service.ordered
service_selection.confirmed
payment.confirmed
service.routed
service.started
service.completed
```

Terminal/exception path đã nhận diện:

```text
service.not_performed
```

Lifecycle khác:

```text
result.ready
```

`result.ready` **không** đồng nghĩa `service.completed`.

Ví dụ:
- siêu âm có thể completed 10:15, result ready 10:17;
- xét nghiệm ngoài có thể phần thực hiện/lấy mẫu xong hôm nay, result ready hai ngày sau.

**[CHƯA CHỐT]**
Các event chi tiết khác của result lifecycle như:
`result.received`, `result.validated`, `result.released`, `result.sent`.

---

# 8. Routing: người, rule engine và AI

## 8.1. Recommendation không phải authoritative state

**[CHỐT-TUYỀN]**

Hệ thống có thể gợi ý phòng theo:
- phòng làm được service;
- phòng active;
- nhân sự phù hợp;
- tải/hàng chờ;
- điều kiện bệnh nhân;
- policy khác.

Gợi ý có thể đổi theo thời gian nên:

```text
room recommendation ≠ service state
```

Không cần tạo canonical Domain Event kiểu `room.suggested` cho hành trình bệnh nhân.

## 8.2. Người xác nhận

**[CHỐT-TUYỀN]**

Hiện tại:
- thư ký có thể chọn/chốt phòng;
- điều dưỡng có thể chọn/chốt phòng;
- tất cả đi qua cùng `AssignServiceRoom`.

Quyền cụ thể phải do backend policy kiểm, không chỉ ẩn/hiện nút frontend.

## 8.3. AI sau này

**[CHỐT-TUYỀN]**

AI có thể thay/góp phần vào recommender:

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

AI **không UPDATE state trực tiếp**.

Nếu sau này cho auto-routing, policy/system vẫn gọi `AssignServiceRoom` chuẩn và chịu cùng invariant như con người.

---

# 9. Invariants đang chốt

**[CHỐT-TUYỀN]**

### INV-01
`service.ordered` không đồng nghĩa khách sẽ làm.

### INV-02
Service không được vào execution thực sự nếu selection chưa `SELECTED`.

### INV-03
Nếu service cần phòng khám thu tiền, không được `StartService` trước khi billing thỏa điều kiện thanh toán.

### INV-04
Dịch vụ `NOT_REQUIRED` có thể bỏ qua payment gate.

### INV-05
Room suggestion không thay state; chỉ assignment thành công mới tạo `service.routed`.

### INV-06
Khi service đã `IN_PROGRESS`, không được đổi phòng bằng thao tác routing bình thường.

### INV-07
`service.completed` luôn có nghĩa dịch vụ đã thực hiện xong; không dùng completed để biểu diễn “không làm được”.

### INV-08
`service.completed` không tự tạo nghĩa `result.ready`.

### INV-09
Gate sống còn của core workflow phải synchronous/transactional. Không đợi một consumer async mới mở quyền thực hiện dịch vụ.

Ví dụ KHÔNG được:

```text
payment.confirmed event
  → worker xử lý vài giây sau
  → mới set service đủ điều kiện thực hiện
```

Payment command phải commit một state đủ nhất quán để gate thực hiện kiểm ngay được.

### INV-10
AI/recommender không bypass các invariant ở Command API.

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
VD: "Đưa khách tới phòng siêu âm", "Xử lý khách chờ quá SLA"

RECOMMENDATION
= đề xuất; chưa tạo business truth
VD: "Nên xếp SA2"
```

Không dùng Recommendation như State.  
Không dùng Notification như Event.  
Không dùng Event để thay Work Item ownership.

---

# 11. Những gì code hiện tại đang khác target

## 11.1. Baseline audit

**[BÁO CÁO-CODE]**

Audit read-only `CLINICAI ARCHITECTURE AUDIT 01` chạy trên:

```text
branch: codex/auto-lot-from-main
HEAD:   0209df61a5b97906cb2d3f6b54e170ead3c13ae9
working tree: DIRTY
```

Do working tree dirty, báo cáo phản ánh filesystem lúc audit, không được coi toàn bộ nội dung là bằng chứng chỉ thuộc đúng commit trên.

## 11.2. Event architecture hiện tại

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

## 11.3. Service-order hiện tại

**[BÁO CÁO-CODE]**

Code hiện tại có lifecycle thiên về một trục như:

```text
draft
authorized
assigned
in_progress
performed / not_performed
```

Target baseline tách rõ:

```text
Selection
Billing
Routing
Execution
```

Đây là khác biệt domain đáng kể.

**[ĐỀ XUẤT]**
Không big-bang rewrite. Khi triển khai, ưu tiên migration tương thích:
- giữ entity `service_order`;
- thêm/chuẩn hóa state cần thiết;
- map legacy state;
- đổi write path theo slice;
- chỉ bỏ legacy field khi toàn bộ read/write/test đã chuyển và có rollout an toàn.

---

# 12. Những gì CHƯA CHỐT — không được AI tự quyết

## 12.1. Đường ngược / edge cases

**[CHƯA CHỐT]**

Phải xử lý trước khi freeze service lifecycle v1:

1. Khách đổi lựa chọn trước thanh toán.
2. Khách đổi ý sau khi đã thanh toán.
3. Refund một phần / toàn phần.
4. Phòng đã assigned nhưng hỏng/đóng/không còn nhân sự.
5. Re-route trước `IN_PROGRESS`.
6. Double click / retry `StartService`.
7. Hai người cùng `StartService`.
8. Dịch vụ đã bắt đầu nhưng không làm được.
9. Cancel khác `NOT_PERFORMED` thế nào.
10. Dịch vụ bên ngoài: ai thu tiền, ai làm, có cần room/routing nội bộ không.

## 12.2. Result lifecycle

**[CHƯA CHỐT]**

Phải quyết định các mốc thật sự có nghĩa:
- received;
- validated;
- ready;
- released;
- sent;
- amended.

Không tự coi mọi dịch vụ cần tất cả các mốc.

## 12.3. Storage của Domain Event / Audit / Delivery

**[CHƯA CHỐT]**

Chưa quyết định:
- tận dụng `event_log` thế nào;
- có bảng canonical domain event riêng không;
- audit lưu riêng hay chung với semantics rõ hơn;
- per-consumer delivery table/cursor/inbox;
- broker có cần hay không.

Định hướng hiện tại: Postgres transactional event/outbox trước, **không cần RabbitMQ/Kafka chỉ để gọi là event-driven**.

## 12.4. Schema DB cụ thể

**[CHƯA CHỐT]**

Bốn trục state là domain truth, nhưng chưa chốt:
- 4 cột riêng;
- bảng phụ;
- derived projection;
- compatibility với `exec_status`;
- migration/backfill.

Cần audit usage của `service_order` trước khi chọn schema.

## 12.5. Quyền chi tiết

**[CHƯA CHỐT/CẦN PM nếu ảnh hưởng phạm vi]**

Đã chốt nguyên tắc:
- thư ký và điều dưỡng đều có thể dùng cơ chế điều phối nếu policy cho phép;
- cùng một command backend.

Chưa chốt matrix hoàn chỉnh theo:
- role tài khoản;
- vai vị trí trong ca;
- loại service;
- cơ sở/phòng;
- override/trưởng ca/quản lý.

---

# 13. Coding rules cho AI trong phạm vi baseline

**[CHỐT-TUYỀN]**

Khi sau này giao code:

1. Không tạo abstraction/framework mới nếu chưa chứng minh có duplicate/responsibility problem thật.
2. Shared mechanism, domain logic tách:
   - PDF renderer dùng chung; từng document template riêng.
   - reporting primitives dùng chung; business metric definition riêng.
3. Comment ưu tiên **WHY / invariant**, không kể dài lịch sử thay đổi.
4. Lịch sử quyết định dài chuyển vào ADR/docs; code có thể link ADR.
5. Một business rule phải có một implementation authoritative hoặc một contract rõ ràng.
6. Không để frontend là nơi duy nhất enforce quyền/invariant.
7. Không để AI tool tự bypass Command API.
8. Không coi class/file tồn tại là capability production-ready; phải trace runtime.
9. Không sửa code/migration/deploy chỉ vì baseline mô tả target; mỗi slice cần impact audit + plan + test.
10. Khi code khác baseline, báo conflict trước, không silent “fix” business.

---

# 14. Definition of Done cho một lát cắt thiết kế

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

# 15. Source register

Baseline này được tạo từ:

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
  - event-driven có giá trị để quan sát/phối hợp/học;
  - đây là nguồn định hướng/draft, không tự là yêu cầu PM đã duyệt.

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
- Chốt tách khái niệm Domain Event / Audit / Delivery / Realtime.
- Chốt service flow: order → selection → payment → routing → execution.
- Chốt state domain theo 4 trục Selection / Billing / Routing / Execution.
- Chốt thư ký và điều dưỡng có thể cùng dùng một command điều phối theo policy.
- Chốt máy/rule engine gợi ý, người xác nhận; AI sau này là recommender, không bypass command.
- Chốt `service.routed` là Domain Event; room suggestion không phải canonical Domain Event.
- Chốt `service.completed != result.ready`.

---

# 16. Change log

## v0.1 — 22/09/2026

Tạo baseline đầu tiên để:
- ngừng phụ thuộc vào lịch sử chat rời rạc;
- làm source of truth thiết kế cho nhiều AI;
- đóng Domain Event contract;
- đóng service lifecycle target ở mức domain;
- ghi rõ các điểm còn mở trước khi code.

**Không có code, migration hoặc deploy nào được thực hiện bởi việc tạo tài liệu này.**
