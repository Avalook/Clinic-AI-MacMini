# ClinicAI — EXTENSION ARCHITECTURE v0.1

**Ngày:** 22/09/2026  
**Trạng thái:** Kiến trúc mở rộng đã chốt ở mức nguyên tắc. Các con số hiệu năng trong mục SLO là **đề xuất kỹ thuật cần benchmark ở staging trước khi freeze**.  
**Phạm vi:** AI, automation, Zalo/Facebook và các kênh khác, analytics, facility/room intelligence, module tương lai.  
**Không thay thế:** `ClinicAI-DESIGN-BASELINE-v0.2.md` và Service Lifecycle v1.

> Mục tiêu: ClinicAI có thể mở rộng thành một nền tảng lớn mà không để AI/integration phá core nghiệp vụ, và không làm các thao tác đơn giản của người dùng bị chậm vì phải chờ AI hay hệ thống ngoài.

---

## 1. Luật nền tảng

### EA-01 — Core state chỉ đổi qua Command API
**[CHỐT-TUYỀN]**

AI, Zalo, Facebook, automation, analytics và module ngoài không được UPDATE trực tiếp state nghiệp vụ lõi.

Đường ghi chuẩn:

```text
Actor / AI / Integration
        ↓
Command API
        ↓
Permission + Invariant + Concurrency
        ↓
Core State
        ↓
Domain Event
```

Nếu một capability mới cần thay đổi core state, nó phải dùng command hiện hữu hoặc thêm command mới có contract rõ.

---

### EA-02 — External system đi qua Adapter
**[CHỐT-TUYỀN]**

Mỗi hệ ngoài có adapter riêng:

```text
Zalo      ┐
Facebook  ├→ Adapter → Canonical Message/Event
WhatsApp  │
Website   ┘
```

Core/AI không được phụ thuộc trực tiếp SDK/schema riêng của từng kênh.

Ví dụ các kênh khác nhau có thể quy về:

```text
customer_message.received
conversation_id
channel
sender_ref
occurred_at
content_ref / normalized_content
```

Payload phải tối thiểu, không copy PHI không cần thiết.

---

### EA-03 — Domain Event không biết consumer
**[CHỐT-TUYỀN]**

Core phát sự thật nghiệp vụ; producer không biết AI/Zalo/Analytics nào đang nghe.

Không viết kiểu:

```text
if ai_enabled:
    call_ai(...)
if zalo_enabled:
    send_zalo(...)
```

ngay trong transaction lõi.

Side-effect ngoài core đi qua event/outbox/delivery phù hợp.

---

### EA-04 — AI đọc Context/Projection, không tự join DB tùy ý
**[CHỐT-TUYỀN]**

AI cần trạng thái hiện tại qua các API/projection có quyền:

```text
PatientContext
VisitContext
RoomLoadContext
StaffAvailabilityContext
ConversationContext
FacilityContext
```

Không cho mỗi agent tự viết SQL xuyên 20 bảng.

Mục đích:
- giảm coupling schema;
- kiểm soát PHI/quyền;
- tối ưu hiệu năng;
- tạo một contract ổn định cho AI/harness.

---

### EA-05 — Output AI mặc định là Recommendation hoặc Work Item
**[CHỐT-TUYỀN]**

Mặc định:

```text
AI → Recommendation
AI → Work Item
```

không phải:

```text
AI → UPDATE database
```

Ví dụ routing:

```text
recommended_room = SA2
reason_codes = [LOW_QUEUE, CAPABLE]
confidence = 0.91
```

Người hoặc policy hợp lệ mới gọi:

```text
AssignServiceRoom(...)
```

---

### EA-06 — AI tự động vẫn chịu cùng Command API
**[CHỐT-TUYỀN]**

Nếu sau này policy cho AI tự hành động:

```text
AI Agent
   ↓
Command API
```

AI không có đường đặc quyền.

Nó vẫn phải chịu:
- permission/capability;
- state gate;
- payment gate;
- optimistic concurrency;
- idempotency;
- audit.

Mức tự động hóa là **policy**, không phải một code path riêng.

---

### EA-07 — Mỗi AI capability phải có Harness
**[CHỐT-TUYỀN]**

Mỗi capability AI có tối thiểu:

```text
Input contract
Output contract
Evaluation harness
Version
Metrics
Promotion policy
```

