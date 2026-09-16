# -*- coding: utf-8 -*-
"""Lớp 2 — KIẾN TRÚC EVENT-DRIVEN: Care Model v1 + Event Catalog v1 +
Work Item Protocol v1 + Experience State Spec v1."""

L = 2

NODES = [
{
 "id": "event-first-dao-nhan-qua", "layer": L, "order": 300,
 "title": "Event-first — đảo thứ tự nhân quả, và bài kiểm 'xoá dashboard dựng lại được không'",
 "tag": "Care Model §1–2",
 "summary": "Ba luận đề của Care Model (architectural, human) và định nghĩa 'event-driven' ở ba cấp độ.",
 "body": """
Ba luận đề mở đầu Care Model:

> «**Core thesis:** Reality không được "nhập vào một trạng thái". Reality biểu lộ qua các sự kiện.» · «**Architectural thesis:** Event stream là bằng chứng gốc của hoạt động. Encounter state, Patient Journey, Experience State, work queue, dashboard và analytics là các projection được dựng từ cùng một dòng bằng chứng.» · «**Human thesis:** Event-driven không nhằm biến phòng khám thành máy. Nó giúp hệ thống nhận phần việc "nhớ, theo dõi, nối ngữ cảnh và phát hiện quên sót", để con người dành sự chú ý cho chăm sóc và phán đoán.»

> «Điểm khác biệt không nằm ở việc có Kafka, queue hay webhook. Nó nằm ở **nguồn sự thật và mô hình nhân quả**.» — *§1*

Ba cấp độ không được trộn (*§2*):

| Cấp độ | Ý nghĩa | Áp dụng |
|---|---|---|
| Event notification | Một module báo cho module khác rằng có thay đổi | «Dùng cho integration đơn giản, nhưng **không đủ làm domain model**» |
| Event-driven architecture | Các thành phần phản ứng bất đồng bộ với event | «Nền tảng cho orchestration, projection và automation» |
| Event sourcing | Event log là lịch sử chuẩn; state được fold/replay từ event | «Áp dụng có chọn lọc cho domain cần temporal truth và audit mạnh» |

> «ClinicAI theo hướng **event-driven architecture + selective event sourcing**.» — *§2*

Domain phải event-centric (*§2*): Encounter · Work Item · Journey/process execution · handoff và acknowledgement · communication · escalation · Experience State derivation · resource load và operational exceptions. Còn «Patient profile, staff directory, service catalog hay cấu hình tĩnh có thể dùng CRUD với audit log.»

### Code đang ở cấp độ nào

Cấp độ **1 — event notification**, làm khá tốt: `notify_row_change()` → `pg_notify('clinicai_changes')` → `ChangeBroker` → SSE ([[realtime-sse]]). Nhưng tin "cố ý nghèo" (chỉ tên bảng + clinic_id) nên nó là *notification*, không phải domain event — đúng như thesis phân loại.

Cấp độ **2** chỉ có một consumer thật: `notification_relay.py` đọc `event_log` gửi Telegram. Không projector, không policy consumer.

Cấp độ **3**: không có. Không domain nào fold state từ event.

Vì vậy điều quan trọng nhất của [[tk-nguyen-tac]]: không chọn "full event sourcing" (§20.6 cấm), mà **đưa 4 domain lên cấp 2–3**: Encounter (visit), Work Item, Communication, Expectation — đúng danh sách §2, và đúng Luật 7.1 (chỉ Postgres).
""",
 "links": ["vong-lap", "selective-event-sourcing", "realtime-sse", "notification-relay", "tk-nguyen-tac", "anti-patterns"],
},
{
 "id": "5-loai-event", "layer": L, "order": 310,
 "title": "Năm loại event — Observed · Domain · Derived · Decision · Outcome",
 "tag": "Care Model §3 · Catalog §4",
 "summary": "Phân loại theo nguồn và vai trò; Derived phải ghi độ chắc chắn, không được giả dạng Observed.",
 "body": """
Quy tắc đặt tên (*Care Model §3.1*): «Một domain event phải được viết ở thì quá khứ và có ý nghĩa nghiệp vụ rõ ràng. […] Tên tốt: LabResultReady · Tên yếu: LabResultUpdated · Tên sai nghĩa: SendLabResult.»

> «Ontology truyền thống thường bắt đầu bằng danh từ: Patient, Appointment, Encounter, Task. ClinicAI vẫn cần các entity này, nhưng event-driven model bắt đầu bằng **động từ đã xảy ra**.» — *§3.2*

| Loại | Nguồn | Ví dụ | Vai trò |
|---|---|---|---|
| **Observed** | Cảm biến, thao tác, hệ thống nguồn | PatientArrived, DoorOpened, LabResultReceived | Bằng chứng trực tiếp về reality |
| **Domain** | Domain service xác nhận ý nghĩa nghiệp vụ | EncounterStarted, SpecimenAccepted | Sự thật có nghĩa trong ClinicAI |
| **Derived** | Rule, temporal engine hoặc AI suy ra | UnexplainedWaitRiskDetected, StaffOverloadDetected | Biến tín hiệu thành điều cần chú ý |
| **Decision** | Policy/human/AI có thẩm quyền | EscalationApproved, RoutingDecisionMade | Lưu dấu quyết định và lý do |
| **Outcome** | Người hoặc hệ thống thực hiện | PatientInformed, ReviewCompleted | Chứng minh vòng lặp đã đóng |

> «Một Derived Event phải ghi rõ mức độ chắc chắn. Nó không được giả dạng Observed Event.» — *§3.3*

Catalog §4 thêm loại thứ sáu: **Reliability** — «Khả năng quan sát/hoạt động của hệ thống thay đổi», ví dụ IntegrationUnavailable.

### Phân loại 17 loại event đang có trên prod

| Loại code | Số | Xếp vào | Ghi chú |
|---|---|---|---|
| `slot_hold.created/released` | 281 | *Không phải domain event* | Là giữ chỗ UI 10 phút (Luật 6.1 «tư vấn, không phải khoá»). Catalog §14: «UI analytics event có thể tồn tại ở telemetry riêng, không trộn vào domain event ledger.» |
| `appointment.created/rescheduled/checked_in/completed` | 69 | Domain | Tên snake_case theo thì quá khứ — đúng tinh thần, chỉ khác quy ước chữ. |
| `patient.created/phone_*` | 69 | Domain (CRUD+audit) | Đúng §7: master data chỉ cần audit. |
| `cskh.tuong_tac` / `_hoan_tac` | 22 | **Outcome** (TRA_KQ, XAC_NHAN_LICH) hoặc Observed (mốc quầy) | Gần PatientInformed nhất trong code. |
| `dispatch.checkin/checkout` | 2 | Observed | Vị trí, nguồn `staff`. |
| `thong_bao.*` | 2 | *Command/notification* | Catalog §14: «NotificationCreated nếu điều cần biết là communication request» → không phê duyệt. |
| `roster.*` | 4 | Resource | Đúng §12 Catalog (ShiftStarted…). |

Không có **Derived**, không có **Decision**, không có **Reliability** event nào. Đây là bằng chứng số cho [[gap-envelope]] và lý do [[tk-event-catalog-table]] cần cột `category` + `evidence_level`.
""",
 "links": ["event-vs-record", "event-envelope", "event-catalog", "gap-envelope", "tk-event-catalog-table", "event-log-table"],
},
{
 "id": "bat-dang-thuc", "layer": L, "order": 320,
 "title": "Sáu bất đẳng thức — NotificationSent ≠ PersonInformed",
 "tag": "Care Model §4 · Catalog §2.4 · Work Item §8",
 "summary": "Các khái niệm không được đồng nhất; 'sent = done' là lỗi nguy hiểm nhất của workflow software.",
 "body": """
Bảng khái niệm (*Care Model §4*):

| Khái niệm | Câu hỏi | Ví dụ |
|---|---|---|
| Event | Điều gì đã xảy ra? | LabResultReady |
| Command | Ta muốn ai/hệ thống làm gì? | RequestDoctorReview |
| State | Ta đang tin điều gì là đúng ở thời điểm này? | Encounter.awaiting_review |
| Work Item | Công việc có ownership nào phải được hoàn tất? | "BS Lan review kết quả trước 11:10" |
| Notification | Tín hiệu nào được gửi tới một người? | Push notification đã gửi |
| Outcome | Reality có thực sự thay đổi không? | Bác sĩ đã review; bệnh nhân đã được giải thích |

> «Các bất đẳng thức bắt buộc: NotificationSent ≠ PersonInformed · WorkAssigned ≠ WorkAcknowledged · WorkAcknowledged ≠ WorkCompleted · CommandAccepted ≠ ActionCompleted · MessageDelivered ≠ MessageUnderstood · ProjectedState ≠ SourceEvent. ClinicAI không được "đóng vòng" chỉ vì đã gửi thông báo hoặc ghi một status.» — *§4*

Work Item Protocol §8 thêm: «MessageSent ≠ PatientInformed · ResultOpened ≠ ResultReviewed · WorkStarted ≠ WorkCompleted · **CheckboxTicked ≠ OutcomeObserved**.»

### Nơi code đang vi phạm — chỉ đích danh

1. **`event_published = TRUE` sau khi Telegram nhận** (`notification_relay.py`, `_mark_published`). Cờ này vừa là "đã lên hàng chờ" (`event_service.py` §Outbox pattern bước 4) vừa là "đã gửi" — ADR-0002 đã gọi tên «hai nghĩa». Không có chỗ nào cho *đã đọc*, càng không cho *đã hiểu*.
2. **Template thiếu → đánh dấu đã xử lý**: `if message is None: await _mark_published(...)` — sự kiện không có mẫu tin bị coi là xong. Thesis §15.6: «event lỗi schema được quarantine, không âm thầm bỏ».
3. **`thong_bao.da_doc_luc` ≠ `da_xu_ly_luc`** — code làm **đúng** bất đẳng thức này, có docstring giải thích: «ĐỌC ≠ ĐÃ XỬ LÝ, và đó là cả lý do có hai cột.» Đây là mẫu tốt để nhân rộng.
4. **`work_item_event` chỉ có `create`** trên prod; và Command API không có `acknowledge` — nên WorkAssigned ≠ WorkAcknowledged **không thể** vi phạm vì chưa tồn tại cả hai.
5. **`TRA_KQ` là attestation** — `tuong_tac_cskh_service.ghi()` bắt `ket_qua == 'DA_LIEN_HE'` mới cho ghi loại này: «Một cuộc gọi hụt vẫn không được mang nhãn đã trả kết quả». Đây là *structured attestation* đúng nghĩa Work Item §8 — giữ nguyên trong [[tk-communication-delivery]].
""",
 "links": ["notification-relay", "thong-bao", "tuong-tac-cskh", "gap-communication", "tk-communication-delivery", "work-item-commitment"],
},
{
 "id": "event-envelope", "layer": L, "order": 330,
 "title": "Event envelope chuẩn — 17 trường, mỗi trường một vai",
 "tag": "Care Model §5 · Catalog §3",
 "summary": "Bao thư bắt buộc trước khi có hàng trăm loại event; đối chiếu từng trường với 14 cột event_log hiện tại.",
 "body": """
Nguyên văn (*Care Model §5*):

```json
{
  "event_id": "evt_01...",           "event_type": "LabResultReady",
  "schema_version": 1,
  "occurred_at": "2026-09-03T10:18:42+07:00",
  "recorded_at": "2026-09-03T10:18:44+07:00",
  "source":  {"type": "LIS", "id": "lis_main"},
  "actor":   {"type": "system", "id": "lis_main"},
  "subject": {"type": "lab_result", "id": "lr_2841"},
  "patient_id": "pat_...", "episode_id": "epi_...", "encounter_id": "enc_...",
  "correlation_id": "cor_...", "causation_id": "evt_...",
  "stream_id": "enc_enc_...", "stream_version": 27,
  "evidence_level": "observed", "confidence": 1.0,
  "privacy_tags": ["clinical", "sensitive"],
  "payload": {}
}
```

> «occurred_at: lúc reality xảy ra · recorded_at: lúc ClinicAI biết · correlation_id: nối toàn bộ một vòng nghiệp vụ · causation_id: event/command nào gây ra event này · stream_version: bảo vệ thứ tự và optimistic concurrency · evidence_level: observed, inferred hoặc self-reported · confidence: bắt buộc với suy luận · schema_version: cho phép nâng cấp event an toàn · privacy_tags: giúp áp policy truy cập, retention và export.» — *§5*

Catalog §3 nói bắt buộc với mọi event: event_id/type/schema_version · occurred/recorded · source/actor/subject · correlation/causation khi có · stream_id/version · evidence_level · privacy classification · payload tối thiểu.

### Đối chiếu `event_log` prod (14 cột, đo 05/09/2026)

| Trường thesis | Cột hiện có | Dùng thật? |
|---|---|---|
| event_id, event_type | `event_id`, `event_type` | ✅ |
| schema_version | `event_version` | 1 giá trị duy nhất trên 449 dòng |
| occurred_at, recorded_at | `occurred_at`, `recorded_at` | có cả hai, nhưng **bằng nhau ở 100% dòng** vì cùng `DEFAULT now()` và đường ghi truyền `now()` — chưa ai truyền mốc thật (max chênh 0s) → chưa bao giờ ghi trễ/ghi bù |
| source | `source` (text: `api:booking`, `cskh.customers`…) | ✅ nhưng là chuỗi tự do, 12 giá trị |
| actor | `metadata.actor_auth_user_id / clinic_staff_id / clinic_role` (JSON) | 424/449 có `clinic_staff_id` — nhưng chìm trong JSON, «không truy vấn hay ràng buộc được» (DANG-LAM §4, PR #8) |
| subject | `aggregate_type` + `aggregate_id` | ✅ tương đương |
| patient_id / episode_id / encounter_id | — | ❌ chỉ suy được qua join `aggregate_id` |
| correlation_id, causation_id | có cột | **0/449** từng khác NULL |
| stream_id, stream_version | — | ❌ |
| evidence_level, confidence | — | ❌ |
| privacy_tags | — | ❌ (có `event-log-redaction.ts` phía dashboard, không ở ledger) |
| payload | `payload` | ✅ «cố ý chỉ mang ID» (`notification_relay._lam_giau` docstring) — đúng §17 data minimization |

Kết luận: **9/17 có chỗ, 5/17 có cột nhưng chưa dòng nào điền tại thời điểm đo, 6/17 thiếu hẳn.** Migration cộng thêm là đủ — [[tk-event-envelope-v2]].
""",
 "links": ["event-log-table", "gap-envelope", "tk-event-envelope-v2", "stream-boundary", "governance-event"],
},
{
 "id": "stream-boundary", "layer": L, "order": 340,
 "title": "Năm stream — Encounter · Work Item · Episode · Resource · Communication",
 "tag": "Care Model §6",
 "summary": "Event phải thuộc một stream có ownership và invariant; không có 'global stream' vô cấu trúc.",
 "body": """
> «Không nên tạo một "global stream" vô cấu trúc rồi mong analytics tự hiểu. Event cần được tổ chức theo stream có ownership và invariant.» — *§6*

| Stream | Nội dung (thesis) | Khoá tự nhiên trong code | Đang ghi ở đâu |
|---|---|---|---|
| **Encounter** | check-in · node · order/result · handoff · delay · completion · cancellation · checkout | `visit.visit_id` | `event_log` (`dispatch.*`, `visit.checkin`), `work_item_event`, `visit_route` |
| **Work Item** | created · assigned · claimed · acknowledged · started · blocked · reassigned · completed · expired · cancelled · escalated | `work_item.id` | `work_item_event` (chỉ 6 lệnh, prod chỉ có `create`) |
| **Episode** | opened · follow-up expected · contacted · booked · adherence · closed | `care_episode.id` | `event_log episode.closed/reopened`; `nhac_tai_kham` |
| **Resource** | shift started · available · room occupied · equipment unavailable · capacity changed · overload · restored | `staff.id` / `clinic_room.id` | `event_log roster.*`; tải phòng tính lúc đọc (`_STATIONS_SQL`) |
| **Communication** | requested · sent · delivery confirmed · patient acknowledged · explanation recorded · failed · retry | `patient.clinic_patient_id` (+ appointment) | `tuong_tac_cskh` (append-only), Telegram relay không để lại vết per-message |

> «Work Item không chỉ là một row có status = done; nó là một commitment có lịch sử ownership.» — *§6.2*

### Vì sao stream quan trọng với thiết kế

Hai thứ cần stream: **ordering** (§15.2: «Chỉ bảo đảm thứ tự trong boundary hợp lý, ví dụ một Encounter Stream») và **timeline cho người đọc** (§19.2: mỗi encounter có timeline với filter clinical/operational/communication/decision…).

Hôm nay muốn xem "mọi thứ đã xảy ra với lượt khám X" phải join 5 bảng theo 5 khoá khác nhau. `v_audit_log` (migration `20260805000001`) là view gộp — hình dạng gần với timeline, nhưng đọc `event_log` thôi.

Thiết kế: [[tk-mot-so-cai]] đặt quy ước `stream_id` = `enc:<visit_id>` · `work:<work_item_id>` · `epi:<episode_id>` · `res:<staff|room id>` · `comm:<patient_id>` và **cột `stream_version` do trigger cấp** — mọi sổ chuyên biệt vẫn giữ, nhưng đều đổ về `event_log` với `stream_id`.
""",
 "links": ["event-envelope", "so-cai-phan-manh", "tk-mot-so-cai", "reliability", "product-surface"],
},
{
 "id": "selective-event-sourcing", "layer": L, "order": 350,
 "title": "Selective event sourcing — bảng nào event-source, bảng nào CRUD + audit",
 "tag": "Care Model §7 · §20.6",
 "summary": "Bảng quyết định lưu trữ theo domain; 'event-source nơi thời gian và nhân quả tạo giá trị; không event-source vì thời thượng'.",
 "body": """
| Domain | Mô hình lưu trữ đề xuất | Lý do (thesis) | Code hôm nay |
|---|---|---|---|
| Patient master data | CRUD + audit | Cần snapshot hiện tại | ✅ `patient` + `patient.created/phone_*` |
| Staff/service/catalog/config | CRUD + versioning | Dữ liệu tham chiếu và policy | 🟡 `node_definition_version` có; các bảng luật khác không version |
| Appointment | State machine + domain events | «Cần lịch sử booking/reschedule/no-show nhưng không nhất thiết full event sourcing ban đầu» | ✅ đúng mô hình: 8 trạng thái, 11 action, event mỗi transition |
| **Encounter** | **Event-sourced hoặc event-centric ledger** | «Temporal truth, audit và reconstruction là cốt lõi» | ❌ `visit` là 5 cột trạng thái; `visit.checkin` chỉ ghi trong SQL check-in |
| **Work Item** | **Event-sourced** | «Ownership, SLA và acknowledgement cần lịch sử chính xác» | 🟡 `work_item_event` append-only có, nhưng vòng đời nghèo |
| Patient Journey | Projection + process manager | «Journey là cách diễn giải stream, không phải nguồn sự thật riêng» | 🟡 `visit_route` là *bản ghi*, không phải projection |
| Experience State | Temporal projection | Suy từ event, thời gian, communication coverage | ❌ |
| Dashboard/analytics | Read model / warehouse | Tối ưu truy vấn; rebuild được | ✅ view (`v_viec_cskh`, `v_dispatch_history`, `v_consultation_duration`) |

> «Nguyên tắc: event-source nơi thời gian và quan hệ nhân quả tạo ra giá trị; không event-source vì thời thượng.» — *§7*

> «20.6 Full event sourcing cho mọi bảng — Tăng độ phức tạp mà không tạo giá trị. Selective event sourcing là chủ đích.» — *§20*

### Quyết định thiết kế rút ra

Không viết lại `visit`/`work_item` thành bảng chỉ-có-event. Cách rẻ hơn và khớp cả thesis lẫn ADR-0003 (net cứng ở Postgres): **bảng trạng thái vẫn là bảng trạng thái, nhưng mọi thay đổi trạng thái của 4 domain event-centric bắt buộc đi qua hàm ghi sự kiện trong cùng transaction**, và `event_log` giữ đủ trường để fold lại được ([[tk-mot-so-cai]], [[tk-emit-function]]). Bài kiểm "xoá projection dựng lại" ([[chung-minh-event-driven]] mục 3) chạy trên **view** — vì view rebuild tức thì.
""",
 "links": ["event-first-dao-nhan-qua", "tk-mot-so-cai", "tk-emit-function", "chung-minh-event-driven", "appointment-visit-tuongtac", "workflow-kernel"],
},
{
 "id": "state-la-projection", "layer": L, "order": 360,
 "title": "State chỉ là projection — 8 projection cốt lõi",
 "tag": "Care Model §8",
 "summary": "Snapshot không phải truth độc lập; nhiều projection nhưng chỉ một source of truth; view CSKH là ví dụ đúng đang có.",
 "body": """
Ví dụ thesis (*§8*): một encounter đang hiển thị `encounter_state: awaiting_doctor_review · current_node: consultation_room_2 · patient_presence: onsite · wait_started_at: 10:18 · assigned_clinician: doctor_lan · experience_state: informed_wait · risk_flags: [result_review_sla_approaching]`

> «Nhưng snapshot này không phải truth độc lập. Nó được fold từ event: PatientArrived → EncounterStarted → ConsultationCompleted → LabOrderPlaced → SpecimenCollected → LabResultReady → DoctorReviewWorkCreated → PatientInformed. **Nếu projection bị lỗi, ClinicAI phải có thể xóa và dựng lại nó từ stream.**» — *§8*

Tám projection cốt lõi (*§8.1*): Encounter Board · Work Queue · Patient Journey · Experience Monitor · Resource Load · Patient View · Management Analytics · Audit View. «Nhiều projection có thể khác nhau nhưng không được có nhiều source of truth.»

### Chỗ code đã làm ĐÚNG nhất

`20260809000005_trang_thai_cskh_suy_ra.sql` mở đầu bằng đúng triết lý này, bằng tiếng Việt:

> «Trạng thái khách hàng là một **HÀM CỦA DỮ LIỆU**, không phải một cột ai đó bấm. […] Một bảng việc mà không có cron thì việc chỉ ra đời khi có người mở màn — và từ giây đó nó là BẢN SAO của sự thật, tự do lệch […] View thì không lệch được: xoá một cuộc gọi thì trạng thái tự lùi về đúng chỗ.»

`v_viec_cskh` = 11 nhánh `UNION ALL`, mỗi nhánh một câu hỏi nghiệp vụ, đọc `luat_cskh`; `v_trang_thai_cskh` chọn việc gấp nhất mỗi khách («QUÁ HẠN TRƯỚC, rồi mới tới ưu tiên»). Đây **là** Work Queue projection + một phần Experience Monitor — chỉ khác nguồn: nó fold từ *bảng trạng thái* (`appointment`, `lab_result`, `tuong_tac_cskh`), không từ event stream.

Cũng đúng: `visit.current_node_code` được **trigger** `update_visit_current_node()` nuôi từ `work_item` (migration `20260803000003`) — projection có người canh, không ai ghi tay. Và `dispatch_service.alerts()`: «Tính từ chính hai truy vấn trên chứ không từ một bảng cảnh báo riêng: một bảng cảnh báo là một bản sao của sự thật, và nó sẽ cũ đúng vào lúc Trưởng ca cần tin nó nhất.»

### Chỗ chưa đúng

`appointment.status`, `visit.status`, `work_item.status` là **cột được UPDATE**, event là hệ quả. Anti-pattern §20.8 «Direct write vào projection» — theo nghĩa thesis, chính các cột status là projection bị ghi thẳng. [[tk-projections]] không đổi điều đó ngay (quá đắt, và ADR-0003 cần cột để đặt CHECK/CAS); nó đòi **bất biến 1** (§22): «Mọi operational state quan trọng phải truy được về event» — tức mỗi lần UPDATE status phải có đúng một dòng event_log cùng transaction, kiểm bằng SQL test đếm cặp.
""",
 "links": ["cskh-views", "dispatch", "tk-projections", "gap-projection-rebuild", "15-invariant"],
},
{
 "id": "journey-process-manager", "layer": L, "order": 370,
 "title": "Patient Journey là Process Manager — expected vs actual, rẽ nhánh theo event thật",
 "tag": "Care Model §9",
 "summary": "Journey không phải sơ đồ tuyến tính hay cột current_step; nó giữ timer, so sánh, phát command, quản ngoại lệ.",
 "body": """
> «Patient Journey không nên là một sơ đồ tuyến tính cố định, cũng không phải một cột current_step.» — *§9*

Ba lớp: **Expected Journey** (policy/template) · **Actual Journey** (event stream) · **Journey Process Manager** («so sánh expected với actual, giữ timer, phát command và quản lý ngoại lệ»).

Ví dụ nguyên văn: «Expected: Check-in → Consultation → Lab → Doctor review → Payment → Follow-up. Actual: Check-in → Consultation → Lab → Waiting → **Patient left facility**. Process Manager thấy PatientLeftFacility trong khi DoctorReviewCompleted chưa xảy ra. Nó chuyển nhánh: tạo PostVisitResultReviewWork; yêu cầu kênh liên hệ phù hợp; đặt deadline; theo dõi acknowledgement và completion.»

```
[*] → Active
Active → AwaitingResult: LabOrderPlaced
AwaitingResult → AwaitingReview: LabResultReady
AwaitingReview → InClinicFollowup: PatientStillOnsite
AwaitingReview → PostVisitFollowup: PatientLeftFacility
InClinicFollowup → Completed: ReviewCompleted
PostVisitFollowup → Completed: PatientInformed
```

> «Journey vì thế không "chạy từng bước". Nó phản ứng với event và giữ các cam kết còn mở.» — *§9*

### Code có gì cho từng lớp

- **Expected**: `node_dependency` (18 cạnh FS) + `instantiate_visit_workflow` đóng dấu 7 bước xương sống lúc check-in; `route_template` (3 tuyến sau khám). Điểm hay: KHAM/DICHVU cố ý **không** sinh sớm — «stamping them at check-in would invent clinical intent nobody expressed» (`20260731000003`).
- **Actual**: `work_item` transitions + `visit.current_*` + `event_log dispatch.*`.
- **Process Manager**: **không có**. `dispatch_service.next_step_of()` chỉ đọc `visit_route` (0 dòng trên prod). `route_derivation.derive_route()` suy tuyến từ chỉ định — là "expected" động, tốt — nhưng không ai *phản ứng* khi actual lệch. Kịch bản «PatientLeftFacility khi còn kết quả chưa xem»: `checkout_service` đóng lượt, `follow_up_case` (0 dòng) không bao giờ được ghi.

Thiết kế: process manager **không cần là một engine mới** — nó là tập policy trong [[tk-policy-engine]] có trigger = event, điều kiện = trạng thái stream, hành động = tạo Work Item/expectation. Ba policy đầu tiên ở [[tk-experience-state]] chính là ba nhánh process manager của pilot.
""",
 "links": ["patient-journey-4-chang", "instantiate-visit", "dispatch", "gap-process-manager", "tk-policy-engine", "timer-expected-event"],
},
{
 "id": "policy-engine", "layer": L, "order": 380,
 "title": "Policy Engine — 5 câu hỏi mỗi policy, có version, owner, test case, audit",
 "tag": "Care Model §10",
 "summary": "Policy không nằm rải rác trong UI; ví dụ LabResultReady với 4 điều kiện → 4 phản ứng → 4 outcome kỳ vọng.",
 "body": """
> «Mỗi policy phải trả lời năm câu: (1) Event nào kích hoạt? (2) Điều kiện/ngữ cảnh nào cần đọc? (3) Decision nào được đưa ra? (4) Command hoặc Work Item nào được phát? (5) Outcome Event nào dùng để đóng vòng?» — *§10*

Ví dụ LabResultReady:

| Điều kiện | Phản ứng | Outcome kỳ vọng |
|---|---|---|
| Patient onsite, encounter active | RequestDoctorReview | DoctorReviewCompleted |
| Patient đã rời cơ sở | StartPostVisitResultFlow | PatientInformed hoặc FollowupBooked |
| Kết quả có cờ urgent | EscalateClinicalReview | UrgentReviewAcknowledged rồi UrgentReviewCompleted |
| Không map được encounter | QuarantineUnmatchedResult | ResultMatched hoặc IntegrationIncidentResolved |

> «Policy không nên nằm rải rác trong UI. Nó cần version, owner, test case và audit.» — *§10*

### Policy hiện đang nằm ở đâu trong code

Thực ra khá nhiều — và **là dữ liệu**, đúng hướng (`docs/kien-truc-nhieu-phong-kham.md` §3: «luật là DỮ LIỆU, không phải code», 4 tầng cấu hình). Nhưng chúng **được thi hành theo ba cách khác nhau**:

| Luật | Bảng | Thi hành lúc | Câu (1)–(5) |
|---|---|---|---|
| Việc CSKH (11 loại) | `luat_cskh` | **lúc đọc** (view) | có (1)(2)(4), không (3)(5) |
| Ngưỡng chờ phòng | `dispatch_threshold` | lúc đọc (`build_alerts`) | có (1)(2), không (4)(5) |
| Thứ tự bắt buộc | `visit_gate_rule` | **lúc ghi** (`gate_rule_service.enforce`) | có (1)(2)(3), override có audit ✅ |
| Bác sĩ bắt buộc | `luat_bac_si_bat_buoc` | lúc ghi (booking) | có |
| Sức chứa 3 tầng | `*_booking_override` + trigger | lúc ghi (DB) | có |
| Giờ ca, giờ mở | `clinic.settings` | lúc ghi | có |

Thiếu chung: **không version, không effective_from, không owner, không test case theo bảng** (test hiện là pytest cho hàm thuần như `gate_rule_service.blocks()` — tốt nhưng không gắn với dòng luật cụ thể). Và không luật nào **phản ứng với event** — cái thứ ba thesis đòi.

Thiết kế [[tk-policy-engine]] không thay các bảng này; nó thêm **một bảng `policy` cho loại luật thứ ba — luật phản ứng** — và thêm version/owner cho các bảng cũ theo cách rẻ nhất (cột `version`, `effective_from`, ghi event `PolicyVersionActivated` khi đổi).
""",
 "links": ["policy-as-data-hien-co", "gate-rule", "cskh-views", "tk-policy-engine", "timer-expected-event"],
},
{
 "id": "timer-expected-event", "layer": L, "order": 390,
 "title": "Thời gian và 'sự kiện không xảy ra' — timer tạo ra sự kiện quan sát được",
 "tag": "Care Model §11 · Catalog §11 · Work Item §7",
 "summary": "Sự vắng mặt không phải event; scheduler phải phát ExpectedEventDeadlineReached; timer huỷ được và idempotent.",
 "body": """
> «Một phần quan trọng của vận hành y tế là phát hiện điều đáng lẽ xảy ra nhưng chưa xảy ra. Sự vắng mặt tự nó không phải event. ClinicAI cần timer/scheduler tạo ra một sự kiện quan sát được.» — *§11*

Event thời gian: ExpectedEventDeadlineReached · AcknowledgementTimeoutOccurred · WaitingThresholdExceeded · FollowupWindowOpened · MissingExpectedEventDetected.

Chuỗi mẫu (*§11*): «(1) LabOrderPlaced tạo expectation: cần LabResultReady trước 11:00; (2) timer được đăng ký; (3) 11:00 chưa có result; (4) hệ thống phát ExpectedEventDeadlineReached; (5) policy kiểm tra lại stream; (6) nếu vẫn thiếu, phát LabResultDelayDetected; (7) tạo Work Item điều tra và communication task.»

> «Timer phải có thể hủy khi outcome đến sớm, và phải idempotent nếu bị kích hoạt lại.» — *§11*

Catalog §11 tách hai bước: `ExpectedEventDeadlineReached` («Timer đến hạn — chưa kết luận outcome bị thiếu») và `MissingExpectedEventDetected` («Recheck xác nhận outcome vẫn chưa có — Derived fact»). Work Item §7: bốn mốc `claim_by · acknowledge_by · start_by · complete_by`; «Timer phát event, không trực tiếp sửa status.»

### Code: không có bộ hẹn giờ — và tự khai điều đó ở hai chỗ

`recall_job_service.py` docstring: «Dự án chưa có bộ hẹn giờ nào (đã tìm: không apscheduler, không croniter, không repeat_every). Nên đường chắc chắn nhất hôm nay là sinh ngay lúc CSKH mở màn — `danh_sach()` gọi `sinh()` trước khi đọc.» Migration `20260809000005` chọn VIEW cũng vì «Dự án không có bộ hẹn giờ».

Hệ quả: mọi "quá hạn" hôm nay là **thuộc tính lúc đọc** (`qua_han` trong view, `wait_minutes > threshold` trong `build_alerts`). Không ai mở màn = không ai biết. Không có event = không có owner, không có ack, không có thời điểm phát hiện để đo.

Nhưng **hạ tầng để làm timer đã có sẵn**: `worker.py --relay` là một tiến trình sống 24/7 với vòng poll 30s + LISTEN. Thiết kế [[tk-expectation-timer]] thêm bảng `expectation` và một vòng "đồng hồ" **trong cùng tiến trình đó** — 0 hạ tầng mới, đúng Luật 7.1 và ADR-0005.
""",
 "links": ["gap-timer", "tk-expectation-timer", "work-item-commitment", "nhac-tai-kham", "notification-relay"],
},
{
 "id": "experience-state", "layer": L, "order": 400,
 "title": "Experience State — giả thuyết có bằng chứng, có lifecycle, có intervention",
 "tag": "Care Model §12 · Experience Spec v1",
 "summary": "Không phải cảm xúc do AI đọc; suy từ event + thời gian + communication coverage; 8 state v1, 3 rule mẫu.",
 "body": """
> «Experience State là giả thuyết có bằng chứng về trải nghiệm hiện tại của bệnh nhân, được suy ra từ event, thời gian và ngữ cảnh để kích hoạt một can thiệp hữu ích. Nó không phải cảm xúc được "AI đọc", không phải điểm hài lòng và không phải thước đo y đức của nhân viên.» — *Experience Spec, mở đầu*

> «Hai bệnh nhân cùng chờ 30 phút: người thứ nhất đã được báo rõ lý do, ETA và biết ai sẽ gọi; người thứ hai không nhận được thông tin và không biết mình có bị quên hay không. Do đó, chỉ đo Waiting Time là chưa đủ.» — *Spec §1*

**Ba lớp bằng chứng** (*§3*): Observed (bấm "Tôi cần hỗ trợ") · Self-reported · Inferred («Risk + confidence + lý do»). «Không phát PatientAnxious chỉ từ thời gian chờ.»

**Data model tối thiểu** (*§4*): `experience_state_id · type · subject{patient_id, encounter_id} · status · detected_at · evidence_level · confidence · evidence_event_ids[] · rule_or_model{id, version} · severity · owner_queue · recommended_intervention · review_at · expires_at · resolved_by_event_id`.

**Lifecycle** (*§5*): Detected → Confirmed / Intervening / Dismissed / Expired; Intervening → Resolved / Escalated. «Expired không đồng nghĩa Resolved.»

**8 state v1** (*§6*): InformedWait · UnexplainedWaitRisk · RepeatedDelayRisk · NeedsExplanation · HandoffUncertaintyRisk · AbandonmentRisk · ContinuityRisk · HighAnxietyContext. «ComplaintRisk chưa nên dùng ở pilot nếu chỉ dựa trên mô hình dự đoán.»

**Rule mẫu §7.1 UnexplainedWaitRisk** — điều kiện: encounter active · onsite · đang waiting · vượt threshold của node · **không có communication coverage hợp lệ** · không suppression. Kết quả: ExperienceRiskDetected → Communication Work Item → owner + deadline → escalation nếu không ack → khi PatientInformed, đánh giá resolution. Không kích hoạt nếu: đã cập nhật còn hiệu lực · bệnh nhân yêu cầu không làm phiền · clinical safety đang xử lý · presence không đủ tin cậy.

**Communication coverage** (*§8*) chỉ "che" khi: đúng bệnh nhân · đúng chủ đề · đúng vai · trong time window · nội dung đạt policy · evidence phù hợp. «Tin nhắn "Phòng khám đã nhận yêu cầu" không che phủ việc giải thích vì sao kết quả đang chậm.» Coverage record: subject · message category · communicated_at · **valid_until** · actor · channel · acknowledgement.

**Intervention contract** (*§10*): mỗi state ↔ một intervention ↔ một completion evidence (UnexplainedWaitRisk → «Giải thích lý do + ETA + bước tiếp theo» → PatientInformed đúng subject).

**Cấu hình theo phòng khám** (*§12*): waiting threshold theo node/khung giờ/loại encounter · refresh interval · ack window · số lần delay · suppression · escalation recipient · vai được confirm/dismiss · retention · consent.

### Code có mảnh nào

- Ngưỡng chờ theo phòng: `dispatch_threshold` (wait_minutes, max_waiting, mặc định 20'/8) ✅ — chính là «waiting threshold theo node».
- Cảnh báo `wait_too_long` trong `build_alerts` — tương đương *WaitingThresholdExceeded* nhưng **không có coverage**, không lifecycle, không owner.
- Coverage: `tuong_tac_cskh` có `loai` (chủ đề), `nhan_vien_staff_id` (vai), `xay_ra_luc` — thiếu `valid_until` và `appointment_id` không bắt buộc ở `TRA_KQ`.
- Severity tách clinical: `lab_result.triage_group` (GROUP_A/B/C) là trục clinical riêng ✅ — đúng §9 «Experience severity không được ghi đè clinical priority.»

Thiết kế: [[tk-experience-state]].
""",
 "links": ["gap-experience-state", "tk-experience-state", "timer-expected-event", "work-item-commitment", "tuong-tac-cskh", "dispatch", "humane-ops"],
},
{
 "id": "work-item-commitment", "layer": L, "order": 410,
 "title": "Work Item là commitment — 10 bất biến, 8 trạng thái, 4 mốc SLA, completion contract",
 "tag": "Care Model §13 · Work Item Protocol v1",
 "summary": "Không có owner thì chưa phải việc; không có completion criteria thì chưa biết thế nào là xong; không có outcome event thì vòng chưa khép.",
 "body": """
> «Work Item là một commitment có thể kiểm chứng: một kết quả cần xảy ra, có lý do, người chịu trách nhiệm, thời hạn và bằng chứng hoàn thành. Work Item không phải một dòng trong danh sách việc và không được đóng chỉ vì đã gửi notification.» — *Protocol, mở đầu*

**10 bất biến** (*§2*): Purpose · Reason (event/policy) · Subject · Owner (người/role/queue) · Priority (clinical và operational **tách**) · Deadline/SLA · Completion criteria · Expected outcome event · Escalation policy · Authority. «Không đủ các trường này thì chỉ là reminder, không phải Work Item.»

**Vòng đời** (*§4*): Open → Assigned → Acknowledged → Active → Blocked ⇄ Active → Completed; Assigned → Escalated (AcknowledgementTimeout); Active → Escalated (CompletionSLAExceeded); Escalated → Assigned (Reassigned); Open/Assigned → Cancelled.

> «4.3 Acknowledged: Người hoặc queue có thẩm quyền xác nhận đã nhận. Acknowledgement phải có actor và timestamp. · 4.4 Active: Việc thực sự bắt đầu. **Không tự động chuyển Active chỉ vì người dùng mở màn hình.** · 4.6 Escalated: Escalation không thay thế owner; nó mở một vòng chịu trách nhiệm mới.»

**Assignment** (*§5*): Direct user (có fallback) · Role queue (claim + queue owner) · Team queue · System agent (idempotency, audit, human fallback) · External system (callback + timeout). «Claim: một người lấy work từ shared queue. Acknowledge: người nhận xác nhận commitment.»

**Priority** (*§6*): clinical (routine/priority/urgent/emergency — do clinical policy) **tách** operational (normal/elevated/high/critical). «AI không tự nâng clinical priority nếu không có governance.»

**SLA** (*§7*): claim_by · acknowledge_by · start_by · complete_by; timer phát ClaimTimeoutOccurred · AcknowledgementTimeoutOccurred · StartSLAExceeded · CompletionSLAExceeded.

**Completion contract** (*§8*): Required domain event · Structured attestation · External callback («có thể chưa đủ cho informed outcome») · Human approval · Compound criteria.

**Escalation** (*§11*) ví dụ: assigned → 5' chưa ack → nhắc queue → 10' → trưởng ca → urgent → clinical escalation riêng → owner ack → đóng ack-escalation, «Completion timer vẫn tiếp tục». «Không tạo escalation chỉ để gửi thêm notification. Escalation phải thay đổi accountability.»

**Idempotency** (*§13*): «Cùng origin_event + policy_version + work_type + subject chỉ tạo một Work Item»; mọi command có expected version; reassignment được optimistic concurrency bảo vệ.

**Anti-patterns** (*§18*), những cái chạm code: «auto-complete ngay sau NotificationSent · giao mọi việc trực tiếp cho một cá nhân không có fallback · cho phép sửa owner/status không tạo event · đóng parent khi child commitment còn mở · biến mọi click nhỏ thành Work Item.»

### Kernel hôm nay đứng ở đâu

`work_item`: 5 trạng thái PENDING/IN_PROGRESS/COMPLETED/SKIPPED/CANCELLED; 4 lệnh start/complete/skip/cancel; `version` optimistic lock ✅; gate FS/SS/FF/SF trong SQL ✅ (`work_item_gate_blockers`); `work_item_event` append-only ✅; `assigned_to`/`assigned_role`/`due_at`/`priority (P0-P2)` có cột nhưng **không có lệnh assign, không ai đặt due_at, priority một trục**. `follow_up_case` có bảng, 0 dòng, không writer. Chi tiết [[gap-work-item]]; thiết kế [[tk-work-item-protocol]].

Điểm cộng của kernel mà Protocol không nói tới: **SKIPPED mở gate, CANCELLED thì không** và «skip/cancel không bao giờ bị gate — đó chính là cách gỡ một luồng bị kẹt» (ADR-0011). Giữ nguyên.
""",
 "links": ["workflow-kernel", "gap-work-item", "tk-work-item-protocol", "timer-expected-event", "bat-dang-thuc", "experience-state"],
},
{
 "id": "reliability", "layer": L, "order": 420,
 "title": "Reliability semantics — at-least-once, ordering theo stream, correction không sửa lịch sử, outbox/inbox, replay",
 "tag": "Care Model §15",
 "summary": "Healthcare không chấp nhận giả định 'message đến đúng một lần đúng thứ tự'; sáu quy tắc và code đã đạt được mấy.",
 "body": """
> «Healthcare operations không chấp nhận giả định "message chắc chỉ đến một lần và đúng thứ tự".» — *§15*

| Quy tắc (thesis) | Nguyên văn | Code hôm nay |
|---|---|---|
| 15.1 At-least-once + idempotency | «Mỗi side effect cần idempotency key, thường dựa trên event_id + policy_id + action_type.» | ✅ `idempotency_key` cho request (17 dòng prod); relay claim event bằng `pg_try_advisory_lock(hashtextextended(event_id))` → hai relay không gửi trùng. ❌ side effect của *policy* chưa có vì chưa có policy. |
| 15.2 Ordering | «Chỉ bảo đảm thứ tự trong boundary hợp lý […] dùng occurred_at để hiểu reality, recorded_at để audit latency; projection phải hỗ trợ recompute.» | ❌ không stream_version; `occurred_at = recorded_at` luôn; relay `ORDER BY occurred_at` toàn clinic. |
| 15.3 Optimistic concurrency | «Command ghi vào một stream phải nêu expected version.» | ✅ `work_item.version` + `CommandRequest.expected_version`; `move_visit_to_station` `FOR UPDATE`; booking CAS `WHERE status = $from`. |
| 15.4 Correction, không sửa lịch sử | «Event đã ghi không bị sửa. Sai sót được xử lý bằng event hiệu chỉnh: ArrivalRecordCorrected · ResultAssociationCorrected · WorkCompletionRevoked.» | ✅ mẫu đúng có sẵn: `tuong_tac_cskh.huy_luc` («Dòng ở lại, chỉ thôi được tính») + event `cskh.tuong_tac_hoan_tac`; `visit` FINALIZED → `amend_visit` RPC (ADR-0008); `event_log` có trigger chặn UPDATE/DELETE. |
| 15.5 Outbox và inbox | «dùng outbox để tránh "DB đã commit nhưng event thất lạc". Consumer dùng inbox/deduplication.» | 🟡 outbox = `event_log.event_published` **một cờ cho mọi consumer** (ADR-0002, `pos_outbox` comment: «One flag cannot serve two consumers»). `pos_outbox` riêng có attempts/backoff/DEAD ✅. |
| 15.6 Replay và quarantine | «projection phải rebuild được; event lỗi schema được quarantine; dead-letter có owner; replay không lặp side effect; mỗi projection ghi checkpoint.» | ❌ không quarantine; relay bỏ qua event không template bằng cách đánh dấu xong; không checkpoint. `pos_outbox.DEAD` là dead-letter thật ✅. |

Kết: **3/6 đạt, 1 nửa, 2 chưa.** Cái nửa (outbox một cờ) là nợ đã được chính ADR-0002 ghi từ 18/07 mà chưa trả: bảng `notification_delivery` per-channel. Thiết kế [[tk-reliability-playbook]] + [[tk-communication-delivery]].
""",
 "links": ["notification-relay", "pos-outbox", "idempotency-concurrency", "tuong-tac-cskh", "gap-reliability", "tk-reliability-playbook", "tk-communication-delivery"],
},
{
 "id": "failure-la-domain", "layer": L, "order": 430,
 "title": "Failure là một phần của domain — im lặng không phải 'không có gì xảy ra'",
 "tag": "Care Model §16 · Catalog §13",
 "summary": "IntegrationUnavailable, EventValidationFailed, NotificationDeliveryFailed… phải là event hiện trên operational health view.",
 "body": """
> «Nếu LIS ngừng kết nối, dashboard không được tiếp tục hiển thị sự yên lặng như "không có result mới". Nó phải biểu diễn độ tin cậy của quan sát. ClinicAI không chỉ hiển thị state. ClinicAI phải hiển thị khi nó không còn đủ bằng chứng để tin state đó.» — *§16*

Failure event (*§16*): IntegrationUnavailable · EventValidationFailed · ResultMappingFailed · NotificationDeliveryFailed · WorkAssignmentFailed · ProjectionLagThresholdExceeded · AutomationBlockedByPolicy.

Catalog §13 thêm: IntegrationRestored · DuplicateEventDetected · EventQuarantined · ProjectionRebuilt · UnauthorizedCommandRejected · ManualOverrideApplied · PolicyVersionActivated · EventSchemaVersionActivated. «Reliability event phải xuất hiện trên operational health view; không chỉ nằm trong log kỹ thuật.»

### Code: có "health view", chưa có "failure event"

`ops_status.py` gộp DB probe + snapshot host (`/run/clinicai-ops/status.json`) → `healthy/degraded/critical`, có trạng thái `unknown` và câu «Chưa có snapshot host hợp lệ; không giả định hệ thống đang an toàn.» — đúng tinh thần §16 ở tầng hạ tầng. `worker.py` có heartbeat file để compose healthcheck bắt «loop stops turning» — bài học «Celery worker chết âm thầm» (Tổng-Quan §14.6).

Nhưng ở tầng **nghiệp vụ** thì im lặng đúng kiểu thesis cấm:
- Relay: Telegram lỗi 3 lần → `logger.error("relay_delivery_failed")`, event nằm lại `event_published = FALSE` — **không có event NotificationDeliveryFailed**, không ai thấy trên màn hình.
- `RealtimeRefresher`: LISTEN rớt → «màn hình rơi về nhịp làm mới dự phòng» 60s — người dùng không biết mình đang nhìn dữ liệu cũ (thesis §19.1 đòi *data freshness* trên card).
- Bài học đã trả giá (GIAI-THICH-CODE §9 bẫy 3): 4 bảng CSKH nằm trong publication đã bỏ suốt 5 ngày, «hai CSKH ngồi cạnh nhau gọi cho cùng một khách hai lần trong một buổi» — đúng chế độ thất bại im lặng.

Thiết kế: [[tk-reliability-playbook]] đưa 4 failure event vào `event_log` (stream `sys:`), và card ATC có `data_freshness` ([[tk-atc-ui]]).
""",
 "links": ["gap-failure-domain", "tk-reliability-playbook", "tk-atc-ui", "realtime-sse", "notification-relay"],
},
{
 "id": "governance-event", "layer": L, "order": 440,
 "title": "Security, privacy, governance ở cấp event — payload tối thiểu, privacy_tags, replay có audit",
 "tag": "Care Model §17 · Catalog §15–16",
 "summary": "Immutable không phải lý do lưu thừa dữ liệu cá nhân; 13 yêu cầu và những gì RLS + redaction đã phủ.",
 "body": """
> «Event log làm audit mạnh hơn nhưng cũng tạo rủi ro tích lũy dữ liệu nhạy cảm.» — *§17*

13 yêu cầu: payload tối thiểu · tách reference khỏi content · field-level classification · role/purpose-based access · encryption · immutable audit cho read/export/action nhạy cảm · retention theo loại event · pseudonymization cho analytics · consent/purpose tags · event schema review · quyền replay bị giới hạn và ghi audit · không sensitive payload vào log kỹ thuật · model inference lưu model/rule version + input references.

> «"Immutable" không phải lý do để lưu thừa dữ liệu cá nhân.» — *§17*

Versioning (*Catalog §15*): additive giữ major; xoá/đổi nghĩa field → version mới; «Không đổi nghĩa của một event đã phát hành»; «Event history cũ không bị migrate chỉ để trông giống schema mới; dùng upcaster khi replay.»

Quy trình phê duyệt event mới (*Catalog §16*) — 10 câu, và **DoD cho một event** (*§17*) 12 ô: tên thì quá khứ · definition/non-definition · producer/authority · stream/subject/correlation/causation · payload schema có version · privacy classification · idempotency & ordering test · happy/duplicate/late/correction test · consumer liệt kê · monitoring có owner · example payload · ba bên phê duyệt.

### Đã có

- **Payload tối thiểu**: `event_log.payload` «cố ý chỉ mang ID» — relay làm giàu lúc gửi (`_lam_giau`). ✅
- **Không PII qua Telegram**: `notification_templates` docstring: «KHÔNG BAO GIỜ đưa số điện thoại / CCCD / địa chỉ vào tin» — có test. ✅
- **Access**: RLS `event_log` chỉ MANAGEMENT trong tenant (`20260717000001` + `20260730000004`). ✅
- **Log kỹ thuật**: `core/logging.py` redaction; `src/dashboard/lib/event-log-redaction.ts`. ✅
- **Retention**: SO-LUAT Phần 7: «Không xoá được, và đó là chủ ý […] chia bảng theo tháng rồi tách ra kho lạnh, không bao giờ xoá.» ✅ chính sách; chưa partition.
- **Model provenance**: `lab_result.triage_model/triage_reason/triage_classified_at` ✅.

### Chưa có

- `privacy_tags` / classification trên từng event.
- Replay: không có công cụ, nên không có audit replay.
- Schema review: `audit_labels.EVENT_LABELS` + `test_audit_labels_drift.py` là *một nửa* — nó bắt nhãn tiếng Việt, không bắt payload schema. [[tk-event-catalog-table]] đưa danh mục vào DB kèm `privacy_class`, `schema_version`; [[tk-governance]] phần còn lại.
""",
 "links": ["tk-governance", "tk-event-catalog-table", "multi-tenant-rls", "audit-labels", "event-envelope"],
},
{
 "id": "15-invariant", "layer": L, "order": 450,
 "title": "15 bất biến cấp 'hiến pháp' — chấm từng điều trên code",
 "tag": "Care Model §22",
 "summary": "Danh sách bất biến kiến trúc; mỗi dòng: đạt / một phần / chưa, kèm bằng chứng.",
 "body": """
| # | Bất biến (nguyên văn) | Code | Bằng chứng |
|---|---|---|---|
| 1 | Mọi operational state quan trọng phải truy được về event | 🟡 | `appointment` mọi transition có event ✅; `visit.status` đổi ở nhiều chỗ, `visit.checkin` chỉ ghi trong SQL; `work_item` có `work_item_event` nhưng không vào `event_log` |
| 2 | Event đã xảy ra không bị sửa; sai được hiệu chỉnh bằng event mới | ✅ | trigger `trg_event_log_no_update/no_delete`; `huy_luc` + `cskh.tuong_tac_hoan_tac` |
| 3 | Derived fact phải được phân biệt với observed fact | ❌ | không có `evidence_level`; không có derived event |
| 4 | Mọi Work Item phải có owner, reason, completion criteria và expected outcome | ❌ | `work_item` có `assigned_to` nullable (1/7 prod), không reason/criteria/outcome |
| 5 | Notification không đóng workflow | ❌ | relay đánh dấu xong khi gửi; `thong_bao` đóng bằng `da_xu_ly` (đúng) nhưng không nối với work item nào |
| 6 | Journey không phải một status; nó là process manager trên event stream | 🟡 | `visit_route` + `next_step_of` là status-ish; không process manager |
| 7 | Experience State là temporal projection có evidence, confidence và expiry | ❌ | không có |
| 8 | Không có autonomy nếu thiếu policy và authority rõ | ✅ | lab GROUP_C hard-block; relay chỉ gửi nội bộ; AI không ghi trạng thái |
| 9 | Projection phải rebuild được | 🟡 | view rebuild tức thì ✅; nhưng từ bảng trạng thái, không từ event |
| 10 | Consumer phải idempotent | ✅ | relay advisory lock + recheck `still_unpublished`; `idempotency_key`; `uq_work_item_visit_node_live` |
| 11 | Không che giấu integration failure thành "không có gì xảy ra" | ❌ | relay lỗi chỉ log; SSE rớt im lặng |
| 12 | Mọi escalation phải có người hoặc queue chịu trách nhiệm | ❌ | không có escalation |
| 13 | Event schema là product contract, không chỉ là chi tiết backend | 🟡 | `audit_labels` + drift test là contract tên; không contract payload |
| 14 | Event payload tuân thủ data minimization | ✅ | payload chỉ ID; relay làm giàu lúc gửi |
| 15 | ClinicAI đo outcome của coordination, không chỉ activity | ❌ | không metric coordination |

**Đạt 5 · một phần 4 · chưa 6.** Sáu cái chưa (3, 4, 5, 7, 12, 15) là cùng một cụm — và [[lo-trinh-tong]] Phase A đóng 4, 5, 12; Phase B đóng 3, 7; Phase C đóng 15.
""",
 "links": ["lo-trinh-tong", "chung-minh-event-driven", "gap-work-item", "gap-experience-state", "gap-failure-domain", "gap-metrics", "reliability"],
},
{
 "id": "kien-truc-toi-thieu", "layer": L, "order": 460,
 "title": "Kiến trúc logic tối thiểu — 12 capability trên modular monolith, và cái nào đã có",
 "tag": "Care Model §21 · §23",
 "summary": "Không cần distributed event platform; phiên bản đầu = 1 DB + event table + outbox + projector + timer + idempotency + state machine + policy versioning.",
 "body": """
Sơ đồ (*§21*): Sources & Human Actions → Ingestion + Validation → **Event Ledger** → Projectors → Operational Read Models; Ledger → Policy / Process Managers → Commands & Work Items → Humans / Systems → (vòng về Sources).

12 capability (*§21*) ↔ code:

| # | Capability | Có gì |
|---|---|---|
| 1 | Ingestion adapters: UI, HIS/EHR, LIS, CRM, device, messaging | UI (FastAPI router) ✅; còn lại ❌ (`PosPort` là mẫu adapter) |
| 2 | Identity/correlation: map patient, encounter, order, external IDs | `patient`/`visit`/`appointment` FK ✅; `mpi_service` dò trùng ✅; correlation_id ❌ |
| 3 | Event validation: schema, permission, duplication, timestamp | permission (JWT + role) ✅; schema/dup ❌ |
| 4 | Event ledger: append-only, partitioned streams, versioning | append-only ✅; stream/version ❌ |
| 5 | Projectors | view SQL ✅ (không cần worker) |
| 6 | Policy engine: rule có version và audit | rule là dữ liệu ✅; version/audit ❌ |
| 7 | Process managers: journey, timer, compensation, commitment | ❌ |
| 8 | Work orchestration: assignment, acknowledgement, SLA, escalation | gate + transition ✅; 4 thứ kia ❌ |
| 9 | Command gateway: kiểm authority trước action | `require_role` + `actor_roles` theo node ✅ (ADR-0004) |
| 10 | Observability: lag, failure, replay, freshness | `ops_status`, heartbeat ✅; lag/freshness ❌ |
| 11 | Governance: access, privacy, retention, audit | RLS tenant/role ✅, redaction ✅ |
| 12 | Analytics sink với pseudonymization | `reports_service` đọc trực tiếp; không sink |

Phạm vi phiên bản đầu (*§23*):

> «Không cần xây distributed event platform quy mô lớn ngay. Phiên bản đầu nên là modular monolith với semantic event backbone: một transactional database đáng tin cậy; append-only domain event table; transactional outbox; projector workers; durable job/timer mechanism; idempotency store; Work Item state machine; policy versioning; event timeline; replay có kiểm soát; adapters qua webhook/API; analytics export tách biệt.»

> «Điều cần bảo vệ từ ngày đầu không phải "scale hạ tầng", mà là: event semantics; correlation/causation; ordering boundary; immutable history; projection discipline; completion/outcome semantics.» — *§23*

Câu này **khớp từng chữ** với ADR-0001/0002/0005 và SO-LUAT Phần 7 («Postgres là hạ tầng có trạng thái duy nhất»). Nghĩa là thesis và sổ luật **không mâu thuẫn về hạ tầng** — mâu thuẫn chỉ ở *nghĩa* của dữ liệu. Toàn bộ [[tk-nguyen-tac]] xây trên điểm gặp nhau này.
""",
 "links": ["tk-nguyen-tac", "tk-modular-monolith", "adr-so-luat", "stack", "workflow-kernel", "gap-timer"],
},
{
 "id": "event-catalog", "layer": L, "order": 470,
 "title": "Event Catalog v1 — ngôn ngữ chung, ~80 event canonical, 3 phase pilot",
 "tag": "Event Catalog v1",
 "summary": "Tên canonical theo domain; event nào không được tồn tại; Definition of Done cho một event; Phase A/B/C.",
 "body": """
> «Nếu mỗi module gọi cùng một sự việc bằng một tên khác nhau, ClinicAI sẽ nhanh chóng trở thành tập hợp workflow rời rạc.» — *§1*

Quy tắc đặt tên (*§2*): thì quá khứ (PatientArrived, không ArrivePatient) · ngôn ngữ domain (ConsultationCompleted, không EncounterRowUpdated; **cấm** EntityChanged, DataSaved) · một event một ý nghĩa (tách AppointmentUpdated thành Confirmed/Rescheduled/Cancelled) · phân biệt mức hoàn thành.

Danh mục theo domain (§5–13), tóm tắt:

- **Booking & Pre-visit**: CareRequestOpened · CareRequestQualified · AppointmentProposed · AppointmentConfirmed · AppointmentRescheduled · AppointmentCancelled · PreVisitInstructionSent · AppointmentNoShowConfirmed. Mỗi cái có cột «Không đồng nghĩa» (AppointmentConfirmed ≠ «Bệnh nhân đã đến»).
- **Encounter & presence**: PatientArrived{location, arrival_method} · IdentityVerified · EncounterStarted · QueueEntered{node, queue, priority} · QueueExited{reason, next_node} · **PatientLocationObserved{location, method, confidence}** · PatientLeftFacility{method, open_commitments} · EncounterCompleted{completion_policy, open_followups} · EncounterCancelled.
- **Service node**: ServiceRequested · ServiceAccepted · ServiceStarted · ServicePaused · ServiceResumed · ServiceCompleted · ServiceUnableToComplete.
- **Orders & results**: OrderPlaced · OrderCancelled · SpecimenCollected · DiagnosticServiceStarted · ResultReady · ResultFlaggedUrgent · ResultReviewed · ResultCommunicated · ResultAssociationFailed.
- **Work**: WorkCreated · WorkAssigned · WorkAcknowledged · WorkStarted · WorkBlocked · WorkResumed · WorkReassigned · WorkEscalated · WorkCompleted · WorkCompletionRejected · WorkCancelled — mỗi cái một invariant («WorkAssigned: Không đồng nghĩa đã nhận»).
- **Communication**: CommunicationRequested · MessageSent{provider message ID} · MessageDeliveryConfirmed · PatientAcknowledged · PatientInformed{actor, method, subject} · CommunicationFailed · CommunicationRetryScheduled.
- **Time/expectation/experience**: ExpectationRegistered · ExpectedEventDeadlineReached · MissingExpectedEventDetected · WaitingThresholdExceeded · AcknowledgementTimeoutOccurred · NoRecentPatientUpdateDetected · ExperienceRiskDetected/Confirmed/InterventionStarted/Resolved/Expired.
- **Resource**: ShiftStarted/Ended · StaffAvailabilityChanged · ResourceOccupied/Released/Unavailable · QueueCapacityChanged · StaffOverloadDetected · NodeCongestionDetected · CapacityRestored.
- **Reliability**: 12 event (xem [[failure-la-domain]]).

Không phê duyệt (*§14*): EntityUpdated · StatusChanged không nghĩa domain · ButtonClicked · NotificationCreated · PatientHappy · AICompleted · WorkflowFinished · «event chứa nguyên record nhạy cảm không cần thiết». «UI analytics event có thể tồn tại ở telemetry riêng, không trộn vào domain event ledger.»

**Ưu tiên pilot** (*§18*): **Phase A** closed-loop core (PatientArrived, EncounterStarted, QueueEntered, ServiceStarted/Completed, ResultReady, WorkCreated/Assigned/Acknowledged/Completed, PatientInformed, EncounterCompleted) → **Phase B** exceptions & time (WaitingThresholdExceeded, AcknowledgementTimeoutOccurred, MissingExpectedEventDetected, WorkBlocked, WorkEscalated, PatientLeftFacility, CommunicationFailed) → **Phase C** capacity & intelligence.

> «Không thêm event vì một màn hình cần dữ liệu. Chỉ thêm event khi một sự thật có ý nghĩa đã xảy ra và tổ chức cần có khả năng nhớ, hiểu hoặc phản ứng với nó.» — *§19*

### Ánh xạ sang tên đang có

Code dùng `<aggregate>.<verb>` snake_case tiếng Anh/Việt lẫn (`appointment.created`, `cskh.tuong_tac`, `dispatch.moved`, `thong_bao.hen_goi_lai`). ~80 tên trong `audit_labels.EVENT_LABELS` — đó là **catalog de-facto**. [[tk-event-catalog-table]] không đổi tên đang chạy (đổi là vỡ relay/view/test); nó thêm cột `canonical` ánh xạ sang tên thesis, ví dụ `appointment.checked_in → PatientArrived`, `dispatch.moved → QueueEntered/QueueExited`, `cskh.tuong_tac[TRA_KQ] → ResultCommunicated`, `slot_hold.* → (telemetry, không phải domain)`.
""",
 "links": ["5-loai-event", "audit-labels", "tk-event-catalog-table", "failure-la-domain", "phase-a-closed-loop", "phase-b-exceptions", "phase-c-intelligence"],
},
{
 "id": "anti-patterns", "layer": L, "order": 480,
 "title": "10 anti-pattern cần cấm — và 4 cái code đang mắc",
 "tag": "Care Model §20",
 "summary": "CRUD rồi EntityUpdated · event là notification · UI status là truth · generic payload · choreography không owner · full ES · phát trước commit · ghi thẳng projection · sent = done · AI không provenance.",
 "body": """
| # | Anti-pattern | Code | Ghi chú |
|---|---|---|---|
| 20.1 | **CRUD rồi phát EntityUpdated** — «Một row đổi trạng thái rồi phát event generic không giữ được nghĩa nghiệp vụ và quan hệ nhân quả.» | 🟡 **mắc một nửa** | Event có tên nghiệp vụ (không generic) ✓, nhưng chiều nhân quả là CRUD-trước-event-sau, và 0% có causation. |
| 20.2 | Event là notification — «Event tồn tại dù không ai subscribe. Notification là một phản ứng có thể thất bại.» | 🟡 | `event_published` gộp hai nghĩa; `thong_bao.*` event thực chất là notification request. |
| 20.3 | UI status là source of truth | ✅ không mắc | ADR-0012: 0 policy ghi cho client; Command API. |
| 20.4 | Generic event payload `{before, after}` | ✅ không mắc | payload có tên trường nghiệp vụ. |
| 20.5 | Choreography không ownership — «không có process manager, journey phức tạp sẽ không ai sở hữu end-to-end completion» | ❌ **mắc** | Không process manager; trigger `update_visit_current_node` + view + relay là choreography rời. |
| 20.6 | Full event sourcing cho mọi bảng | ✅ không mắc | và thiết kế này cũng không. |
| 20.7 | Phát event trước khi transaction chắc chắn | ✅ không mắc | event ghi cùng transaction; relay đọc sau commit. (`EventService.record_and_publish` publish *sau* commit, đúng.) |
| 20.8 | Direct write vào projection | 🟡 | các cột `status` được UPDATE thẳng — xem [[state-la-projection]]. |
| 20.9 | **Coi "sent" là "done"** — «Một trong những lỗi nguy hiểm nhất của workflow software.» | ❌ **mắc** | relay `_mark_published` sau `send_telegram`. |
| 20.10 | AI inference không provenance | ✅ không mắc | `triage_model/reason/classified_at`; nhưng chưa có expiry/confidence. |

Bốn cái mắc (20.1, 20.2, 20.5, 20.9) đóng bằng ba việc: cửa ghi sự kiện duy nhất có causation ([[tk-emit-function]]), tách delivery khỏi ledger ([[tk-communication-delivery]]), và policy/process manager ([[tk-policy-engine]]).
""",
 "links": ["gap-crud-roi-log", "gap-communication", "gap-process-manager", "tk-emit-function", "tk-communication-delivery", "tk-policy-engine", "state-la-projection"],
},
{
 "id": "product-surface", "layer": L, "order": 490,
 "title": "Product surface sinh ra từ event model — ATC card, Event Timeline, 'Why am I seeing this', Replay",
 "tag": "Care Model §19 · Pilot §6 · Work Item §15",
 "summary": "Event-driven phải đổi sản phẩm, không chỉ backend: 9 trường trên mỗi card, timeline có filter, mọi cảnh báo giải thích được.",
 "body": """
> «Event-driven architecture phải thay đổi sản phẩm, không chỉ backend.» — *§19*

**Air Traffic Control** (*§19.1*) — mỗi card encounter: current projected state · state age · event gần nhất và thời điểm · commitment đang mở · owner · SLA/timer · experience risk · **data freshness** · đề xuất action và lý do.

**Event Timeline** (*§19.2*) — mỗi encounter, filter: clinical · operational · communication · decision · automation · correction · integration failure.

**"Why am I seeing this?"** (*§19.3*) — mọi cảnh báo/đề xuất giải thích: event nào kích hoạt · rule/model nào · evidence · confidence · action đề xuất · ai có quyền quyết định.

**Replayable operations review** (*§19.4*) — xem lại một ca: bottleneck bắt đầu từ event nào · ai nhận ownership · ack trễ bao lâu · communication có bao phủ thời gian chờ không · intervention nào tạo outcome · policy nào cần sửa.

Work Item §15 thêm ba màn: **My Work** (ưu tiên theo authority/urgency/deadline; một primary action; ack/claim nhanh; «Vì sao tôi nhận việc này?»; dấu hiệu clinical/operational tách) · **Team Queue** (unclaimed/assigned/blocked/overdue; «không che giấu work cũ vì sort theo việc mới») · **ATC** (open commitments; unowned/unacknowledged; approaching SLA; overload; escalation; history reassignment).

Pilot §6.3 **Patient panel**: số thứ tự/tên hoặc mã · bước hiện tại · hướng dẫn vị trí · dự kiến bước tiếp theo · thông báo chờ đã được phê duyệt.

### Màn hình hiện có, và thiếu trường nào

| Màn | Có | Thiếu so với thesis |
|---|---|---|
| `/truong-ca` (overview) — `dispatch_service._OVERVIEW_SQL` | current node, room, floor, wait/total minutes, threshold, done_steps, route_steps, next_step, queue_number, doctor | commitment đang mở + owner, SLA, experience risk, **freshness**, lý do đề xuất |
| `/truong-ca/canh-bao` — `build_alerts` | 4 loại, severity 2 mức, patients affected, câu tiếng Việt | «why» có sẵn trong message ✓ nhưng không event_id/rule_id; không ack/owner |
| `/truong-ca/hang-doi` — `_STATIONS_SQL` | serving/waiting/max/avg wait, capacity, accepting, floor | overload là màu, không phải event |
| `/truong-ca/lich-su` — `v_dispatch_history` | ai chuyển ai từ đâu tới đâu vì sao | chỉ `dispatch.*`, không phải timeline đủ loại |
| `/tasks`, `/work-items` — `list_worklist` | `actionable_by_me`, `blocked`, blockers endpoint («so the UI can say why a button is disabled» ✓) | acknowledge, due_at trống, không "why assigned" |
| `/display` — TV gọi số | số + phòng | bước tiếp theo, thông báo chờ |
| `/audit-log` — `v_audit_log` | event_log có nhãn Việt | không filter theo stream/loại; MANAGEMENT-only |

Thiết kế: [[tk-atc-ui]].
""",
 "links": ["tk-atc-ui", "man-hinh-theo-vai", "dispatch", "workflow-kernel", "gap-atc"],
},
{
 "id": "fhir-mapping", "layer": L, "order": 500,
 "title": "Quan hệ với chuẩn y tế — FHIR là boundary, không phải ontology nội bộ",
 "tag": "Care Model §27",
 "summary": "Map ở integration boundary; không ép mọi event thành FHIR resource; tránh semantic drift Task ↔ Work Item.",
 "body": """
> «ClinicAI không nên dùng FHIR như internal ontology duy nhất. FHIR là boundary quan trọng để liên thông, còn event model nội bộ được tối ưu cho orchestration.» — *§27*

Mapping dự kiến: Patient/subject ↔ FHIR Patient · appointment intent ↔ Appointment · care contact ↔ **Encounter** · longitudinal grouping ↔ EpisodeOfCare · executable work ↔ **Task** · service capability ↔ HealthcareService.

Nguyên tắc: map ở integration boundary · không ép mọi operational event thành resource update · giữ correlation giữa event và external resource/version · tránh semantic drift giữa FHIR Task và Work Item nội bộ · version adapter độc lập với domain event contract.

### Nghĩa cho ClinicAI Việt Nam

Bối cảnh pháp lý đã tra trong phiên IoT 04/09: Thông tư 26/2025/TT-BYT và Quyết định 808/QĐ-BYT (Phụ lục II–VII = đặc tả kết nối HIS) — đây là boundary mà lúc nào đó ClinicAI phải map ra, đúng như §27 nói. Tổng-Quan §14.7: TT13/2025 bắt EMR trước 31/12/2026, cần ký số + CCCD.

Bảng nội bộ đã ở dạng dễ map: `patient`→Patient, `appointment`→Appointment, `visit`→Encounter, `care_episode`→EpisodeOfCare, `work_item`→Task, `service_type`→HealthcareService, `clinic_location`/`clinic_room`→Location. Thiết kế **không** thêm gì ở phase này ngoài một ghi chú trong [[tk-event-catalog-table]]: cột `fhir_hint` tuỳ chọn cho event liên quan (ResultReady → DiagnosticReport), để adapter sau này không phải đoán.
""",
 "links": ["ontology-9", "tk-event-catalog-table", "tk-sensing"],
},
]
