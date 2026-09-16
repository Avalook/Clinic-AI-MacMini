# -*- coding: utf-8 -*-
"""Lớp 4 — KHOẢNG CÁCH: từng khái niệm thesis đối chiếu code + số đo prod."""

L = 4

NODES = [
{
 "id": "gap-envelope", "layer": L, "order": 900, "status": "mot-phan",
 "title": "Khoảng cách 1 — Envelope: 9/17 trường có chỗ, 0% correlation, actor chìm trong JSON, 62% nhiễu",
 "tag": "event_envelope ↔ event_log",
 "summary": "Bảng có hình đúng nhưng không ai điền; không có evidence_level nên không phân biệt được suy luận với quan sát.",
 "body": """
| Thiếu | Hệ quả người dùng gặp | Bằng chứng |
|---|---|---|
| `correlation_id` / `causation_id` không bao giờ điền | Không trả lời được «cuộc gọi này là do việc nào sinh ra» hay «lịch này đổi vì ca nào bị xoá» — phải suy bằng tay từ giờ | 0/449 khác NULL |
| Không `stream_id` / `stream_version` | Timeline một lượt khám không có; không đảm bảo thứ tự trong lượt | cột không tồn tại |
| Actor trong `metadata` JSON, 3 kiểu khoá khác nhau | «ai làm» không index được, không FK; PR #8 treo từ tháng 7 | 424 `clinic_staff_id`, 24 `by_staff_id` ở payload |
| Không `evidence_level` / `confidence` | Bất biến 3 (derived ≠ observed) không thể giữ; AI phát hiện gì cũng sẽ trông như sự thật | cột không tồn tại |
| Không `privacy_tags` | Retention/export theo loại không làm được; audit view phải cho MANAGEMENT xem hết hoặc không gì | cột không tồn tại |
| `recorded_at = occurred_at` 100% (bằng nhau do cả hai `DEFAULT now()`, không phải do không có độ trễ) | Ghi bù/ghi trễ (Tổng-Quan §14.3 «`performed_at` bất biến + thời điểm ghi») không có đường | max chênh 0s |
| 62% là `slot_hold` | Telemetry lẫn với mốc chăm sóc trong cùng một bảng; nhật ký thao tác vẫn đọc được, nhưng chưa tách được lớp nào là sự thật nghiệp vụ | 281/449 |
| `patient_id`/`visit_id` không phải cột | Mọi timeline phải join qua `aggregate_id` theo từng loại | |

Câu thesis bị vi phạm trực tiếp: «Mọi event cần một envelope thống nhất **trước khi có hàng trăm event type**» (§5) — repo đã có ~80 tên trong `audit_labels` mà envelope chưa thống nhất. Đây là chỗ đúng thứ tự "nền trước" của TAM-NHIN.

Đóng bằng: [[tk-event-envelope-v2]] (một migration cộng thêm, backfill được từ dữ liệu có sẵn), [[tk-event-catalog-table]] (đuổi `slot_hold` sang telemetry), [[tk-emit-function]] (một cửa ghi điền đủ).
""",
 "links": ["event-envelope", "event-log-table", "tk-event-envelope-v2", "tk-event-catalog-table", "tk-emit-function"],
},
{
 "id": "gap-crud-roi-log", "layer": L, "order": 910, "status": "mot-phan",
 "title": "Khoảng cách 2 — CRUD rồi log: state trước, event sau, 29 cửa ghi, độ phủ thưa",
 "tag": "anti-pattern §20.1 ↔ services/*.py",
 "summary": "Event là phụ phẩm của UPDATE; nhiều thay đổi trạng thái không có event nào; không cửa ghi bắt buộc điền envelope.",
 "body": """
Mẫu phổ biến trong 21 file service — ví dụ `episode_service.set_status()`: UPDATE `care_episode.status` → INSERT `event_log episode.closed` (cùng transaction ✓). Chiều nhân quả: **cột trạng thái là chính, event là ghi chú**. Thesis §1: «Đó là "CRUD có message"».

Độ phủ đo được trên prod:
- 66 `appointment.created`, 1 `appointment.checked_in`. **Đây không phải bằng chứng mất event** — xem [[event-log-table]]: mốc quầy CSKH và lễ tân dùng CHUNG một máy trạng thái, chung một event; 66 là lịch đã tạo chứ không phải khách đã đến. Phép đo đúng để kết luận **không phải** so hai tổng `count(*)`: phải đối soát từng cặp `(clinic_id, appointment_id)` giữa lịch từng đạt `CHECKED_IN` và dòng `appointment.checked_in` tương ứng, có xét hoàn tác (`appointment.checkin_undone`) và thứ tự thời gian, vì một lịch có thể check-in rồi hoàn tác rồi check-in lại. *Chưa chạy.*
- `visit`: `move_visit_to_station` **có** ghi `event_log` (`20260804000013_room_serves_many_nodes.sql:227`, hàm khai từ dòng 122, `p_event_type` mặc định `dispatch.moved`) và chính nó lật `visit.status` OPEN → IN_PROGRESS trong cùng hàm. Chỗ hụt là **tên**, không phải chuyện thiếu ghi: bước ngoặt vòng đời đi lậu bên trong một event "chuyển phòng", nên projection chỉ suy ra "encounter đã bắt đầu" bằng cách đoán từ lần chuyển đầu tiên. `INCOMPLETE` có `visit.closed_incomplete`, FINALIZED có `clinical.signed`, không có `EncounterCompleted`.
- `work_item`: 7 `create`, và toàn bộ vòng đời nằm ở `work_item_event`, **không** vào `event_log`.
- `lab_result`, `payment`: 0 dòng prod nên chưa đo được, nhưng code có `lab_result.*`, `payment.recorded/voided`.

Hệ quả: bài kiểm «xoá dashboard, dựng lại từ event history» (§1) thất bại ngay ở `visit` — không dựng lại được `current_node_code` từ `event_log` vì `dispatch.moved` chỉ có 2 dòng còn `work_item` chuyển trạng thái không ghi vào đó.

29 câu `INSERT INTO event_log` viết tay = 29 cơ hội quên `metadata`, quên `source`, quên `correlation`. `services/audit.py:record_event()` là cửa chung có sẵn nhưng ít nơi dùng.

Đóng bằng: [[tk-emit-function]] (hàm SQL `ghi_su_kien` là cửa duy nhất, CI ceiling 29 → 0) + [[tk-mot-so-cai]] (trigger đổ các sổ chuyên biệt vào ledger) + bất biến «mỗi UPDATE status = một event» trong [[chung-minh-event-driven]].
""",
 "links": ["anti-patterns", "event-log-table", "so-cai-phan-manh", "tk-emit-function", "tk-mot-so-cai", "chung-minh-event-driven"],
},
{
 "id": "gap-work-item", "layer": L, "order": 920, "status": "mot-phan",
 "title": "Khoảng cách 3 — Work Item: 5 trạng thái, không owner bắt buộc, không ack, không SLA, không escalation",
 "tag": "work-item-commitment ↔ workflow-kernel",
 "summary": "Kernel có transition + gate + version; thiếu toàn bộ nửa 'commitment' của Protocol; lúc đo trên prod chưa có lệnh start nào.",
 "body": """
Đối chiếu 10 bất biến Protocol §2 với `work_item`:

| Bất biến | Cột/lệnh hiện có | Kết luận |
|---|---|---|
| Purpose | `node_definition.name` | ✅ qua node |
| Reason (event/policy) | `work_item_event.metadata.spawn_on` | 🟡 không trỏ event |
| Subject | `clinic_patient_id/visit_id/appointment_id/care_episode_id` | ✅ |
| Owner (người/role/queue) | `assigned_to` nullable, `assigned_role` nullable | ❌ 1/7 có `assigned_to`; không «queue» |
| Priority tách clinical/operational | `priority P0/P1/P2` một trục | ❌ |
| Deadline/SLA | `due_at` nullable, không ai đặt | ❌ |
| Completion criteria | — | ❌ (complete = bấm nút) |
| Expected outcome event | — | ❌ |
| Escalation policy | — | ❌ |
| Authority | `actor_roles` theo node ✅ | ✅ |

Vòng đời: Protocol 8 trạng thái (Open/Assigned/Acknowledged/Active/Blocked/Escalated/Completed/Cancelled) vs kernel 5. Thiếu lệnh: **assign · claim · acknowledge · block · resume · reassign (có trong CHECK của `work_item_event` nhưng không có API) · escalate · reject_completion**.

Timer 4 mốc (claim_by/acknowledge_by/start_by/complete_by): không có mốc nào, không có timer.

Idempotency §13 «cùng origin_event + policy_version + work_type + subject chỉ tạo một»: có `uq_work_item_visit_node_live` (theo visit+node) — tốt cho spine, không phủ work item do policy sinh (chưa có).

`follow_up_case` (parent–child §9: «Parent work chỉ Completed khi các child work bắt buộc đã completed»): 0 dòng, không writer.

Hai thứ kernel làm **tốt hơn** Protocol: gate trong SQL để «no caller can route around it», và luật SKIPPED/CANCELLED. Giữ.

Hệ quả người dùng: Trưởng ca nhìn bảng thấy «SA1: 4 người chờ» nhưng không thể hỏi «ai đang phụ trách đưa người thứ nhất vào, đã biết chưa, còn mấy phút». Đó chính là Coordination Debt (v1 §9.2) — không đo được vì không có dữ liệu.

Đóng bằng: [[tk-work-item-protocol]].
""",
 "links": ["work-item-commitment", "workflow-kernel", "tk-work-item-protocol", "thong-bao", "cskh-views", "metrics-thesis"],
},
{
 "id": "gap-timer", "layer": L, "order": 930, "status": "chua",
 "title": "Khoảng cách 4 — Không bộ hẹn giờ: 'sự kiện không xảy ra' là vô hình",
 "tag": "timer-expected-event ↔ (không có gì)",
 "summary": "Mọi 'quá hạn' là thuộc tính lúc đọc; không ai mở màn = không ai biết; việc sau khám sinh khi CSKH mở trang.",
 "body": """
Code tự khai ở hai chỗ: `recall_job_service.py` («Dự án chưa có bộ hẹn giờ nào (đã tìm: không apscheduler, không croniter, không repeat_every)») và `20260809000005` («Dự án không có bộ hẹn giờ»).

Hậu quả cụ thể:
- `v_viec_cskh.qua_han` = `han < hôm nay` **lúc SELECT**. Không có thời điểm "phát hiện quá hạn", không có ai được giao khi quá hạn.
- `build_alerts()` `wait_too_long` sống trong response HTTP của `/truong-ca/canh-bao`. Đóng tab = cảnh báo biến mất; không ack; không đo «thời gian từ phát hiện đến can thiệp» (Spec §14).
- `nhac_tai_kham` sinh lúc `danh_sach(sinh_truoc=True)` — CSKH nghỉ một ngày, việc lượt 1 sinh trễ một ngày.
- `slot_hold` hết hạn 10 phút: giải phóng lúc có người khác đặt (`release_on_booking`) hoặc view `v_slot_hold_active` lọc — đúng cho giữ chỗ, nhưng là cùng một mẫu "hết hạn lúc đọc".
- Không có `AcknowledgementTimeoutOccurred` vì không có acknowledge; không `ExpectedEventDeadlineReached` vì không có expectation.

Thesis §11: «Sự vắng mặt tự nó không phải event. ClinicAI cần timer/scheduler tạo ra một sự kiện quan sát được.» Và v1 §10 Level 4 phản xạ số 6: «MissingExpectedEvent → hệ thống chủ động hỏi hoặc escalation thay vì giả định mọi thứ bình thường.»

Vì sao chưa làm: SO-LUAT 7.2 đúng — đừng thêm hạ tầng. Nhưng câu trả lời không phải cron/Celery/pg_cron: **`worker.py --relay` đã là một tiến trình sống 24/7 có poll 30s + LISTEN + heartbeat**. Thêm một vòng "đồng hồ" đọc bảng `expectation` vào đó là 0 hạ tầng mới. [[tk-expectation-timer]].
""",
 "links": ["timer-expected-event", "tk-expectation-timer", "cskh-views", "nhac-tai-kham", "dispatch", "notification-relay"],
},
{
 "id": "gap-experience-state", "layer": L, "order": 940, "status": "chua",
 "title": "Khoảng cách 5 — Experience State: không có; gần nhất là ngưỡng chờ theo phòng",
 "tag": "experience-state ↔ dispatch_threshold",
 "summary": "Hệ thống biết 'chờ bao lâu' nhưng không biết 'đã được giải thích chưa' — nên không phân biệt được chờ có thông tin và chờ vô định.",
 "body": """
Có mảnh: `dispatch_threshold` (ngưỡng theo phòng ✓ = Spec §12 «waiting threshold theo node»), `wait_too_long` alert (≈ WaitingThresholdExceeded nhưng không phải event), `tuong_tac_cskh` (≈ communication record), `lab_result.triage_group` (clinical severity riêng trục ✓).

Không có: bảng `experience_state`; khái niệm **communication coverage** (Spec §8: subject · category · communicated_at · **valid_until** · actor · channel); lifecycle Detected→Intervening→Resolved/Expired; intervention contract; confidence/evidence_event_ids; owner_queue; review_at/expires_at.

Ba rule mẫu của Spec §7 đối chiếu:

| Rule | Cần | Có |
|---|---|---|
| 7.1 UnexplainedWaitRisk | active + onsite + waiting + vượt threshold node + **không coverage** + không suppression | vượt threshold ✓; onsite ✓ (`visit.status IN OPEN/IN_PROGRESS`); coverage ❌; suppression ❌ |
| 7.2 HandoffUncertaintyRisk | WorkAssigned + hết ack window + chưa Acknowledged/Reassigned/Cancelled | không có assign/ack |
| 7.3 ContinuityRisk | PatientLeftFacility + open commitment + chưa post-visit owner | `dispatch.checkout` ✓; open commitment tính được từ `work_item PENDING` + `lab_result` chưa review ✓; owner ❌ |

Hệ quả người dùng: CSKH không được nhắc «chị Lan chờ SA2 25 phút chưa ai nói gì với chị» — họ chỉ thấy nếu đang mở màn Trưởng ca, mà CSKH không có màn đó.

Điểm cần nói thẳng (Spec §2.5): «State chỉ nên tồn tại khi có intervention khả thi.» Dr4Women hôm nay có 10 CSKH và Zalo cá nhân — intervention «giải thích lý do + ETA» khả thi ngay. Nên state đầu tiên nên là UnexplainedWaitRisk, không phải cái gì cần AI. [[tk-experience-state]].
""",
 "links": ["experience-state", "tk-experience-state", "dispatch", "tuong-tac-cskh", "gap-timer", "gap-communication"],
},
{
 "id": "gap-projection-rebuild", "layer": L, "order": 950, "status": "mot-phan",
 "title": "Khoảng cách 6 — Projection: view rebuild được, nhưng từ bảng trạng thái chứ không từ event",
 "tag": "state-la-projection ↔ v_*, visit.current_*",
 "summary": "Bất biến 9 đạt một nửa; bài kiểm §26.3 'rebuild một projection từ lịch sử' hôm nay không chạy được cho visit.",
 "body": """
Có 9 view: `patient_summary · v_audit_log · v_clinical_status · v_consultation_duration(_stats) · v_dispatch_history · v_slot_hold_active · v_trang_thai_cskh · v_viec_cskh`. View = projection rebuild tức thì ✓. `visit.current_node_code` do trigger nuôi từ `work_item` ✓ (§20.8 không mắc ở đây).

Nhưng nguồn fold là **bảng trạng thái** (`appointment.status`, `lab_result.reviewed_at`, `work_item.status`), không phải `event_log`. Nên: (a) không có "projection lag" để đo — vì không có projector; (b) nếu `work_item` bị sửa tay, `visit.current_node_code` theo, và `event_log` không biết; (c) muốn xem «trạng thái lúc 10:20 hôm qua» thì không có cách — không temporal query.

Thesis §7 cho phép Appointment ở mức state machine + events và master data CRUD — nên **không phải mọi bảng** cần fold từ event. Domain phải fold được: Encounter, Work Item, Communication, Experience (§2). Trong bốn cái, code hôm nay không fold được cái nào.

Cái cần: không phải viết projector worker (view đủ nhanh ở 1 RPS, DB cùng máy <1ms), mà là **đảm bảo event_log chứa đủ để fold** — tức [[tk-mot-so-cai]] + [[tk-event-envelope-v2]] — rồi viết **view đối chứng** `v_visit_state_from_events` và test «view từ bảng == view từ event» ([[chung-minh-event-driven]] mục 3). Khi hai view bằng nhau trên staging vài tuần, ledger mới đáng tin làm nguồn cho policy.
""",
 "links": ["state-la-projection", "cskh-views", "tk-projections", "tk-mot-so-cai", "chung-minh-event-driven"],
},
{
 "id": "gap-process-manager", "layer": L, "order": 960, "status": "chua",
 "title": "Khoảng cách 7 — Không process manager: rời cơ sở khi còn việc mở thì việc biến mất",
 "tag": "journey-process-manager ↔ dispatch/checkout",
 "summary": "Expected có, actual có, nhưng không ai so sánh và phản ứng; visit_route 0 dòng; follow_up_case không writer.",
 "body": """
Kịch bản thesis §9: PatientLeftFacility khi DoctorReviewCompleted chưa xảy ra → tạo PostVisitResultReviewWork + kênh liên hệ + deadline + theo dõi ack/completion.

Code: `checkout_service` đóng lượt (`dispatch.checkout`, `CHECK_OUT` mốc quầy, `visit.closed_incomplete` nếu chưa khám xong). `work_item` PENDING còn lại → `cancel_visit_workflow` hoặc để nguyên. `follow_up_case` — bảng được tạo đúng cho việc này («Non-blocking work that was still open when the visit closed») — **không có INSERT nào trong toàn repo**. `lab_result` chưa review sau checkout → chỉ hiện ở `v_viec_cskh` nhánh CHO_BAC_SI/KQ_CHUA_GUI (tốt, nhưng không owner).

Đến muộn (Journey §5.1: «không chỉ đổi trạng thái "muộn"; đánh giá lịch và công suất; phương án tiếp nhận hoặc đổi lịch; ai quyết định»): code có `walkin` seat, `is_priority_slot`, `queue_order` — nhưng không phản ứng tự động khi `now() > slot_start + X` mà chưa check-in (không timer).

Kết quả bất thường (§5.6): lab GROUP_C → `staff_task` URGENT — có, nhưng `staff_task` 0 dòng và không nối kernel.

`visit_route`: 0 dòng; `route_derivation` suy được nhưng «bảng Trưởng ca có cột "bước kế tiếp" […] trống với mọi bệnh nhân». `docs/kien-truc-nhieu-phong-kham.md` §2c: «Không có tuyến nào cho người chỉ khám rồi về.»

Đóng bằng: process manager = **policy phản ứng với event** trong [[tk-policy-engine]]; ba policy đầu (UnexplainedWait, HandoffUncertainty, ContinuityRisk) là ba nhánh rẽ; `follow_up_case` có writer đầu tiên từ policy ContinuityRisk.
""",
 "links": ["journey-process-manager", "dispatch", "nhac-tai-kham", "tk-policy-engine", "tk-experience-state", "patient-journey-4-chang"],
},
{
 "id": "gap-communication", "layer": L, "order": 970, "status": "mot-phan",
 "title": "Khoảng cách 8 — Communication: attestation tốt, delivery kém; sent = done; không coverage window",
 "tag": "bat-dang-thuc ↔ tuong_tac_cskh / relay",
 "summary": "Với bệnh nhân: sổ chạm là bằng chứng đủ ở quy mô này; với nội bộ: Telegram gửi xong là 'xong', không ai biết ai đọc.",
 "body": """
Hai kênh, hai tình trạng:

**Với bệnh nhân** (qua CSKH gọi/Zalo cá nhân): `tuong_tac_cskh` ghi có người, có giờ, có kết quả, có `khach_xac_nhan` — «SỔ CHĂM SÓC CHÍNH LÀ BẰNG CHỨNG, ở quy mô hiện tại» (docstring, Tuyền chốt 14/08). Đúng Protocol §8 *Structured attestation*. Thiếu: `valid_until` (coverage hết hạn khi nào), chủ đề rõ (`loai` gộp "giải thích chờ" vào KHAC), và không nối commitment (dòng TRA_KQ không đóng một work item nào — nó đóng một *nhánh view*).

**Nội bộ** (Telegram): `event_published` được đặt cả ở nhánh không-có-template (không gửi gì, `notification_relay.py:205-214`) lẫn nhánh nhà cung cấp trả ok (`:238`), và `processed` trong log cộng cả hai (`:256`) → nhẹ hơn cả §20.9 «Coi "sent" là "done"»: ở đây "chưa từng gửi" cũng đọc ra thành "đã xử lý". Không MessageDeliveryConfirmed, không ai-đã-đọc, không retry có lịch (3 lần rồi nằm lại đến vòng sau — thực ra là retry vô hạn mỗi 30s cho event hỏng vĩnh viễn, không DEAD). `thong_bao` trong app làm đúng hơn (đọc ≠ xử lý) nhưng không gửi ra ngoài.

Zalo OA (kênh cho bệnh nhân theo D010) chưa xây; `providers/zalo.py` là stub.

Người dùng gặp: Trưởng ca gọi «SA1 tắc» → điều dưỡng có thấy không? Nếu họ không mở app, không có gì báo; nếu Telegram nhóm báo, không ai biết ai nhận.

Đóng bằng: [[tk-communication-delivery]] — `notification_delivery` per channel (ADR-0002), `tuong_tac_cskh` + `valid_until` + `subject`, và quy tắc: **PatientInformed chỉ từ attestation có subject**, MessageSent không bao giờ đóng việc.
""",
 "links": ["bat-dang-thuc", "notification-relay", "tuong-tac-cskh", "thong-bao", "tk-communication-delivery", "experience-state"],
},
{
 "id": "gap-policy", "layer": L, "order": 980, "status": "mot-phan",
 "title": "Khoảng cách 9 — Policy: là dữ liệu (mạnh), nhưng không version, không owner, không phản ứng với event",
 "tag": "policy-engine ↔ 9 bảng luật",
 "summary": "Điểm mạnh nhất của code so với thesis; việc còn lại nhỏ và rẻ: version/effective_from + một bảng cho luật phản ứng.",
 "body": """
Thesis §10 đòi 4 thứ: **version · owner · test case · audit**. Đo:

| | version | effective_from | owner | event khi đổi | test theo dòng |
|---|---|---|---|---|---|
| `node_definition` | ✅ `_version` snapshot | ❌ | ❌ | ❌ | SQL test kernel ✓ |
| `luat_cskh` | ❌ | ❌ | ❌ | ❌ | ❌ |
| `dispatch_threshold` | ❌ (`updated_by/at`) | ❌ | 🟡 `updated_by` | ❌ | ❌ |
| `visit_gate_rule` | ❌ | ❌ (`is_active`) | ❌ | ❌ (override có bảng riêng ✓) | pytest hàm thuần ✓ |
| `luat_bac_si_bat_buoc` | ❌ | ❌ | ❌ | ✅ `booking.doctor_rule_saved` | `xem_thu()` đếm hậu quả ✓ |
| `*_booking_override` | ❌ (`slot_superseded` event ✓) | ✅ có ngày áp | ❌ | ✅ | test race ✓ |
| `clinic.settings` | ❌ (`hours_truoc_13_08` là "version" bằng tay!) | ❌ | ❌ | ✅ `clinic_settings.*` | ✓ |

Thiếu lớn nhất không phải version — là **loại luật thứ ba**: «Event nào kích hoạt? → … → Outcome Event nào đóng vòng?» Không bảng nào trả lời câu 1 và 5. Mọi luật hôm nay hoặc chặn lúc ghi hoặc tô màu lúc đọc.

Pilot §14: «Mọi thay đổi policy trong live pilot phải có version và ngày hiệu lực để số liệu không bị trộn.» → không có thì baseline/outcome không so được.

Đóng bằng: [[tk-policy-engine]] — thêm cột `version, effective_from, effective_to, owner_role` cho 6 bảng cũ (migration nhỏ) + event `PolicyVersionActivated` từ trigger; bảng `policy` mới cho luật phản ứng; bảng `policy_case` để test theo dòng luật chạy trong CI.
""",
 "links": ["policy-engine", "policy-as-data-hien-co", "tk-policy-engine", "gate-rule", "pilot-scope"],
},
{
 "id": "gap-reliability", "layer": L, "order": 990, "status": "mot-phan",
 "title": "Khoảng cách 10 — Reliability: một cờ cho mọi consumer, không quarantine, không replay, không checkpoint",
 "tag": "reliability ↔ event_published / pos_outbox",
 "summary": "ADR-0002 (07/2026) đã chẩn đúng và kê đơn notification_delivery; đơn chưa lấy.",
 "body": """
Từ [[reliability]]: 3/6 đạt (idempotency ✓, optimistic concurrency ✓, correction ✓), 1 nửa (outbox), 2 chưa (ordering, replay/quarantine).

Cụ thể chưa:
- `event_log.event_published` gộp «đã lên hàng chờ» + «đã gửi Telegram» (ADR-0002 §Context). Consumer thứ hai không dùng được → mỗi consumer mới lại đẻ một bảng outbox riêng như `pos_outbox` — hoặc, tệ hơn, dùng chung cờ và ăn trộm event của nhau.
- Không `consumer_checkpoint`: nếu policy engine ra đời, nó đọc từ đâu, đã xử lý đến event nào?
- Event không template → đánh dấu xong (không quarantine). Event lỗi validate → không có chỗ nằm.
- Relay lỗi vĩnh viễn (ví dụ token revoke như 01/09) → mỗi 30s thử lại 3 lần mãi mãi, log đầy, không DEAD, không ai được báo — trái với `pos_outbox` có DEAD.
- Không có công cụ replay có kiểm soát; replay thủ công = bật `event_published=FALSE` → bắn lại Telegram (side effect lặp — §15.6 cấm).
- Ordering: relay `ORDER BY occurred_at` toàn clinic; event cùng giây không có thứ tự ổn định; không stream_version.

Đóng bằng: [[tk-reliability-playbook]] — một giao thức tiêu thụ có xác nhận **theo từng event** (con trỏ `seq > last_seq` đơn thuần đã bị đánh dấu chưa an toàn, xem [[tk-event-envelope-v2]]); `event_quarantine`; DEAD cho notification; replay tool có guard `dry_run`/`no_side_effects`; và [[tk-communication-delivery]].
""",
 "links": ["reliability", "notification-relay", "pos-outbox", "tk-reliability-playbook", "tk-communication-delivery"],
},
{
 "id": "gap-failure-domain", "layer": L, "order": 1000, "status": "chua",
 "title": "Khoảng cách 11 — Failure không phải event: relay hỏng chỉ có log, SSE rớt màn hình im lặng",
 "tag": "failure-la-domain ↔ ops_status / relay",
 "summary": "Có health view hạ tầng; không có failure event nghiệp vụ; card không có data freshness.",
 "body": """
Có: `ops_status.py` (DB probe + snapshot host + `unknown` state), heartbeat worker cho compose healthcheck, Uptime Kuma 4 monitor + sao lưu đêm, Dozzle. Đây là quan sát **hạ tầng** tốt cho 1 người vận hành.

Không có ở tầng **nghiệp vụ**:
- `NotificationDeliveryFailed` — relay `logger.error("relay_delivery_failed")` rồi thôi.
- `ProjectionLagThresholdExceeded` — không có projector nên không có lag, nhưng SSE rớt = màn hình cũ 60s mà không ai biết.
- `IntegrationUnavailable` — chưa có integration, nhưng Telegram token revoke 01/09 chính là IntegrationUnavailable và không ai được báo trong app (chỉ khi mở Kuma).
- `AutomationBlockedByPolicy` — lab hard-block ghi `escalation_note` nhưng không event.
- `data_freshness` trên card ATC (§19.1) — không có; `_OVERVIEW_SQL` tính `wait_minutes` từ `now()` nên luôn "tươi" kể cả khi dữ liệu nguồn không được cập nhật (bệnh nhân đã đi mà không ai bấm move).

Thesis §16: «ClinicAI không chỉ hiển thị state. ClinicAI phải hiển thị khi nó không còn đủ bằng chứng để tin state đó.» Tổng-Quan §14.6 gọi mất internet là «lỗ hổng kiến trúc lớn nhất» — và freshness chính là cách nói ra điều đó trên màn hình thay vì im lặng.

Đóng bằng: [[tk-reliability-playbook]] — 4 failure event vào `event_log` stream `sys:<clinic>`; `ops_status` đọc thêm từ đó; card ATC có `last_event_at` + `freshness` = `now() − last_event_at` của stream ([[tk-atc-ui]]).
""",
 "links": ["failure-la-domain", "notification-relay", "realtime-sse", "tk-reliability-playbook", "tk-atc-ui"],
},
{
 "id": "gap-atc", "layer": L, "order": 1010, "status": "mot-phan",
 "title": "Khoảng cách 12 — ATC: có bảng toàn cảnh và cảnh báo, thiếu commitment/owner/SLA/risk/freshness/why",
 "tag": "product-surface ↔ /truong-ca/*",
 "summary": "Khung màn đúng; card thiếu 5/9 trường thesis; cảnh báo không có nút nhận/lý do/nguồn.",
 "body": """
Card thesis §19.1 (9 trường) vs `_overview_row()`:

| Trường | Có |
|---|---|
| current projected state | ✅ `current_node_name`, `room`, `floor`, `visit_status` |
| state age | ✅ `wait_minutes` (từ `current_node_since`) |
| event gần nhất + thời điểm | ❌ (chỉ suy từ `done_steps`) |
| commitment đang mở | ❌ (chỉ `next_step` nếu có tuyến) |
| owner | 🟡 `doctor_name` = bác sĩ lượt, không phải owner bước |
| SLA/timer | 🟡 `threshold_minutes` là ngưỡng, không phải deadline của một việc |
| experience risk | ❌ |
| data freshness | ❌ |
| đề xuất action + lý do | 🟡 alert `message` có câu, không có rule_id/evidence |

Cảnh báo (`build_alerts`): 4 loại đúng tinh thần khách hàng, có `patients` bị ảnh hưởng ✓; nhưng không có `id` ổn định (tính lại mỗi lần), không ack, không «vì sao tôi thấy» theo §19.3 (event nào, rule nào, evidence, confidence, ai quyết).

`thong_bao` là nút «gọi bộ phận» từ cảnh báo — vòng đóng một nửa: có `da_xu_ly` và `giay_phan_hoi` ✓, không escalation nếu không ai xử lý.

Team Queue/My Work: `/tasks` + `GET /work-items?workspace=` có `actionable_by_me`, `blocked`, blockers endpoint ✓; thiếu acknowledge, due, «vì sao tôi nhận việc này».

Timeline: `v_dispatch_history` chỉ `dispatch.*`; `v_audit_log` chỉ MANAGEMENT.

Đóng bằng: [[tk-atc-ui]] — không thêm màn, thêm trường từ [[tk-work-item-protocol]] + [[tk-experience-state]] + [[tk-reliability-playbook]]; cảnh báo trở thành derived event có id.
""",
 "links": ["product-surface", "dispatch", "man-hinh-theo-vai", "tk-atc-ui", "thong-bao"],
},
{
 "id": "gap-metrics", "layer": L, "order": 1020, "status": "chua",
 "title": "Khoảng cách 13 — Metric: đo được flow, không đo được coordination hay experience",
 "tag": "metrics-thesis ↔ reports_service / v_consultation_duration",
 "summary": "Không có dữ liệu ack/owner/coverage thì 0/5 metric coordination và 0/5 metric humane tính được.",
 "body": """
Từ [[metrics-thesis]]: tính được wait/total minutes, consultation duration, no-show/huỷ theo lý do, giây phản hồi thông báo. Không tính được: Unowned Work Time · Acknowledgement Time · Handoff Failure Rate · Escalation Resolution Time · Coordination Debt · Unexplained Waiting Time · Patient Forgotten Risk · Communication Debt · Staff Overload Minutes · Event Coverage · State Freshness.

Vì sao quan trọng ngay bây giờ: Pilot §13 khoá success criteria **sau baseline**; v2 §3.9 proof plan cần «giảm unowned work, handoff failure». Không có metric = không có baseline = không có kết luận go/no-go. Và Luật 7.2/5.3 «đo trước khi tối ưu» là luật của chính repo.

Thêm: `reports_service` gộp 8 lượt PostgREST thành 1 GROUP BY (Luật 5.1 ✓) — hình thức đúng, nội dung là báo cáo kinh doanh (lịch, doanh thu), không phải vận hành.

Đóng bằng: [[tk-metrics]] — mỗi metric = một view SQL trên `event_log` (sau [[tk-event-envelope-v2]]) hoặc trên `work_item`/`experience_state`; bảng `metric_daily` rollup; và nêu rõ metric nào chỉ có nghĩa sau phase nào (Acknowledgement Time cần Phase A; Unexplained Waiting cần Phase B).
""",
 "links": ["metrics-thesis", "tk-metrics", "tk-event-envelope-v2", "kill-criteria", "pilot-scope"],
},
{
 "id": "gap-ai", "layer": L, "order": 1030, "status": "mot-phan",
 "title": "Khoảng cách 14 — AI: đúng chỗ, có provenance, nhưng chỉ một nhánh và không Recommend nào",
 "tag": "3-muc-quyen-ai ↔ ai-hien-co",
 "summary": "Lab triage là mẫu đúng; thiếu confidence/expiry; Operations Copilot chưa thể có vì chưa có projection đáng tin.",
 "body": """
Đúng: AI ở Interpretation (phân loại lab), hard-block GROUP_C, persist trước khi trả lời, provenance model/reason/time, fallback an toàn khi không LLM, static routing, không local LLM (ADR-0005), D012/D013.

Thiếu theo thesis:
- `confidence` số + `expires_at` cho suy luận (§20.10, Spec §4).
- Derived event có `evidence_level='inferred'` — hôm nay kết quả triage là **cột** trên `lab_result`, không phải event, nên không vào timeline.
- Recommend: không có đề xuất nào được lưu «tín hiệu đầu vào, lý do, đề xuất, người phê duyệt, kết quả» (v1 §5.2). `route_derivation` gần nhất nhưng không ghi.
- Tổng-Quan §9 Copilot shadow mode: chưa — và đúng là chưa nên: TAM-NHIN «Tính năng lv4 phải chỉ được tên bảng lv3 nó đọc, và bảng đó phải đã đáng tin.» Bảng lv3 cho copilot là `event_log` + `work_item` + `experience_state` — chưa đáng tin.

`lab_result` prod 0 dòng → nhánh AI duy nhất chưa có dữ liệu thật. `scheduling` graph: «confirm không tạo lịch!» (design v5) → gate debug-only.

Đóng bằng: [[tk-ai-placement]] — không xây AI mới ở phase 0–A; Phase B thêm `evidence_level/confidence` cho derived; Phase C mới có Recommend (redistribution) dưới dạng Decision event có approver.
""",
 "links": ["3-muc-quyen-ai", "ai-hien-co", "tk-ai-placement", "4-tang-truong-thanh", "phase-c-intelligence"],
},
{
 "id": "gap-wedge-mismatch", "layer": L, "order": 1040, "status": "mot-phan",
 "title": "Khoảng cách 15 — Wedge: thesis nói in-visit, người dùng thật là CSKH trước buổi khám",
 "tag": "wedge ↔ số liệu prod",
 "summary": "Không phải lỗi kỹ thuật — là quyết định sản phẩm chưa được nói thành lời; thiết kế đích trung lập với cả hai đường.",
 "body": """
Số đo prod 04–05/09 *(chưa xác minh lại ở vòng đính chính này)*: 65 lịch thật / 66 hồ sơ, **5 tài khoản CSKH** đặt 100%; 0 lịch kênh walk-in tại thời điểm đo (ảnh chụp bảng lịch hẹn, không phải lịch sử thực thi); 1 lượt khám qua kernel; `visit_route` 0; `visit_gate_rule` 0; `lab_result` 0; `payment` 0.

Bốn thứ khác nhau, trước đây tôi gộp làm một và kết luận quá tay:

| | Đo/đọc được gì | Kết luận cho phép rút |
|---|---|---|
| **Ai tạo lịch** | 5 tài khoản CSKH, 100% | Đường vào của lịch hẹn là CSKH, không có khách tự đặt |
| **Code hỗ trợ chặng nào** | `tuong_tac_cskh` phủ cả trong buổi khám (`CHECK_IN`, `CHECK_OUT`, `THANH_TOAN`, `MUA_THUOC` — `tuong_tac_cskh_service.py:62`) và sau khám (`TRA_KQ`, `:71`) | **Không** kết luận được là code chỉ phục vụ trước buổi khám |
| **Mức dùng thật từng chặng** | 16 dòng `tuong_tac_cskh` tổng, **chưa tách theo `loai`** | Chưa đủ dữ liệu để nói chặng nào tạo giá trị |
| **Chọn wedge** | quyết định sản phẩm | Của Quang, không phải suy ra từ số đo |

Nên câu cũ «toàn bộ giá trị nằm ở chặng 1» bị rút. Phép đo còn thiếu để nói được điều gì đó chắc chắn: `tuong_tac_cskh` tách theo `loai` (biết CSKH đang chạm chặng nào), và đối soát check-in theo từng cặp `(clinic_id, appointment_id)` có xét hoàn tác. *Chưa chạy.*

Thesis v1 §11.2 chọn wedge in-visit vì «dữ liệu có tần suất cao, ROI có thể đo». Pilot §4.2 cũng chọn journey in-visit. Nhưng thesis v2 §3.5 cũng nói: «Wedge ban đầu phải tạo giá trị ngay cả khi dữ liệu và kỷ luật vận hành chưa hoàn hảo: giúp CSKH nhập hoặc cập nhật nhanh hơn; […] giảm việc nhân viên phải nhớ» — chính là thứ code đang làm.

TAM-NHIN: «CSKH là bãi thử lv4 tự nhiên» và «Trước mắt cứ làm việc mình nghĩ là có ích đã».

Hai đường không loại trừ nhau về **kiến trúc**: Work Item Protocol, expectation timer, policy engine, communication delivery dùng được cho việc CSKH (gọi xác nhận, nhắc hẹn, trả kết quả) y hệt cho việc in-visit (sinh hiệu, siêu âm, review). Chỉ khác *node nào sinh việc* và *ai là owner*.

Điều phải quyết (không phải kỹ thuật): pilot đo cái gì trước — «unexplained waiting minutes» (in-visit) hay «open commitments không owner» + «manual status-check contacts» (CSKH)? Pilot §13.3 liệt cả hai. Đề xuất của tôi trong [[cau-hoi-mo]]: Phase A áp Work Item Protocol lên **việc CSKH đang có dữ liệu** (33 `nhac_tai_kham`, 16 `tuong_tac`), Phase B mới mở in-visit khi Trưởng ca dùng thật — vì đo được ngay trên người dùng đang có.
""",
 "links": ["wedge", "cau-hoi-mo", "tk-work-item-protocol", "phase-a-closed-loop", "workflow-kernel", "pilot-scope"],
},
]