Ví dụ `RoomRoutingAdvisor` đo:
- invalid-room suggestion rate;
- human override rate;
- waiting-time impact;
- reroute rate;
- latency;
- cost.

Không promote model/prompt mới chỉ vì “cảm giác trả lời hay hơn”.

---

### EA-08 — Không self-modify / self-deploy production
**[CHỐT-TUYỀN]**

AI có thể:
- đề xuất code/config/prompt;
- chạy harness trong môi trường cho phép;
- tạo candidate version;
- so sánh với version hiện tại.

Nhưng promotion production phải qua:

```text
evaluation
→ review/policy gate
→ staging
→ smoke/UAT phù hợp
→ production
```

Không cho agent tự sửa core production rồi tự deploy.

---

## 2. Performance Contract — không để AI làm chậm thao tác đơn giản

### PERF-01 — Core fast path không phụ thuộc AI
**[CHỐT-TUYỀN]**

Các thao tác cơ bản như:

```text
mở hàng chờ
bấm Bắt đầu
lưu thông tin
xếp phòng
thu tiền
xem trạng thái
```

không được bắt buộc chờ LLM hoặc API ngoài.

Nếu AI down/chậm:

```text
core workflow vẫn chạy
AI panel có thể chậm / unavailable
```

---

### PERF-02 — Không synchronous fan-out trên một click
**[CHỐT-TUYỀN]**

Một click đơn giản không được đồng bộ gọi hàng loạt:

```text
DB
→ AI
→ Zalo
→ Facebook
→ analytics
→ partner API
```

Core transaction chỉ làm phần cần thiết để business state đúng.

Các side-effect chuyển sang async/outbox khi không phải invariant.

---

### PERF-03 — Recommendation được tính trước khi có thể
**[ĐỀ XUẤT KỸ THUẬT]**

Ví dụ room recommendation không nên đợi người dùng bấm “Xếp phòng” rồi mới bắt đầu gọi AI.

Có thể precompute khi:

```text
service_selection.confirmed
payment.confirmed
room.load_changed
```

UI mở ra đã có:
- state thật;
- recommendation mới nhất nếu còn hợp lệ.

Nếu recommendation cũ/stale, UI vẫn usable và có thể refresh riêng.

---

### PERF-04 — UI trả phản hồi ngay
**[ĐỀ XUẤT KỸ THUẬT]**

Khi người dùng bấm:
- nút đổi loading/disabled gần như ngay;
- không để màn “đứng im” chờ network;
- nếu command lâu, hiển thị trạng thái đang xử lý;
- lỗi phải nói được bước nào thất bại.

AI response có thể stream/render riêng, không chặn dữ liệu chính.

---

### PERF-05 — Read model cho màn nóng
**[CHỐT-TUYỀN ở mức nguyên tắc]**

Các màn đọc nhiều như:
- hàng chờ;
- room load;
- cashier board;
- dashboard điều phối;

không nên mỗi refresh tự join sâu toàn domain nếu đã thành hotspot.

Dùng:
- query/read model tối ưu;
- projection/cache khi cần;
- invalidate theo event/realtime.

Không tạo projection chỉ vì “kiến trúc đẹp”; chỉ tạo khi đo thấy query path cần.

---

### PERF-06 — Timeout + graceful degradation
**[CHỐT-TUYỀN]**

External/AI call phải có timeout.

Nếu AI/Zalo/Facebook lỗi:
- không giữ transaction DB mở chờ;
- ghi delivery/retry state riêng;
- core action đã thành công không bị rollback chỉ vì side-effect ngoài thất bại, trừ khi business rule thật sự yêu cầu.

---

### PERF-07 — Không N+1 / không loop gọi external
**[CHỐT-TUYỀN]**

Không để:
- mỗi row trong bảng gọi thêm 1 API;
- mỗi bệnh nhân gọi LLM riêng trong một lần load dashboard;
- mỗi service gọi external provider tuần tự.

Batch/prefetch/projection khi phù hợp.

---

## 3. SLO ban đầu để benchmark

**[ĐỀ XUẤT — chưa freeze, phải đo trên staging]**

Mục tiêu ban đầu:

```text
UI local feedback sau click:          < 100 ms
Core simple read/write API P95:       < 300 ms backend time
Dashboard/read model P95:             < 800 ms backend time
Core command không phụ thuộc AI:      bắt buộc
AI recommendation panel:              render riêng, không block core
External delivery:                    async/retry khi nghiệp vụ cho phép
```

