# -*- coding: utf-8 -*-
"""Lớp 1 — HIẾN PHÁP: 9 tài liệu thesis của Quang (03/09/2026), đọc trọn 04–05/09.

Quy ước trích dẫn: «…» — *Tên tài liệu, §mục*. Mỗi nút nói: tài liệu nói gì,
nghĩa là gì với ClinicAI, và nút nào trong code/khoảng cách/thiết kế nối tới.
"""

L = 1

NODES = [
{
 "id": "north-star", "layer": L, "order": 100,
 "title": "North Star — quan sát được · điều phối được · có tính người",
 "tag": "Thesis v1 §1 · v2 §1 · v3 §1",
 "summary": "Câu định vị gốc của toàn bộ hệ thống, và câu hỏi duy nhất ClinicAI phải trả lời khác HIS/CRM/ERP.",
 "body": """
Ba bản Thesis v1→v3 mở đầu bằng cùng một câu, không đổi một chữ:

> «ClinicAI không số hóa quy trình của phòng khám. ClinicAI số hóa **trạng thái vận động** của phòng khám — để hệ thống có thể nhìn thấy điều đang xảy ra, hiểu điều gì cần xảy ra tiếp theo, điều phối người chịu trách nhiệm và tạo ra điều kiện cho việc chăm sóc tốt hơn.» — *Thesis v1, Core thesis*

Và câu phân biệt với mọi phần mềm y tế khác:

> «HIS/EHR hỏi: Hồ sơ bệnh nhân và dữ liệu lâm sàng là gì? · CRM hỏi: Quan hệ với bệnh nhân là gì? · ERP hỏi: Nguồn lực và giao dịch là gì? · Workflow software hỏi: Quy trình đã được định nghĩa phải chạy thế nào? · **ClinicAI hỏi: Ngay lúc này đang xảy ra chuyện gì, điều gì đáng lẽ phải xảy ra tiếp theo, và ai hoặc hệ thống nào chịu trách nhiệm để nó xảy ra?**» — *Thesis v1 §1*

North Star:

> «Make the clinic observable, coordinated, and humane. — Làm cho phòng khám có thể quan sát được, được điều phối tốt và vận hành có tính người.» — *Thesis v1 §1*

### Nghĩa là gì với code

Ba tính từ ấy là ba bài kiểm cho mọi tính năng. Đối chiếu code hôm nay:

| | Câu hỏi | Code trả lời được chưa |
|---|---|---|
| **Observable** | Bệnh nhân này đang ở đâu, chờ gì, bao lâu? | Một phần — `visit.current_node_code/current_room_id` + bảng Trưởng ca (xem [[dispatch]]). Nhưng chỉ **1 lượt khám** trên prod từng đi qua kernel ([[workflow-kernel]]). |
| **Coordinated** | Ai chịu trách nhiệm bước tiếp theo, đã nhận chưa, quá hạn chưa? | Chưa — `work_item` không có acknowledge/SLA/escalation ([[gap-work-item]]). |
| **Humane** | Bệnh nhân có bị chờ mà không được giải thích không? | Chưa — không có khái niệm *communication coverage* hay Experience State ([[gap-experience-state]]). |

Thesis cũng nói thẳng câu sâu hơn North Star: «Better operational conditions → Better human behavior → Better care» (*v1 §1*). Tức là mục tiêu không phải throughput; [[humane-ops]] là điều kiện đạo đức để hệ được phép tồn tại trong y tế (*v3 §2.13*).
""",
 "links": ["vong-lap", "ontology-9", "humane-ops", "wedge", "4-tang-truong-thanh", "gap-work-item", "gap-experience-state", "dispatch"],
},
{
 "id": "vong-lap", "layer": L, "order": 110,
 "title": "Vòng lặp Reality → Event → State → Interpretation → Decision → Action",
 "tag": "Thesis v1 §5 · Care Model §1",
 "summary": "Mô hình vận hành cốt lõi; Care Model v1 đảo lại thứ tự nhân quả so với cách code đang làm.",
 "body": """
Thesis v1 §5 vẽ vòng lặp khép kín:

> «Reality → Event → State → Interpretation → Decision → Action → New Reality. AI nằm chủ yếu ở hai khâu Interpretation và Decision. AI không được rải khắp sản phẩm chỉ để tạo cảm giác "có AI".» — *Thesis v1 §1*

> «Một event chỉ có giá trị vận hành khi nó làm thay đổi nhận thức hoặc hành động của hệ thống.» — *Thesis v1 §5*

Care Model v1 §1 nói vì sao phải **viết lại theo event-first** — và đây là câu quan trọng nhất để soi code:

> «Bản Care Delivery Model trước […] về bản chất vẫn là mô hình trạng thái có thêm Event. Nó khiến người đọc có thể hiểu rằng: (1) UI hoặc workflow cập nhật một trạng thái; (2) hệ thống lưu trạng thái đó; (3) sau đó phát một event để các module khác biết. **Đó là "CRUD có message", chưa phải ClinicAI event-driven theo nghĩa mạnh.**» — *Care Model §1*

Thứ tự nhân quả mới, 7 bước:

> «(1) Một sự thật xảy ra […]; (2) ClinicAI ghi nhận sự thật đó dưới dạng event bất biến; (3) các projection diễn giải event để tạo ra trạng thái hiện tại; (4) policy và process manager quyết định phản ứng; (5) hệ thống phát command hoặc tạo Work Item; (6) hành động ngoài đời tạo ra outcome event mới; (7) **vòng lặp chỉ đóng khi outcome được quan sát.**» — *Care Model §1*

Và bài kiểm quyết định:

> «Nếu xóa tất cả dashboard và bảng trạng thái, ClinicAI phải có khả năng dựng lại chúng từ event history. Nếu không làm được, event chưa phải là nền tảng của hệ thống.» — *Care Model §1*

### Code hôm nay đứng ở bước nào

Code hiện tại làm đúng **(1)→(2)** ở mức "ghi vết trong cùng transaction" (ví dụ `episode_service.py:105`, `tuong_tac_cskh_service.py:249`), nhưng theo chiều **state trước, event sau** — đúng cái "CRUD có message" mà §1 gọi tên ([[gap-crud-roi-log]]). Bước (3) projection có thật ở [[cskh-views]] và `visit.current_node_code`, nhưng dựng từ **bảng trạng thái**, không từ event. Bước (4)–(7) chưa có: không policy engine, không process manager, không outcome event đóng vòng ([[gap-process-manager]], [[gap-timer]]).

Thiết kế đích không đòi viết lại: nó đòi **đảo chỗ ngồi** — mọi thay đổi trạng thái đi qua một cửa ghi sự kiện ([[tk-emit-function]]), rồi projection/policy đọc từ đó ([[tk-policy-engine]], [[tk-projections]]).
""",
 "links": ["north-star", "event-first-dao-nhan-qua", "gap-crud-roi-log", "gap-process-manager", "gap-timer", "cskh-views", "tk-emit-function", "tk-policy-engine", "3-muc-quyen-ai"],
},
{
 "id": "ontology-9", "layer": L, "order": 120,
 "title": "Ontology — 9 thực thể lõi và bảng nào trong code đang gánh chúng",
 "tag": "Thesis v1 §4.1",
 "summary": "Patient · Encounter · Node · Event · State · Work Item · Actor/Resource · Policy/SLA · Experience State — ánh xạ từng cái sang bảng thật.",
 "body": """
> «Ontology là bộ khái niệm gốc mà từ đó dữ liệu, tính năng và quyết định được xây dựng. Nếu ontology sai, sản phẩm sẽ dần trở thành một tập hợp tính năng rời rạc.» — *Thesis v1 §4*

Bảng gốc (*v1 §4.1*) và ánh xạ sang lược đồ prod (79 bảng, đo 05/09/2026):

| Thực thể | Câu hỏi nó trả lời | Trong code hôm nay | Nhận xét |
|---|---|---|---|
| **Patient** | Ai đang được chăm sóc? | `patient` (+`patient_sdt_them`, `patient_medical_profile`, `pregnancy`, `patient_link`) | ✅ Đủ. Đa SĐT, MPI dò trùng có. |
| **Encounter** | Một lần chăm sóc đang diễn ra trong bối cảnh nào? | `visit` (lượt khám) — *không phải* `appointment` | ✅ Tách đúng: «`appointment` là lời hứa, `visit` là sự việc» (*GIAI-THICH-CODE §0.4*). `care_episode` = nhiều encounter. |
| **Node** | Encounter đang ở đâu trong hệ thống dịch vụ? | `node_definition` (41 node) + `clinic_room` (12 phòng) + `visit.current_node_code` | ✅ Có, và **là dữ liệu** (ADR-0011). Thesis không tách "node" khỏi "phòng"; code đã tách ([[dispatch]]). |
| **Event** | Điều gì vừa thực sự xảy ra? | `event_log` (449 dòng, 17 loại) | 🟡 Có bảng, thiếu envelope, thiếu độ phủ ([[gap-envelope]]). |
| **State** | Reality hiện tại của đối tượng là gì? | `appointment.status`, `visit.status`, `work_item.status`, `v_trang_thai_cskh` | 🟡 Là **cột được ghi**, không phải projection từ event — trừ view CSKH ([[gap-projection-rebuild]]). |
| **Work Item** | Điều gì cần được làm? | `work_item` (5 trạng thái) + `nhac_tai_kham` + `thong_bao` + `hen_goi_lai` + `follow_up_case` | 🟡 Kernel có nhưng thiếu ownership/ack/SLA ([[gap-work-item]]); việc CSKH sống ở view chứ không ở bảng. |
| **Actor / Resource** | Ai hoặc nguồn lực nào có thể thực hiện? | `staff` + `clinic_membership` (13 vai) · `clinic_room` · `work_roster` (ca trực) | ✅ Người và phòng có; **thiết bị** chưa là thực thể. |
| **Policy / SLA** | Khi nào trạng thái trở thành bất thường? | `luat_cskh` (11) · `dispatch_threshold` · `visit_gate_rule` · `luat_bac_si_bat_buoc` · `*_booking_override` · `clinic.settings` | ✅ Luật là dữ liệu — mạnh nhất trong 9 thực thể ([[policy-as-data-hien-co]]). Nhưng SLA cho *work item* thì chưa có. |
| **Experience State** | Bệnh nhân đang có nguy cơ trải nghiệm điều gì? | — | ❌ Không có gì ([[gap-experience-state]]). |

Kết luận đọc được từ bảng: **8/9 thực thể đã có chỗ đứng trong lược đồ**, thực thể thiếu hẳn là Experience State. Nhưng ba thực thể giữa (Event · State · Work Item) mới có *hình dạng* chứ chưa có *nghĩa* theo thesis — đó chính là toàn bộ [[gap-crud-roi-log]] và [[gap-work-item]].

Thesis cũng dặn về FHIR: «có thể ánh xạ với chuẩn FHIR phù hợp — Encounter, Task, HealthcareService, Location — nhưng ClinicAI cần giữ một operational model đủ linh hoạt» (*v1 §4.1*); Care Model §27 nói rõ hơn ở [[fhir-mapping]].
""",
 "links": ["event-vs-record", "workflow-kernel", "dispatch", "appointment-visit-tuongtac", "policy-as-data-hien-co", "gap-envelope", "gap-projection-rebuild", "gap-work-item", "gap-experience-state", "fhir-mapping"],
},
{
 "id": "event-vs-record", "layer": L, "order": 130,
 "title": "Event khác record — lịch hẹn là ý định, PatientArrived là sự thật",
 "tag": "Thesis v1 §4.2",
 "summary": "Bốn loại thứ hay bị gộp làm một: record, event quan sát, thay đổi state, event suy ra, event xác nhận hành động.",
 "body": """
> «Record trả lời: "Thông tin đã được lưu là gì?" Event trả lời: "Điều gì đã xảy ra, khi nào, với ai, ở đâu và do nguồn nào xác nhận?"» — *Thesis v1 §4.2*

Ví dụ nguyên văn — năm dòng, năm bản chất khác nhau:

> «Lịch hẹn 10:00 là record về ý định. · PatientArrived lúc 10:17 là event về reality. · EncounterCreated là thay đổi state của hệ thống. · WaitingThresholdExceeded là event được suy ra. · PatientInformed là event xác nhận một hành động chăm sóc đã được thực hiện.» — *Thesis v1 §4.2*

> «Event phải đủ bất biến để tạo lịch sử tin cậy. State là kết quả hiện tại được dựng từ chuỗi event. Work Item là cam kết rằng một actor cụ thể sẽ biến state hiện tại thành state mong muốn.» — *Thesis v1 §4.2*

### Code đã hiểu đúng một nửa

Phần code hiểu đúng — và hiểu từ một lỗi thật: `appointment` ≠ `visit` ≠ `tuong_tac_cskh`. `docs/GIAI-THICH-CODE.md §0.4` gọi ba thứ là **lời hứa · sự việc · lần chạm**, và chép lại sự cố 06/08: khách về giữa chừng, cách duy nhất là huỷ lịch hẹn, «hồ sơ trông như người ấy chưa từng đến» → sinh trạng thái `INCOMPLETE` (`20260806000004_luot_kham_do.sql`). Đó chính là "record về ý định ≠ event về reality" nói bằng tiếng Việt.

Phần chưa: **event bất biến** hiện là *phụ phẩm* của việc đổi cột trạng thái — `booking_service.apply_action()` UPDATE `appointment.status` rồi mới INSERT `event_log` (cùng transaction, nhưng chiều nhân quả ngược). Và ba loại event còn lại của ví dụ trên — *event suy ra* (WaitingThresholdExceeded), *event xác nhận hành động* (PatientInformed) — không tồn tại như event: cảnh báo chờ lâu được **tính lúc đọc** trong `dispatch_service.build_alerts()` và biến mất khi đóng tab; "đã trả kết quả" là một dòng `tuong_tac_cskh` loại `TRA_KQ` chứ chưa được coi là outcome event đóng một commitment.

Nút [[5-loai-event]] mở rộng năm bản chất này thành bảng phân loại chính thức.
""",
 "links": ["ontology-9", "5-loai-event", "appointment-visit-tuongtac", "gap-crud-roi-log", "tuong-tac-cskh"],
},
{
 "id": "10-principles", "layer": L, "order": 140,
 "title": "10 nguyên tắc sản phẩm — và nguyên tắc nào code đang vi phạm",
 "tag": "Thesis v1 §7",
 "summary": "Từ Reality before workflow tới Learn from every loop; mỗi nguyên tắc chấm điểm code hiện tại.",
 "body": """
Nguyên văn mười nguyên tắc (*Thesis v1 §7*), kèm đối chiếu:

1. **Reality before workflow** — «Quy trình là giả định về tương lai. Event là bằng chứng về điều đã xảy ra. Khi hai thứ xung đột, ClinicAI ưu tiên reality và làm rõ sai lệch.» → Code: kernel sinh 7 bước xương sống lúc check-in (`instantiate_visit_workflow`) = *expected journey*; nhưng không có gì so sánh expected với actual ([[gap-process-manager]]).
2. **Every important state must be observable** — «…hệ thống phải nhìn thấy hoặc **biết rằng mình chưa nhìn thấy**.» → Code không biểu diễn "không biết": `ops_status.py` có `unknown`, còn màn điều phối thì im lặng khi thiếu dữ liệu ([[gap-failure-domain]]).
3. **Every next action must have ownership** — «Không có "hệ thống đã thông báo" nếu không xác định được ai chịu trách nhiệm, đã acknowledge chưa và khi nào cần escalation.» → Vi phạm trực tiếp: relay Telegram coi `event_published = TRUE` là xong, mà cờ ấy được đặt ở hai nhánh — sự kiện **không có template** thì đánh dấu mà không gửi gì (`notification_relay.py:205-214`), sự kiện gửi được thì đánh dấu khi nhà cung cấp trả ok (`:238`). Cả hai đều khác "người đã nhận và đã hiểu"; `thong_bao` có `da_xu_ly_luc` nhưng không escalation ([[gap-communication]], [[gap-work-item]]).
4. **Exception is first-class** — → Code làm tốt ở đặt lịch (5 mã lý do huỷ, `BAC_SI_DOI_LICH`, cờ mất bác sĩ) và điều phối (`visit_route.is_exception` bắt lý do). Điểm cộng thật.
5. **Human attention is a scarce resource** — «ClinicAI không đẩy thêm notification. Nó phải lọc, ưu tiên, gom ngữ cảnh…» → `v_trang_thai_cskh` chọn *một việc gấp nhất* mỗi khách — đúng tinh thần. `thong_bao` chống bấm hai lần bằng unique index — đúng. Nhưng chưa có ngân sách cảnh báo (Tổng-Quan §14.4: «tối đa 1 cảnh báo chặn/lượt khám»).
6. **Transparency is care** — → Chưa có kênh nào nói với *bệnh nhân* (Zalo OA chưa xây; `/display` chỉ gọi số).
7. **Optimize the system, not the individual** — → Báo cáo hiện tại không chấm điểm cá nhân — nhưng cũng chưa đo coordination debt ([[gap-metrics]]).
8. **AI must be accountable** — → `lab_result.triage_model`, `triage_reason`, `triage_classified_at` có sẵn cột provenance ✅; GROUP_C hard-block ✅ ([[ai-hien-co]]).
9. **Interoperate, do not replace by default** — → `PosPort` + `NullPosAdapter` (ADR-0010) là mẫu đúng; lab/LIS chưa có adapter.
10. **Learn from every loop** — «Event history không chỉ phục vụ audit.» → `event_log` hôm nay 62% là `slot_hold`. Nó vẫn đang được đọc làm nhật ký thao tác, nhưng chưa học được gì từ nó vì thiếu correlation và thiếu event vòng đời — không phải vì tỷ lệ nhiễu ([[gap-envelope]]).

Điểm số thô: **3 làm tốt (4, 8, 9)**, 2 làm một phần (5, 1), **5 chưa đạt (2, 3, 6, 7, 10)** — và cả 5 cái chưa đạt đều quy về một gốc: thiếu vòng lặp *ownership → ack → outcome* trên một sổ sự kiện đủ nghĩa.
""",
 "links": ["north-star", "gap-process-manager", "gap-failure-domain", "gap-communication", "gap-work-item", "gap-metrics", "gap-envelope", "ai-hien-co", "pos-outbox"],
},
{
 "id": "6-lop-san-pham", "layer": L, "order": 150,
 "title": "Product map 6 lớp — Sensing · State · Coordination · Intelligence · Interfaces · Governance",
 "tag": "Thesis v1 §8",
 "summary": "Bản đồ sản phẩm chính thức; mọi module chỉ được thêm khi phục vụ một lớp — và code hiện dồn vào lớp nào.",
 "body": """
> «Các module appointment, CRM, EHR-lite, follow-up hay inventory chỉ nên được đưa vào khi chúng phục vụ một hoặc nhiều lớp nói trên. Product map không được quay lại logic "có feature nào thì thêm feature đó".» — *Thesis v1 §8*

Sáu lớp nguyên văn, và code đang ở đâu:

| Lớp | Năng lực (thesis) | Sản phẩm biểu hiện (thesis) | Code hôm nay |
|---|---|---|---|
| 1. Sensing | Thu event từ hệ thống và thế giới thật | Check-in, integration, nhập nhanh, thiết bị, event API | Check-in RPC, mốc quầy `tuong_tac_cskh` (CHECK_IN/OUT/THANH_TOAN/MUA_THUOC), `move_visit_to_station`. Không integration, không thiết bị. |
| 2. Operational State | Dựng trạng thái hiện tại | Encounter timeline, node, resource state, experience state | `visit.current_*`, `_STATIONS_SQL` (tải phòng), `v_viec_cskh`. Không experience state. |
| 3. Coordination | Tạo và phân phối công việc | Work Item, queue, ownership, SLA, escalation, handoff | `work_item` + gate SQL; `thong_bao` (gọi bộ phận). Không SLA/escalation/handoff-ack. |
| 4. Intelligence | Hiểu, dự báo, đề xuất | Risk detection, ETA, prioritization, recommendation | Lab triage (LLM + rule) là thứ duy nhất. |
| 5. Human Interfaces | Biến state thành nhận thức và hành động | Air Traffic Control, role views, patient status, daily brief | 55 màn theo 13 vai; `/truong-ca/*` 5 màn; `/display` TV; `pre_visit_brief` graph. |
| 6. Learning & Governance | Đo, truy nguyên và cải tiến | Analytics, audit, simulation, policy, AI governance | `v_audit_log` + `/audit-log`; `reports_service`; RLS tenant/role; **policy có nhưng không version**. |

Đọc bảng thấy hình dạng thật của sản phẩm: **nặng ở lớp 5 (giao diện) và lớp 1 (nhập tay), rỗng ở lớp 3–4**. 326 file TS/TSX so với 212 file Python là một chỉ dấu; `booking_service.py` 2.037 dòng là module dày nhất — tức là tiền và công đang đổ vào *appointment*, thứ thesis liệt vào «không phải appointment software» (*v1 §3.2*).

Thiết kế đích ([[tk-modular-monolith]]) xếp lại thư mục backend theo đúng 6 lớp này để ranh giới nằm trong code, đúng ADR-0001 chưa thi hành.
""",
 "links": ["north-star", "wedge", "man-hinh-theo-vai", "workflow-kernel", "ai-hien-co", "tk-modular-monolith", "gap-wedge-mismatch"],
},
{
 "id": "4-tang-truong-thanh", "layer": L, "order": 160,
 "title": "Bốn tầng trưởng thành của thesis và thang lv1→lv5 của Quang",
 "tag": "Thesis v1 §10 · docs/TAM-NHIN.md",
 "summary": "Hai thang đo cùng một thứ; ClinicAI đang xây nền lv3 (= Level 2 digital record) và thesis đòi Level 4.",
 "body": """
Thesis (*v1 §10*):

| Tầng | Đặc điểm | Giới hạn |
|---|---|---|
| Level 1 — Human-memory operation | Reality nằm trong đầu người; ai nhớ thì việc chạy | Phụ thuộc cá nhân, lỗi vô hình |
| Level 2 — Digital record | SaaS ghi lại dữ liệu; con người nhìn dashboard và tự điều phối | **Có dữ liệu nhưng chưa tạo closed loop** |
| Level 3 — AI-assisted operation | Hệ thống hiểu state, phát hiện bất thường và đề xuất hành động | Con người vẫn là bottleneck điều phối |
| Level 4 — Event-driven intelligent organization | Reality tự kích hoạt coordination trong guardrail rõ ràng | Đòi hỏi event coverage, governance và niềm tin cao |

Thang của Quang chốt 24/08 (`docs/TAM-NHIN.md`): lv1 người+quan hệ · lv2 quy trình · lv3 SaaS (record) · lv4 AI đọc state → khuyến nghị · lv5 tự cải thiện từ ngoại lệ. Hai thang khớp nhau lệch một bậc: **Level 2 thesis = lv3 Quang; Level 3 = lv4; Level 4 ≈ lv5**.

Định vị hôm nay (TAM-NHIN): «Phòng khám Dr4Women: lv1–2 · ClinicAI: đang xây nền lv3.» Nợ lv3 có số: «42/63 route dashboard còn chạm thẳng database».

Thesis mô tả Level 4 bằng 6 phản xạ — đây là **bảng kiểm hành vi** cho thiết kế đích:

> «PatientArrived → tạo encounter và work item tiếp đón. · LabResultReady → bác sĩ được đưa đúng context và journey tiếp tục. · WaitingThresholdExceeded → CSKH nhận task giải thích. · StaffOverloaded → trưởng ca nhận đề xuất redistribution. · PatientLeftClinic → follow-up workflow bắt đầu. · MissingExpectedEvent → hệ thống chủ động hỏi hoặc escalation thay vì giả định mọi thứ bình thường.» — *Thesis v1 §10*

Đối chiếu code: phản xạ 1 **có** (check-in → `instantiate_visit_workflow` sinh work item). Năm phản xạ còn lại **không có**, và cả năm đều cần cùng ba mảnh: sự kiện đủ nghĩa ([[tk-event-envelope-v2]]), bộ hẹn giờ phát hiện "chưa xảy ra" ([[tk-expectation-timer]]), policy phản ứng ([[tk-policy-engine]]).

Luật rút ra từ TAM-NHIN mà thiết kế này tuân theo: «Tính năng lv4 phải chỉ được tên bảng lv3 nó đọc, và bảng đó phải đã đáng tin.» Vì thế [[lo-trinh-tong]] bắt đầu từ sổ sự kiện, không từ AI.
""",
 "links": ["north-star", "lo-trinh-tong", "tk-event-envelope-v2", "tk-expectation-timer", "tk-policy-engine", "instantiate-visit", "3-muc-quyen-ai"],
},
{
 "id": "3-muc-quyen-ai", "layer": L, "order": 170,
 "title": "Ba mức quyền hành động — Observe · Recommend · Act",
 "tag": "Thesis v1 §5.2 · Care Model §14",
 "summary": "AI chỉ ở Interpretation/Decision; quyền tự hành động tuỳ rủi ro, khả năng hoàn tác và trách nhiệm chuyên môn.",
 "body": """
> «AI không được tự động hóa một quyết định chỉ vì quyết định đó có thể được mô hình dự đoán. Quyền tự động phải phụ thuộc vào mức rủi ro, khả năng hoàn tác và trách nhiệm chuyên môn.» — *Thesis v1 §5.1*

| Mức | Vai trò hệ thống | Ví dụ (thesis) |
|---|---|---|
| Observe | Nhìn thấy và cảnh báo | Phát hiện bệnh nhân chờ quá SLA |
| Recommend | Đề xuất, con người phê duyệt | Đề xuất chuyển encounter sang bác sĩ khác |
| Act | Tự hành động trong guardrail rõ ràng | Gửi cập nhật trạng thái đã được phê duyệt trước |

> «ClinicAI phải luôn lưu được: tín hiệu đầu vào, lý do, đề xuất hoặc hành động, người phê duyệt và kết quả.» — *Thesis v1 §5.2*

Care Model §14 nêu 7 yếu tố quyết định mức quyền: clinical risk · reversibility · confidence · data sensitivity · policy của cơ sở · vai trò chịu trách nhiệm · khả năng audit và rollback. Và: «AI có thể diễn giải signal, nhưng clinical decision không được ngầm chuyển thành automation nếu chưa có governance tương ứng.»

Khi nào AI phù hợp (*v1 §5.1*): state không xác định được bằng rule đơn giản · cần tổng hợp nhiều tín hiệu · cần dự báo · nhiều phương án điều phối · diễn giải ngôn ngữ tự nhiên · học từ lịch sử nhưng người chịu trách nhiệm cuối.

### Code hôm nay xếp vào mức nào

- **Observe**: `dispatch_service.build_alerts()` (4 loại cảnh báo), `v_viec_cskh` (11 loại việc suy ra). Đây là *rule*, đúng như Experience Spec §13 khuyên cho pilot: «ưu tiên rule-based inference vì dễ giải thích và đo».
- **Recommend**: chưa có gì. `route_derivation.derive_route()` gợi ý tuyến từ chỉ định — gần nhất với Recommend, nhưng không ghi lại "đề xuất/ai duyệt/kết quả".
- **Act có guardrail**: lab triage GROUP_C → `hard_block` + tạo `staff_task` URGENT SLA 4h (`graphs/lab_triage/graph.py`). Đây là Act ở mức *chặn* (an toàn), không phải Act ở mức *gửi đi*. Relay Telegram là Act không guardrail — nó gửi mọi `appointment.*` có template (`notification_templates.TEMPLATES`, 5 mẫu) cho *nhóm nội bộ*, không cho bệnh nhân — nên rủi ro thấp, chấp nhận được.

Lằn ranh cấm đã có trong repo và thiết kế này giữ nguyên: **D012** không chatbot tư vấn lâm sàng cho bệnh nhân; **D013** không risk-scoring AI (design v5 §5.7). Chi tiết vị trí AI trong thiết kế đích: [[tk-ai-placement]].
""",
 "links": ["vong-lap", "ai-hien-co", "tk-ai-placement", "experience-state", "dispatch"],
},
{
 "id": "wedge", "layer": L, "order": 180,
 "title": "Wedge — In-visit Operational Coordination, không phải đặt lịch",
 "tag": "Thesis v1 §11.2 · v2 §12.2",
 "summary": "Thesis chọn điểm cắm là điều phối TRONG buổi khám; code hiện dày nhất ở TRƯỚC buổi khám (CSKH đặt lịch).",
 "body": """
> «Wedge nên là In-visit Operational Coordination cho phòng khám tư nhân nhiều cơ sở: quan sát toàn bộ encounter đang hoạt động; quản lý node và bước tiếp theo; queue và Work Item theo vai trò; phát hiện chờ quá SLA và patient forgotten risk; workload view cho trưởng ca; timeline sự kiện để audit và handoff; communication trigger cho CSKH.» — *Thesis v1 §11.2*

> «Đây là nơi đau vận hành rõ, dữ liệu có tần suất cao, ROI có thể đo, và ClinicAI khác biệt rõ nhất so với appointment/CRM/HIS thông thường. Appointment, onboarding và post-visit follow-up sẽ nối vào hai đầu của cùng một encounter lifecycle.» — *Thesis v1 §11.2*

Thứ tự ưu tiên roadmap (*v1 §11.1*), nguyên văn 7 bước: (1) Nhìn thấy reality · (2) Tạo ownership · (3) Situational awareness · (4) Đóng patient communication loop · (5) Operational intelligence · (6) Tự động hoá có kiểm soát · (7) Học xuyên cơ sở.

### Chỗ lệch lớn nhất giữa thesis và code

Đo trên prod 04–05/09/2026:
- 65 lịch hẹn thật, **100% do 5 tài khoản CSKH** đặt; 0 lịch kênh walk-in tại thời điểm đo; 1 lượt khám đi qua kernel.
- Module dày nhất: `booking_service.py` (2.037 dòng), `tuong_tac_cskh_service.py` (883), `booking_override_service.py` (852) — toàn *trước* buổi khám.
- Điều phối trong buổi (`dispatch_service.py` 633 dòng, 5 màn `/truong-ca/*`) có, nhưng lúc đo **`visit_route` 0 dòng** và `visit_gate_rule` 0 dòng *(số đo 04–05/09, chưa đo lại)*.

Tức là **sản phẩm đang bán cho CSKH cái thesis gọi là "hai đầu"**, còn cái thesis gọi là *wedge* thì xây rồi để đó. Không phải lỗi ai: người dùng thật hôm nay là 10 CSKH của Dr4Women, và họ đặt lịch. Nhưng đây là quyết định phải nói ra, không để trôi — [[cau-hoi-mo]] câu 1.

Hai đường khả dĩ: (A) giữ CSKH làm bãi thử lv4 (đúng TAM-NHIN: «CSKH là bãi thử lv4 tự nhiên») và áp *cùng khuôn* Work Item/ownership/SLA lên việc CSKH trước; (B) chuyển trọng tâm sang in-visit theo đúng Pilot Proposal. Thiết kế đích ([[tk-work-item-protocol]]) cố ý **trung lập**: khuôn Work Item dùng được cho cả hai — chỉ khác node nào sinh việc.
""",
 "links": ["north-star", "6-lop-san-pham", "gap-wedge-mismatch", "pilot-scope", "cau-hoi-mo", "tk-work-item-protocol", "dispatch"],
},
{
 "id": "kill-criteria", "layer": L, "order": 190,
 "title": "Kill criteria, proof plan và baseline Excel + Zalo",
 "tag": "Thesis v2 §3.3 · §3.9 · §3.10",
 "summary": "Thesis là giả thuyết có điều kiện bác bỏ; pilot phải so với một baseline đủ mạnh chứ không so với hỗn loạn.",
 "body": """
> «Bài kiểm tra bắt buộc: Pilot phải so ClinicAI với một baseline đủ mạnh — ví dụ Excel + quy tắc vận hành được cải tiến — chứ không so với hiện trạng hỗn loạn. Nếu một giải pháp đơn giản tạo gần như toàn bộ giá trị với chi phí thấp hơn, không nên xây một hệ thống phức tạp.» — *Thesis v2 §3.3*

Bảy đặc điểm khiến thủ công không bền (*v2 §3.3*): nhiều state đổi đồng thời · nhiều actor phụ thuộc · ngoại lệ thường xuyên · tốc độ phản ứng ảnh hưởng outcome · không thấy toàn cảnh từ bảng tĩnh · chi phí "hỏi nhau" tăng theo quy mô · lịch sử tạo năng lực dự báo.

Proof plan (*v2 §3.9*) — 7 giả thuyết, mỗi cái có tín hiệu ủng hộ/bác bỏ. Hai dòng đáng nhớ nhất cho kỹ thuật:

| Giả thuyết | Ủng hộ | Bác bỏ |
|---|---|---|
| Reality có thể quan sát | State đủ mới với ít thao tác thêm | Nhiều state sai hoặc phải nhập kép |
| Coordination tốt hơn | Giảm unowned work, handoff failure | **Chỉ chuyển việc sang notification** |

Kill criteria (*v2 §3.10*), trích những điều chạm thẳng vào thiết kế:

> «không quan sát được phần lớn encounter mà không tăng đáng kể thao tác nhập liệu; · event đến quá chậm hoặc không đủ tin cậy để điều phối; · […] · AI không tạo thêm giá trị đáng kể so với rule và dashboard; · việc tăng visibility làm tăng giám sát, áp lực hoặc hành vi đối phó nhiều hơn chất lượng chăm sóc.»

> «Nếu thất bại tập trung ở AI nhưng coordination loop vẫn tạo giá trị, nên bỏ bớt AI chứ không nhất thiết bỏ ClinicAI. Nếu thất bại ở việc thu nhận reality hoặc adoption, core thesis cần được xem xét lại.» — *v2 §3.10*

### Hệ quả cho thiết kế

1. Mọi thứ trong [[lo-trinh-tong]] phải **đo được trước/sau** — vì thế [[tk-metrics]] không phải việc cuối mà là việc đi kèm từng phase.
2. Thiết kế phải chịu được kết luận "bỏ AI": mọi mảnh trong [[tk-policy-engine]] và [[tk-experience-state]] chạy bằng **rule** trước; AI là lớp cắm thêm.
3. "Chỉ chuyển việc sang notification" là chế độ thất bại **đang xảy ra** trên code (relay = sent = done) — [[gap-communication]] phải đóng trước khi đo bất cứ gì.
""",
 "links": ["lo-trinh-tong", "tk-metrics", "tk-policy-engine", "tk-experience-state", "gap-communication", "7-tieu-chi-event-source"],
},
{
 "id": "7-tieu-chi-event-source", "layer": L, "order": 200,
 "title": "Bảy tiêu chí cho mọi nguồn event — value per unit of data-entry burden",
 "tag": "Thesis v2 §3.4",
 "summary": "Điều kiện khả thi quan trọng nhất: thu được reality mà không bắt người làm thư ký; thước đo cho IoT, camera, nhập tay.",
 "body": """
> «Toàn bộ thesis phụ thuộc vào khả năng quan sát reality. Nếu event thiếu, chậm hoặc sai, state và mọi đề xuất phía sau đều không đáng tin.» — *Thesis v2 §3.4*

Nguồn event có thể gồm (*v2 §3.4*): thao tác tự nhiên trong quá trình làm việc · dữ liệu từ HIS, LIS, POS, CRM và lịch hẹn · check-in, QR hoặc kiosk · xác nhận tối giản của nhân viên · thiết bị, badge hoặc camera ở nơi phù hợp · event được suy ra từ nhiều tín hiệu.

> «Nguyên tắc thiết kế: **Không bắt con người làm thư ký cho một hệ thống tự nhận là thông minh.**» — *v2 §3.4*

Bảy tiêu chí đánh giá mỗi event: (1) giá trị quyết định mà nó mở khoá · (2) độ chính xác · (3) độ trễ · (4) chi phí tích hợp · (5) thao tác bổ sung cho nhân viên · (6) rủi ro riêng tư và pháp lý · (7) khả năng duy trì khi pilot kết thúc.

> «Một chỉ số nền tảng của ClinicAI phải là: **Value created per unit of data-entry burden.**» — *v2 §3.4*

### Áp vào ClinicAI

Đây là thước đo đã dùng trong cuộc debate IoT 04/09 (memory `thesis-clinicai-cua-quang-0309`): vòng BLE/camera là nguồn *cắm thêm sau*, không phải thứ thiết kế quanh — Event Catalog §6 đã chừa `PatientLocationObserved{location, method, confidence}` cho việc đó, và Pilot Proposal §5 xếp «camera/IoT diện rộng» ngoài phạm vi.

Nguồn event **rẻ nhất đang có sẵn** trong code, xếp theo tiêu chí 5 (thao tác thêm ≈ 0):
- Chuyển trạng thái lịch hẹn (`booking_service.apply_action`) — nhân viên đã bấm để làm việc, event là phụ phẩm miễn phí.
- Mốc quầy `CHECK_IN / CHECK_OUT / THANH_TOAN / MUA_THUOC` trong `tuong_tac_cskh` — một chạm.
- `move_visit_to_station` — Trưởng ca chuyển phòng = một event vị trí có nguồn `staff`.
- Kết quả xét nghiệm nhập tay (`lab_result.result_received_at`) — chưa có LIS.

Nguồn **đắt nhất theo tiêu chí 5**: bắt điều dưỡng bấm `start`/`complete` từng work item. Migration `20260731000003` đã thấy điều này và cho `LUOTKHAM-01` sinh ra ở trạng thái `COMPLETED` ngay lúc check-in: «pressing check-in IS performing tiếp nhận người bệnh». Thiết kế đích ([[tk-sensing]]) đi đúng hướng ấy: **suy event từ thao tác đã có** trước, hỏi người sau cùng.
""",
 "links": ["tk-sensing", "event-catalog", "pilot-scope", "kill-criteria", "tuong-tac-cskh"],
},
{
 "id": "humane-ops", "layer": L, "order": 210,
 "title": "Design for Humane Operations — không biến y đức thành điểm số",
 "tag": "Thesis v1 §6 · v3 §2.13",
 "summary": "Bảo vệ bệnh nhân, bảo vệ nhân viên, và điều kiện đạo đức để hệ thống được phép tồn tại trong y tế.",
 "body": """
> «Một hệ thống vận hành tốt không chỉ tăng throughput. Nó phải giúp hành vi tử tế trở thành lựa chọn dễ nhất trong điều kiện làm việc hàng ngày.» — *Thesis v1 §6*

Bảo vệ bệnh nhân (*§6.1*): không để bị "quên"; không chờ mà không có chủ sở hữu; chuyển trạng thái nội bộ thành lời giải thích; **phân biệt chờ cần thiết và chờ do lỗi điều phối**; nhận diện bối cảnh lo âu cao; truy nguyên khi khiếu nại.

Bảo vệ nhân viên (*§6.2*): «Dashboard kiểu Air Traffic Control không chỉ hỏi "bệnh nhân nào gặp vấn đề?" mà còn phải hỏi "nhân viên nào đang bị quá tải?"» — cần thấy: số encounter active mỗi người · số chờ quá SLA · work item pending · escalation chưa xử lý · thời gian liên tục trên ngưỡng tải.

Không chấm điểm (*§6.3*):

> «ClinicAI không nên tạo chỉ số "Y đức bác sĩ A = 87/100". Một con số như vậy vừa giản lược đạo đức, vừa dễ trở thành công cụ trừng phạt.» — *v1 §6.3*

Điều kiện đạo đức (*v3 §2.13*): «Dùng visibility để sửa hệ thống; không dùng visibility để vắt kiệt con người.» — «Design for Humane Operations vì thế không chỉ là positioning. Nó là điều kiện đạo đức để ClinicAI nhận được quyền hoạt động trong healthcare.»

### Ràng buộc đưa vào thiết kế

- Work Item Protocol §17 lặp lại: «Không dùng số Work Completed đơn lẻ để chấm hiệu suất cá nhân.» → [[tk-metrics]] chỉ định nghĩa metric **theo node/phòng/ca**, không theo người; metric theo người chỉ có trong *workload view* (tải hiện tại), không có trong báo cáo.
- Experience Spec §11: không hiển thị «bảng xếp hạng nhân viên theo số complaint risk» → [[tk-experience-state]] không có cột "ai gây ra".
- Event Catalog §12: «Các event overload là Derived Event; không dùng để chấm điểm cá nhân.»
- Đang có sẵn trong code: `_STATIONS_SQL` tách `serving` và `waiting` («gộp hai số này lại thì Trưởng ca không biết phòng đang kẹt hay đang rảnh») — đúng tinh thần tìm bottleneck chứ không tìm người.
""",
 "links": ["north-star", "tk-metrics", "tk-experience-state", "product-surface", "dispatch"],
},
{
 "id": "metrics-thesis", "layer": L, "order": 220,
 "title": "Bốn nhóm chỉ số — visibility · coordination · humane · business",
 "tag": "Thesis v1 §9 · Care Model §25",
 "summary": "Danh sách metric chính thức; hôm nay code tính được 0 trong 5 metric coordination.",
 "body": """
Nguyên văn (*Thesis v1 §9*):

**9.1 Operational visibility** — Observable Encounter Rate · Unknown State Duration · Event Coverage · State Freshness.

**9.2 Coordination quality** — Unowned Work Time · Acknowledgement Time · Handoff Failure Rate · Escalation Resolution Time · Coordination Debt («tổng số work item cần phối hợp nhưng đang thiếu owner, context hoặc next action»).

**9.3 Humane operations** — Unexplained Waiting Time · Patient Forgotten Risk · Communication Debt · Staff Overload Minutes · Prevented Complaints / Early Interventions.

**9.4 Business outcomes** — thời gian hoàn tất encounter · throughput · no-show/conversion · utilization · chi phí/encounter · retention, follow-up completion · lỗi, rework, khiếu nại.

> «Business metrics là kết quả cần thiết, nhưng không được tối ưu tách rời khỏi patient safety, staff wellbeing và care quality.» — *v1 §9.4*

Care Model §25 nói các metric này «sinh ra tự nhiên từ event stream» và thêm nhóm **System quality**: ingestion latency · projection lag · duplicate rate · unmatched event rate · late/out-of-order rate · failed side-effect rate · replay success · % warning có provenance.

### Tính được gì từ dữ liệu hôm nay

| Metric | Tính được? | Từ đâu |
|---|---|---|
| Thời gian chờ ở bước hiện tại, tổng thời gian trong phòng khám | ✅ | `dispatch_service._OVERVIEW_SQL` (`wait_minutes`, `total_minutes`) |
| Thời gian khám (consultation duration) | ✅ | `v_consultation_duration`, `v_consultation_duration_stats` |
| No-show, huỷ theo lý do | ✅ | `appointment.status`, `ly_do_huy_ma` (5 mã) |
| Giây phản hồi khi Trưởng ca gọi bộ phận | ✅ | `thong_bao.da_xu_ly` trả `giay_phan_hoi` |
| Acknowledgement Time, Unowned Work Time | ❌ | không có trạng thái ack, không có owner bắt buộc |
| Unexplained Waiting Time | ❌ | không có communication coverage |
| Event Coverage, State Freshness | ❌ | Hai cột cùng `DEFAULT now()` và đường ghi truyền `now()`, nên `recorded_at = occurred_at` là tất yếu → **độ trễ thật chưa từng được đo**, không phải bằng 0 |

Thiết kế: [[tk-metrics]] định nghĩa từng metric bằng SQL trên [[tk-event-envelope-v2]] và ghi rõ metric nào chỉ có nghĩa sau phase nào.
""",
 "links": ["tk-metrics", "gap-metrics", "tk-event-envelope-v2", "humane-ops"],
},
{
 "id": "decision-checklist", "layer": L, "order": 230,
 "title": "Decision checklist cho mọi feature — 11 câu hỏi",
 "tag": "Thesis v1 Phụ lục A · §12 Guardrails",
 "summary": "Bộ câu hỏi chặn feature rời rạc; nên trở thành mẫu PR description.",
 "body": """
Guardrails (*v1 §12*): chỉ build khi trả lời "có" ít nhất một: «Nó làm reality observable hơn? · next action rõ hơn? · ownership tốt hơn? · giảm coordination debt? · bảo vệ bệnh nhân hoặc nhân viên tốt hơn? · đóng một feedback loop đang hở? · tạo dữ liệu đáng tin để hệ thống học?»

Trì hoãn nếu: «chỉ sao chép module phổ biến của HIS/CRM · tạo thêm nơi nhập liệu nhưng không làm state chính xác hơn · tạo thêm dashboard nhưng không dẫn tới quyết định hoặc action · dùng AI ở nơi rule đơn giản minh bạch hơn · tăng throughput bằng cách chuyển áp lực sang nhân viên · không có owner cho dữ liệu, policy và hậu quả của tự động hóa.»

Phụ lục A — 11 câu:
1. Reality nào feature này giúp hệ thống nhìn thấy?
2. Event nào tạo hoặc cập nhật reality đó?
3. State nào bị thay đổi?
4. Next action nào được tạo ra?
5. Ai sở hữu action?
6. SLA và escalation là gì?
7. Người dùng cần thấy ngữ cảnh nào để quyết định?
8. AI có thực sự cần thiết không? Nếu có, tại sao rule không đủ?
9. Rủi ro nếu AI sai là gì? Có hoàn tác và audit được không?
10. Patient, staff và business metric nào sẽ thay đổi?
11. Feedback loop được đóng ở đâu?

### Đề xuất dùng ngay, không cần code

`SO-LUAT.md` Phần 12 đã có luật «giao việc theo TÌNH HUỐNG, không theo tính năng» và mẫu 5 dòng cho prompt báo lỗi. Ghép hai thứ: **PR template** thêm 4 câu bắt buộc (2, 4, 5, 11) — event nào · việc nào · ai sở hữu · vòng đóng ở đâu. Không trả lời được là PR đang thêm màn hình, không thêm năng lực. Đây là chốt rẻ nhất trong toàn bộ thiết kế và có thể áp trong tuần này ([[phase-0-nen]]).
""",
 "links": ["phase-0-nen", "adr-so-luat", "ci-guards"],
},
{
 "id": "macro-v3", "layer": L, "order": 240,
 "title": "Thesis v3 — care capacity, 5 tài sản founder đầu tư, đội hiện tại",
 "tag": "Thesis v3 §2",
 "summary": "Bức tranh vĩ mô và câu tự nhận về team — quyết định 'productize gì, custom gì'.",
 "body": """
> «Hệ thống biết điều gì nên làm, nhưng không thể làm điều đó đúng lúc, đúng người, nhất quán và ở quy mô đủ lớn.» — *v3 §2.1, healthcare delivery gap*

> «Nguồn lực khan hiếm thật sự: coordinated human attention. […] ClinicAI không chỉ là labor-saving software. Nó có thể trở thành attention allocation system for care delivery.» — *v3 §2.2*

Năm tài sản founder đang đầu tư (*§2.10*): (1) Ontology · (2) Operational data (event history) · (3) Workflow intelligence · (4) Trust · (5) Distribution. «Nếu chỉ tạo màn hình và feature theo yêu cầu từng phòng khám, phần lớn công sức không tích lũy thành tài sản.» → «Đây là tiêu chuẩn để quyết định một việc "nên build custom" hay "nên productize".»

Pilot phải tạo tài sản đi lên được (*§2.6*): canonical event model · reusable state machine · specialty configuration · integration adapters · deployment playbook · operational benchmark · trust/governance/audit layer.

Team (*§2.12*): «Cấu hình hiện tại gồm founder, người điều phối và một dev còn là sinh viên» — đủ để khám phá reality, xây ontology, prototype, pilot, chứng minh product loop; «chưa phải cấu hình để xây một healthcare infrastructure company».

Con đường (*§2.9*): 1 journey → 2 cơ sở → 1 khách ngoài pilot → 1 chuỗi khác → 1 chuyên khoa khác → 1 thị trường tương tự → partner ecosystem. «Đơn vị mở rộng phải là: thêm encounter được điều phối trên cùng một operational model với chi phí cận biên giảm dần.»

### Nghĩa cho thiết kế này

Ba thứ trong 5 tài sản mà code đã chạm: **ontology** (kernel + luật là dữ liệu — ADR-0011, `docs/kien-truc-nhieu-phong-kham.md` 4 tầng cấu hình), **operational data** (`event_log` — nhưng đang nhiễu), **trust** (RLS tenant, audit append-only, ký bệnh án). Thiết kế đích không thêm tài sản mới; nó **làm hai tài sản đầu có giá** bằng cách cho event_log nghĩa và cho work item vòng đời. Với đội 1 dev + AI, mỗi phase trong [[lo-trinh-tong]] cố ý nhỏ hơn 2 tuần và không đòi hạ tầng mới (Luật 7.1).
""",
 "links": ["lo-trinh-tong", "adr-so-luat", "multi-tenant-rls", "policy-as-data-hien-co"],
},
{
 "id": "pilot-scope", "layer": L, "order": 250,
 "title": "Partner Pilot Proposal — 8–10 tuần, in/out scope, 7 tín hiệu tối thiểu, 4 tầng gate",
 "tag": "Pilot Proposal v1",
 "summary": "Bản đề xuất pilot là bản 'định nghĩa xong' cụ thể nhất cho toàn bộ thiết kế: journey, node, exception, tín hiệu, cổng đánh giá.",
 "body": """
**Journey tham chiếu** (*§4.2*): «Có lịch → bệnh nhân đến → tiếp nhận → chờ bác sĩ → khám → phát sinh siêu âm/xét nghiệm → bác sĩ xem kết quả → tư vấn → thanh toán → follow-up.» Khớp gần hết xương sống kernel `LUOTKHAM-01→02→03→05→13→14→15` + `DICHVU-*` + `THEODOI-*`.

**Exception trong phạm vi** (*§4.4*): đến muộn · chờ vượt ngưỡng · chưa có communication coverage · kết quả sẵn sàng chưa review · Work Item chưa acknowledge · node/nhân sự quá tải · rời cơ sở khi còn việc mở · hệ thống nguồn mất kết nối.

**Ngoài phạm vi** (*§5*): thay HIS/EHR · bệnh án điện tử hoàn chỉnh · AI tự chẩn đoán · automation clinical decision · toàn cơ sở cùng lúc · **chấm KPI cá nhân bằng số task** · tích hợp mọi legacy · **camera/IoT diện rộng** · mobile app hoàn chỉnh · revenue cycle · cam kết business trước baseline.

**7 tín hiệu tối thiểu** (*§7*) — mỗi cái có nguồn ưu tiên và fallback:

| Tín hiệu | Nguồn ưu tiên | Fallback | Code hôm nay |
|---|---|---|---|
| Lịch được xác nhận | Appointment/CRM API | CSKH xác nhận trên ClinicAI | ✅ `tuong_tac_cskh.XAC_NHAN_LICH` |
| Bệnh nhân đã đến | Check-in/POS/HIS | Lễ tân một chạm | ✅ `check_in_appointment` RPC, mốc `CHECK_IN` |
| Vào/rời hàng đợi | Workflow integration | Nhân viên chuyển node | ✅ `move_visit_to_station` |
| Dịch vụ bắt đầu/kết thúc | HIS/LIS/device | Vai trò cung cấp dịch vụ xác nhận | 🟡 `work_item start/complete` (chưa ai bấm) |
| Kết quả sẵn sàng | LIS/HIS callback | Người được phân quyền ghi nhận | 🟡 `lab_result.result_received_at` nhập tay |
| Work đã nhận/hoàn tất | ClinicAI | «Không dùng kênh ngoài nếu cần đo» | ❌ không có *nhận* |
| Bệnh nhân được thông tin | ClinicAI/messaging callback | Structured attestation | 🟡 `TRA_KQ` là attestation nhưng chưa gắn subject/valid_until |
| Bệnh nhân rời cơ sở | Checkout/presence | Lễ tân/trưởng ca xác nhận | ✅ `dispatch.checkout`, mốc `CHECK_OUT` |

> «Không cần tín hiệu hoàn hảo từ ngày đầu. Cần biết rõ tín hiệu nào tự động, tín hiệu nào thủ công và độ tin cậy của chúng.» — *§7*

**Bốn tầng gate** (*§13*): Data & observability (≥90% encounter dựng lại được journey; ≥95% event có timestamp/source hợp lệ; integration failure hiển thị; projection lag trong ngưỡng) → Adoption & coordination (≥80% Work Item ack trong SLA; ≥90% có owner; ≥85% completion có evidence; không tăng thao tác) → Outcome (giảm ≥20% unexplained waiting; ≥30% open commitments không owner; ≥20% result-ready-to-review; ≥25% manual status-check) → Guardrails (0 safety incident; false alert trong ngưỡng; 0 privacy incident).

> «Nếu không qua gate này, chưa dùng outcome để kết luận.» — *§13.1*

Bốn tầng gate này là **tiêu chí nghiệm thu** của [[lo-trinh-tong]]; [[chung-minh-event-driven]] chuyển chúng thành test.
""",
 "links": ["wedge", "7-tieu-chi-event-source", "lo-trinh-tong", "chung-minh-event-driven", "patient-journey-4-chang", "tk-sensing"],
},
{
 "id": "patient-journey-4-chang", "layer": L, "order": 260,
 "title": "Patient Journey — 4 chặng, 3 lớp, 7 nhánh phát sinh",
 "tag": "Patient Journey v1",
 "summary": "Bản dành cho đối tác: hành trình là trải nghiệm liên tục, không phải sơ đồ phòng; 3 lớp expected/actual/next.",
 "body": """
> «Bệnh nhân không phân biệt đâu là việc của lễ tân, điều dưỡng, bác sĩ, kỹ thuật viên, thu ngân hay CSKH. Họ chỉ cảm nhận: phòng khám có biết tôi là ai và tôi đến để làm gì không? tôi đang phải đi đâu? tại sao tôi phải chờ? ai đang chịu trách nhiệm cho bước tiếp theo? …» — *Journey §1*

Ba điều một journey tốt tạo ra (*§1*): **Liên tục · Có người chịu trách nhiệm · Có thông tin**. «Một hành trình tốt không nhất thiết không có chờ đợi. Nhưng nó không để bệnh nhân chờ trong vô định và không để công việc tồn tại mà không có người sở hữu.»

Ba lớp (*§2*):

| Lớp | Ý nghĩa | Trong code |
|---|---|---|
| Hành trình dự kiến | Con đường thông thường cho loại dịch vụ đã đặt | `node_dependency` + `route_template` (3 tuyến) |
| Hành trình thực tế | Những gì đang thật sự xảy ra | `work_item` + `visit.current_*` + `event_log dispatch.*` |
| Việc cần xảy ra tiếp theo | Hành động phù hợp với tình huống hiện tại | `dispatch_service.next_step_of()` — chỉ khi có `visit_route` (0 dòng) |

Bốn chặng (*§3*): Trước khi đến · Đến và được tiếp nhận · Khám, chờ và dùng dịch vụ · Kết thúc và sau khám. Mỗi chặng có "bệnh nhân cần / phòng khám cần biết / ClinicAI hỗ trợ / kết quả mong muốn". Chặng 4: «Patient Journey không kết thúc khi bệnh nhân thanh toán hoặc bước ra khỏi cửa.» → «Không có bệnh nhân "rơi khỏi hệ thống" chỉ vì họ đã rời cơ sở.»

Bảy nhánh phát sinh (*§5*) mà thiết kế phải xử lý: đến muộn · chờ lâu · node quá tải · phát sinh chỉ định · **rời cơ sở trước khi hoàn tất** · kết quả bất thường · **hệ thống nguồn mất kết nối** («Không được khiến người dùng hiểu nhầm rằng "không có kết quả" khi thực tế là hệ thống không nhận được dữ liệu» — §5.7).

Bảy nguyên tắc (*§10*), câu 10.3 đáng in ra dán tường: «Mười lăm phút không biết chuyện gì có thể tệ hơn ba mươi phút được giải thích rõ.»

### Cách làm discovery với đối tác (*§11*)

Năm nhóm câu hỏi cho từng loại dịch vụ: hành trình dự kiến · tín hiệu quan sát («Tín hiệu đang ở HIS, LIS, một phần mềm khác hay chỉ trong đầu người?») · trách nhiệm · trải nghiệm · kết quả. Đây là **format workshop** để lấp `visit_gate_rule` (0 dòng) và sửa `route_template` («Không có tuyến nào cho người chỉ khám rồi về» — `docs/kien-truc-nhieu-phong-kham.md` §2c).
""",
 "links": ["journey-process-manager", "dispatch", "gap-process-manager", "pilot-scope", "experience-state"],
},
]