Không dùng các số này để che latency:
- phải log/trace P50/P95/P99;
- tách DB time / app time / external time;
- endpoint nào vượt budget phải biết nguyên nhân.

Nếu staging thực tế cho thấy budget không hợp lý, chỉnh budget bằng số đo, không bằng cảm giác.

---

## 4. Extension contracts tương lai

Chỉ tạo interface khi có nhu cầu thay thế thực:

```text
RoomAdvisor
MessagingChannel
RecommendationProvider
ResultProvider
PaymentProvider
```

Ví dụ:

```text
RuleBasedRoomAdvisor
AIRoomAdvisor
```

Core chỉ phụ thuộc contract, không phụ thuộc vendor/model.

Không dựng plugin framework tổng quát từ bây giờ.

---

## 5. AI Decision Trace

**[CHỐT-TUYỀN ở mức nguyên tắc]**

Mỗi recommendation/action quan trọng của AI cần lưu đủ để audit:

```text
capability
model/provider/version
policy/prompt version
context snapshot/hash
recommendation
reason_codes
confidence (nếu có nghĩa)
accepted/rejected/by whom
command/result reference
timestamps
```

Không cần lưu private chain-of-thought.

Mục đích:
- audit;
- harness;
- đo override;
- so model version;
- điều tra sự cố.

---

## 6. Ranh giới dữ liệu

**[CHỐT-TUYỀN]**

AI chỉ nhận dữ liệu cần cho nhiệm vụ.

Ví dụ routing thường cần:

```text
service capability
room availability
queue load
staff availability
patient constraints cần thiết
```

không mặc định cần:

```text
toàn bộ bệnh án
CCCD
số điện thoại
mọi ghi chú lâm sàng
```

Context API chịu trách nhiệm cắt dữ liệu theo capability/quyền.

---

## 7. Kiến trúc tổng quát

```text
                    External World
           Zalo / Facebook / Partner / IoT
                         │
                      Adapters
                         │
             Canonical Events / Messages
                         │
          ┌──────────────┴──────────────┐
          │                             │
     Context/Projection             Event Stream
          │                             │
          └──────────── AI / Rules ─────┘
                         │
             Recommendation / Work Item
                         │
                  Policy / Human
                         │
                     Command API
                         │
                     Core Domain
                         │
                  Domain Event/Outbox
```

---

## 8. Definition of Done cho capability AI/integration mới

Một capability mới chỉ đủ để merge khi có:

1. input contract;
2. output contract;
3. permission/capability;
4. failure behavior;
5. timeout;
6. idempotency nếu có action;
7. audit/decision trace;
8. harness/tests;
9. latency measurement;
10. không làm chậm core fast path ngoài budget;
11. fallback khi provider unavailable;
12. PHI minimization.

---

## 9. Điều cố ý KHÔNG làm ở v0.1

Chưa làm:
- microservices;
- Kafka/RabbitMQ như requirement;
- event sourcing;
- generic plugin marketplace;
- AI tự deploy production;
- AI tự update DB;
- một “super agent” có toàn quyền;
- projection cho mọi bảng;
- interface cho mọi service.

Chỉ dựng **seam** đủ tốt để mở rộng an toàn.

---

## 10. Quan hệ với code hiện tại

**[BÁO CÁO-CODE]**

Audit `codex/auto-lot-from-main@0209df61…` cho thấy:
- `LuotKhamService` đang ôm nhiều concern;
- router tương đối mỏng;
- `luot_kham_rules.py` là nền pure-rule tốt;
- payment/refund/work-item/config đã tách tương đối;
- event/outbox hiện mới ở mức `event-aware / outbox-lite`;
- RabbitMQ path chưa là runtime truth;
- routing recommender logic `_tu_xep_phong()` đã có thể tái sử dụng.

Do đó strategy là:
- tách module dần trong lúc implement v0.2;
- giữ modular monolith;
- không rewrite.

---

## 11. Change log

### v0.1 — 22/09/2026
- chốt extension seams cho AI/integration;
- chốt Command API là đường ghi core;
- chốt Context/Projection là đường đọc AI;
- chốt Recommendation/Work Item là output mặc định;
- chốt harness/promotion gate;
- thêm Performance Contract để AI/integration không làm chậm core path;
- thêm SLO ban đầu ở trạng thái đề xuất, chờ benchmark staging.

**Không có code, migration hoặc deploy nào được thực hiện khi tạo tài liệu này.**
