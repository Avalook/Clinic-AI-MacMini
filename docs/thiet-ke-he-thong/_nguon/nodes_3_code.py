# -*- coding: utf-8 -*-
"""Lớp 3 — CODE HIỆN TRẠNG: đo trên prod 04–05/09/2026 và đọc code tại
worktree (main sau #163). Mọi con số là đo, không ước."""

L = 3

NODES = [
{
 "id": "stack", "layer": L, "order": 600, "status": "co",
 "title": "Stack đang chạy — Caddy → Next.js → FastAPI → Postgres 17, một VPS, một người vận hành",
 "tag": "CLAUDE.md · SO-LUAT Phần 1 · docker ps 04/09",
 "summary": "Quy mô thật quyết định kiến trúc: ~1 lượt gọi/giây, 50–80 BN/ngày, 4 vCPU/8 GB, Postgres cùng máy.",
 "body": """
Đo `docker ps` trên `clinic-vps` 04/09/2026 — 23 container, 2 môi trường:

```
prod    (:80)   clinicai_prod-{api, dashboard, caddy, notification-relay, uptime-kuma, dozzle}
                clinicai_{db, auth, rest, realtime, supabase_gateway, auth_guard}
staging (:8080) cùng bộ, tiền tố clinicai_staging-* / clinicai_stg_*
```

| | |
|---|---|
| Máy | VPS Vietnix, 4 vCPU AMD EPYC, 8 GB, 48 GB đĩa (dùng 26%) |
| Tải đo được | ~1 lượt gọi/giây (SO-LUAT Phần 1) |
| Database | Postgres 17 tự dựng, **cùng máy** với backend — «một truy vấn nóng dưới 1 ms», «một lượt đi hỏi tốn ~4 ms» (Phần 5) |
| Đội | 1 dev + AI |
| Backend | FastAPI, 212 file Python; `services/` 69 file, 23.049 dòng — phẳng, không module (ADR-0001 chưa thi hành) |
| Frontend | Next.js, 326 file TS/TSX, 55 route màn hình, 62 route BFF |
| DB | 79 bảng public, 119 migration, 9 view, 24 SQL test |
| Realtime | LISTEN/NOTIFY → SSE (không Supabase Realtime từ 06/08) |
| Async | 1 tiến trình `worker --relay` (Telegram) + `--pos-relay` (profile) |
| AI | Anthropic API (Haiku/Sonnet), LangGraph, checkpointer schema `langgraph` |
| Auth | GoTrue tự dựng + PostgREST (chỉ đọc) + JWT → `staff.auth_user_id` |

Ba luật nền chi phối thiết kế đích (SO-LUAT):

> «**Luật 7.1** — Postgres là hạ tầng có trạng thái duy nhất phía ứng dụng. Idempotency, hàng chờ gửi tin, giữ chỗ, giới hạn truy cập, "cache" = index + view.»

> «**Luật 7.2** — Trước khi đề xuất bất kỳ hạ tầng nào: đưa ra phép đo chứng minh thứ đang có không đủ.»

> «**Luật 8.1** — Ghi vết đi cùng transaction với việc nó mô tả.» (và Phần 7: đẩy nhật ký qua hàng chờ «Sai với y tế»)

Đây chính là lý do thiết kế đích không có Kafka/Redis/broker — và thesis cũng không đòi ([[kien-truc-toi-thieu]] §23).
""",
 "links": ["kien-truc-toi-thieu", "adr-so-luat", "realtime-sse", "notification-relay", "multi-tenant-rls", "ci-guards"],
},
{
 "id": "event-log-table", "layer": L, "order": 610, "status": "mot-phan",
 "title": "event_log — 14 cột, 17 loại, 449 dòng, 29 chỗ ghi",
 "tag": "supabase/migrations · đo prod 05/09/2026",
 "summary": "Sổ sự kiện append-only có thật, nhưng 62% là nhiễu slot_hold, 0% correlation, actor chìm trong JSON, không cửa ghi duy nhất.",
 "body": """
### Lược đồ (prod)

`event_id uuid · event_type text · event_version int · aggregate_type text · aggregate_id uuid · payload jsonb · metadata jsonb · correlation_id uuid · causation_id uuid · source text · occurred_at timestamptz · recorded_at timestamptz · event_published bool · clinic_id uuid`

Trigger: `trg_event_log_no_update`, `trg_event_log_no_delete` (append-only thật), `trg_notify_event_log` **chỉ AFTER INSERT** («Nghe cả UPDATE là relay tự đánh thức mình sau mỗi lần gửi» — `20260815000003`). RLS: MANAGEMENT trong tenant.

### Đo trên prod 05/09/2026

| event_type | số | từ → đến |
|---|---|---|
| `slot_hold.created` / `.released` | 175 / 106 | 17/08 → 01/09 |
| `patient.created` | 67 | 19/08 → 01/09 |
| `appointment.created` | 66 | |
| `cskh.tuong_tac` / `_hoan_tac` | 16 / 6 | |
| `roster.shift_added_cho_xep`, `roster.week_applied` | 2 / 2 | |
| `appointment.checked_in`, `.completed`, `.rescheduled` | 1 / 1 / 1 | |
| `dispatch.checkin`, `.checkout` | 1 / 1 | |
| `thong_bao.hen_goi_lai`, `.tuan_lich_truc` | 1 / 1 | |
| `patient.phone_added`, `.phone_removed` | 1 / 1 | |

- **281/449 = 62,6%** là `slot_hold` — giữ chỗ khung giờ 10 phút trên giao diện: telemetry của thao tác đặt lịch, không phải mốc chăm sóc.
- `correlation_id` khác NULL: **0**. `causation_id` khác NULL: **0**. `event_version` distinct: **1**.
- `recorded_at − occurred_at`: max **0 giây** trong ảnh chụp cũ. Đây **không** phải bằng chứng "chưa từng có ghi bù/ghi trễ ngoài đời": cả hai cột đều `DEFAULT now()` (`baseline_schema.sql:539-540`) và đường ghi truyền thẳng `now()` (`tuong_tac_cskh_service.py:249-256`), nên chúng bằng nhau **do cấu tạo**. Điều đọc được chỉ là: chưa đường ghi nào truyền `occurred_at` thật của sự việc. Độ trễ thực tế (khách đến 10:17, nhân viên bấm 10:40) hiện **không đo được**.
- `metadata` có `clinic_staff_id`: 424/449; `actor_auth_user_id`: 421; 24 dòng để `by_staff_id` trong **payload** (một số service ghi actor sai chỗ).
- `event_published = TRUE`: 449/449 — **cờ này KHÔNG chứng minh relay đã chạy hay tin đã tới nơi.** Có ít nhất hai cơ chế đặt được cờ này, và số đo không nói cơ chế nào đã đặt dòng nào: `scripts/danh-dau-event-cu-truoc-khi-bat-telegram.sql` UPDATE hàng loạt mọi dòng `FALSE` thành `TRUE` mà **không gửi gì** (bản thân tệp ghi ~1.164 dòng ở thời điểm 15/08 — nhiều hơn 449 dòng tôi đếm được, nên hai con số này thuộc hai phạm vi khác nhau và chưa đối chiếu được), và `notification_relay` đặt cờ ở **hai nhánh khác nhau**: nhánh không có template (`notification_relay.py:205-214`) đánh dấu rồi `continue` — **không gửi gì cả** — còn nhánh gửi được mới đánh dấu sau khi nhà cung cấp trả `ok` (`:238`). Bốn thứ phải tách: `processed` trong log (`:256`, cộng cả hai nhánh) · không có template (đặt cờ, không gửi) · nhà cung cấp trả ok · người nhận đã biết (không có gì trong hệ biểu diễn điều này). Nhánh thiếu cấu hình nhà cung cấp (`result["skipped"]`) thì **không** đặt cờ, để lại cho vòng sau. Muốn biết relay thật sự đưa tin thì phải đọc log `relay_poll_complete`/`relay_delivery_failed` hoặc lịch sử nhóm Telegram, không phải đọc cờ. *Chưa xác minh lại ở vòng này.*
- `source`: 12 chuỗi tự do (`api:booking` 281, `api:patient-intake` 67, `cskh.customers` 23, `config.roster` 3, `api` 2…).

### Ai ghi

`grep "INSERT INTO event_log"` trong `src/clinicai`: **29 chỗ** ở 21 file service (`booking_service.py:2019`, `patient_service.py:185/578/640`, `payment_service.py:387`, `dispatch_service.py:345`, `tuong_tac_cskh_service.py:249/380`, `config_service.py:265/614/694`, `lab_safety_service.py:331`…). Cộng 2 hàm SQL (`move_visit_to_station`, check-in). Có `services/audit.py:record_event()` — một cửa chung — nhưng chỉ vài nơi dùng.

Hai cách ghi metadata khác nhau cùng tồn tại: `{"actor_auth_user_id","clinic_staff_id","clinic_role"}` (đa số) và `{"trace_id"}` (`EventService.record_and_publish`, đường tool/orchestrator).

### Đọc ra được gì

1. Bảng **đúng hình** (append-only, có correlation/causation, có hai mốc giờ) nhưng **không ai điền phần hình ấy** — vì không có cửa ghi bắt buộc điền.
2. Nhiễu 62% **không** làm `event_log` vô dụng — nó đang được đọc thật: `AuditLogService.events()` (`audit_log_service.py:191`) đọc `v_audit_log`, UNION với `work_item_event`, giải nghĩa actor/subject/action rồi trả cho màn `/audit-log`. Ba việc phải tách bạch: (a) **lọc telemetry** — `v_audit_log` không lọc `slot_hold` (migration `20260805000001` còn ép bất biến "một dòng vào, một dòng ra"), nên dòng giữ chỗ **có thể lấn** cửa sổ `LIMIT 200` chung cho hai nguồn. Tỷ lệ 62% là của **toàn bộ lịch sử**, không suy ra được thành phần của 200 dòng mới nhất — hai thứ khác nhau, và mẫu hiện tại chưa đo *(phép đo còn thiếu: đếm `event_type` trong 200 dòng đầu của chính câu SQL ấy)*; (b) **độ đầy đủ/ngữ nghĩa domain event** — thiếu envelope và thiếu event vòng đời, đây mới là khoảng cách thật; (c) **replay** — chưa dựng lại được projection từ stream, vì (b) chứ không vì (a).
3. Độ phủ: **1 dòng `appointment.checked_in` trên 66 lịch đã tạo — con số này KHÔNG chứng minh mất event.** Mẫu số sai: 66 là số lịch *đã tạo*, không phải số khách *đã thật sự đến*; lịch tương lai, huỷ và no-show không bao giờ sinh `checked_in`. Và mốc quầy CSKH **không** phải một đường riêng: nó gọi `_doi_trang_thai_lich` (`tuong_tac_cskh_service.py:188-191`) → `BookingService.apply_action(action="checkin")` (`tuong_tac_cskh_service.py:437-446`) → chuyển trạng thái `CHECKED_IN` + `_log(event_type="appointment.checked_in")` + `_open_visit`, tất cả trong một transaction (`booking_service.py:273-274` định nghĩa chuyển tiếp, `booking_service.py:819-840` ghi event rồi mở lượt khám). Nút lễ tân (`booking.py:482`) hội tụ vào đúng hàm ấy. **Có một nhánh thứ hai cùng phát event này**, không đi qua `apply_action`: đặt lịch kênh `WALK_IN` trong ngày bật `auto_checkin` (`booking_service.py:464`) và tự ghi `appointment.checked_in` kèm `auto_walk_in: True` rồi mở lượt khám (`booking_service.py:623-637`). Mẫu đo 0 khách vãng lai **không** cho biết nhánh ấy đã từng chạy hay chưa: nó là ảnh chụp một thời điểm của bảng lịch hẹn, không phải lịch sử thực thi. Muốn biết thì phải đi đúng đường dữ liệu: `_log` ghi `origin` vào **cột `source`** *và* vào `metadata->>'origin'` (`booking_service.py:2019-2036`) — **không có cột tên `origin`**. Phép đo: đếm `event_log` có `source = 'api:appointment-walkin-autocheckin'` hoặc `metadata->>'origin'` bằng chuỗi ấy (hoặc `payload->>'auto_walk_in'`), lọc theo `clinic_id` và một khoảng thời gian rõ ràng. *Chưa chạy.* Nên phát biểu đúng phạm vi là *hai nhánh đã biết, cùng một tên event*, không phải "một cửa ghi duy nhất toàn hệ". Nếu lịch đã ở `CHECKED_IN`/`COMPLETED` thì hàm trả `False` và **cố ý** không ghi gì — đó là chống bấm trùng, không phải mất event. Cái đo được thật là: `visit` gần như không có event vòng đời.

Thiết kế: [[tk-event-envelope-v2]] (cột), [[tk-emit-function]] (cửa ghi), [[tk-event-catalog-table]] (đuổi slot_hold sang telemetry).
""",
 "links": ["event-envelope", "gap-envelope", "gap-crud-roi-log", "tk-event-envelope-v2", "tk-emit-function", "tk-event-catalog-table", "audit-labels", "notification-relay"],
},
{
 "id": "audit-labels", "layer": L, "order": 620, "status": "co",
 "title": "audit_labels.EVENT_LABELS — danh mục event de-facto (~80 tên) với nhãn tiếng Việt",
 "tag": "src/clinicai/services/audit_labels.py",
 "summary": "Đã có 'event catalog' dưới dạng dict Python + drift test; thiếu payload schema, category, privacy.",
 "body": """
`services/audit_labels.py` giữ `EVENT_LABELS: dict[str, str]` — tên event → nhãn tiếng Việt cho `/audit-log`. Trích:

```
"appointment.created": "Tạo lịch hẹn"        "appointment.checked_in": "Tiếp nhận (check-in)"
"appointment.no_show": "Khách không đến"      "slot_hold.created": "Giữ chỗ khi đang chọn"
"dispatch.moved": "Chuyển sang bước khác"     "dispatch.alert_called": "Trưởng ca gọi bộ phận"
"visit.closed_incomplete": "Đóng lượt khi chưa khám xong"
"clinical.signed": "Ký bệnh án"               "clinical.released": "Cho phép gửi kết quả"
"lab_result.ordered/entered/finalized"        "payment.recorded/voided"
"cskh.tuong_tac": "Ghi lần liên hệ với khách" "cskh.tuong_tac_hoan_tac": "Rút lại một lần liên hệ đã ghi"
"pharmacy.dispensed/refused/line_closed/adjusted/discarded"
"work_item.create/start/complete/skip"        "staff.created/updated/deactivated"
"clinic_settings.booking_policy_updated"      "booking_override.slot_superseded"
```

Có bài kiểm chống lệch `test_audit_labels_drift.py`: event mới ghi vào `event_log` mà thiếu nhãn là CI đỏ (DANG-LAM §0.2: «drift-test audit_labels đòi nhãn Việt cho event mới»). `thong_bao_service.NGUON` ghi chú: hai mã đi vào event_log «như THAM SỐ» nên bộ quét không thấy — phải thêm tay.

### Vì sao đây là tài sản

Đây là **Catalog §1** làm bằng tay: «tên canonical của event; nghĩa nghiệp vụ» — ở mức tên + nhãn. Nó đã có ~80 tên, phủ 9 domain. So với Catalog v1 (~80 event), độ phủ **khái niệm** khá tốt — thiếu chủ yếu ở Work (ack/escalate/block), Time/Expectation, Experience, Reliability.

Thiếu so với Catalog §1: thời điểm được phép phát · nguồn/authority · stream · payload tối thiểu · «không được nhầm với» · phản ứng dự kiến · privacy/versioning. Và nó là dict Python → phòng khám thứ hai không thêm được, và nhãn không dùng được trong SQL view.

[[tk-event-catalog-table]] đưa dict này vào bảng `event_catalog` (seed từ chính `EVENT_LABELS`), giữ drift test hai chiều (dict ↔ bảng).
""",
 "links": ["event-catalog", "event-log-table", "tk-event-catalog-table", "5-loai-event"],
},
{
 "id": "workflow-kernel", "layer": L, "order": 630, "status": "mot-phan",
 "title": "Workflow kernel — node_definition (41) · node_dependency (18) · work_item · gate SQL · Command API",
 "tag": "20260730000005 · ADR-0011 · services/work_item_service.py",
 "summary": "Luồng khám là dữ liệu; gate FS/SS/FF/SF chạy trong SQL; nhưng prod mới có 7 work_item từ 1 lượt khám.",
 "body": """
### Bảy bảng (`20260730000005_workflow_kernel.sql`)

`node_definition` (code, name, flow_group, workspace, actor_roles[], priority P0–P2, is_group, config jsonb, current_version) · `node_definition_version` (snapshot đóng băng) · `node_dependency` (predecessor/successor, FS/SS/FF/SF, is_blocking, gate_group, gate_operator AND/OR/XOR, condition) · `work_item` · `work_item_dependency` · `work_item_event` (append-only: command ∈ create/start/complete/skip/cancel/reassign) · `follow_up_case`.

> «This is the part of ClinicAI that makes it a workflow product rather than another clinic CRUD app: what happens in the clinic is DATA (node_definition), not Python.» — *migration header*

Prod 05/09: **41 node** (37 seed + 4 `THUOC-01..04`), 9 flow_group; **18 cạnh** FS (`LUOTKHAM-01→02→03→05→13→14→15`, `DATLICH-01→…→04`, `THEODOI-01→…→04`, `NGUONLUC`, `KETQUA-XETNGHIEM→DUYET-KETQUA`). KHAM-* và DICHVU-* **cố ý không nối** («which service follows which exam is a clinical decision, not something to infer from a table»).

### Gate trong SQL — `work_item_gate_blockers(work_item_id, phase)`

`start` ← FS/SS · `complete` ← FF/SF. Predecessor "xong" = COMPLETED **hoặc SKIPPED**; CANCELLED không thoả. Nhóm AND/OR/XOR; XOR đóng khi cả hai nhánh đều xong — và hàm trả về *các nhánh đã xong* «vì chính chúng là vấn đề» (ADR-0011). Rỗng = mở.

### Command API — `POST /work-items/{id}/commands/{start|complete|skip|cancel}`

`work_item_service.issue()` trong **một transaction**: `SELECT … FOR UPDATE` + join `clinic_membership` (khác tenant → 404, không 403) → kiểm transition (`_TRANSITIONS`) → kiểm vai theo `node_definition.actor_roles` (rỗng = «nobody yet», fail-closed) → gate → `UPDATE … WHERE status = $current AND version = $expected` → INSERT `work_item_event`. Bắt buộc `Idempotency-Key`; khoá được trả lại khi 4xx (`tra_khoa_neu_bi_tu_choi`).

`GET /work-items?workspace=` — worklist theo `node_definition.workspace` («a clinic that adds a node to its reception desk gets it on the board without a deploy»), **không lọc theo ngày mặc định** («a queue that resets at midnight loses the patient who is still sitting there»). `GET /visits/{id}/work-items` — thứ tự theo độ sâu `node_dependency` (CTE đệ quy). `GET …/blockers` — «What is still in the way — so the UI can say why a button is disabled.»

### Đo prod

`work_item`: **7 dòng, 1 visit** — LUOTKHAM-01 COMPLETED, 02/03/05/13/14 **CANCELLED**, 15 COMPLETED. `work_item_event`: 7 dòng, toàn `create`. Không `start`/`complete` nào từng được bấm. `follow_up_case`: 0. `staff_task`: 0 (đã không dùng). Tức là kernel **chạy được nhưng chưa được dùng** — vì Dr4Women hôm nay mới dùng CSKH đặt lịch ([[gap-wedge-mismatch]]).

### Khoảng cách với Work Item Protocol

Xem [[gap-work-item]]. Ngắn gọn: có transition + gate + version + event, **không có** owner bắt buộc / acknowledge / SLA / escalation / completion criteria / origin event / hai trục ưu tiên.
""",
 "links": ["work-item-commitment", "gap-work-item", "tk-work-item-protocol", "instantiate-visit", "dispatch", "gap-wedge-mismatch", "ontology-9"],
},
{
 "id": "instantiate-visit", "layer": L, "order": 640, "status": "co",
 "title": "Check-in sinh việc — instantiate_visit_workflow đi ngược node_dependency, không danh sách cứng",
 "tag": "20260731000003_visit_workflow_instantiation.sql",
 "summary": "Phản xạ Level 4 đầu tiên đã có: PatientArrived → tạo encounter + work item; và lý do LUOTKHAM-01 sinh ra ở COMPLETED.",
 "body": """
> «node_definition has had 37 rows and work_item has had ZERO since W4. The kernel could transition items and evaluate gates, but nothing ever created one […]. This is the missing writer.» — *migration header*

Cơ chế: CTE đệ quy từ node có `config->>'spawn_on' = 'visit.checkin'` (đặt trên `LUOTKHAM-01` — **là dữ liệu**, «so a clinic can move its own starting node without a deploy») đi theo `node_dependency` → INSERT `work_item` cho cả xương sống 7 node, `ON CONFLICT (clinic_id, visit_id, node_code) WHERE status <> 'CANCELLED' DO NOTHING` (idempotent qua `uq_work_item_visit_node_live`) → INSERT `work_item_event 'create'` → INSERT `work_item_dependency` từ template.

Ba quyết định ghi trong file đáng giữ:

> «WHY THE WHOLE SPINE, not one node at a time. […] Creating each node lazily needs a second write that can fail after the first commits, and its failure mode is a visit with no open work and no error anywhere, which is the worst outcome available in a clinic.»

> «LUOTKHAM-01 is born COMPLETED when an actor is supplied, because pressing check-in IS performing "tiếp nhận người bệnh". Leaving it PENDING would hold a blocking FS gate shut in front of the nurse until somebody clicked to assert a fact the database already stores.»

> «KHAM-* and DICHVU-* are the OUTPUT of LUOTKHAM-05 — a clinical decision the seed leaves unlinked on purpose; stamping them at check-in would invent clinical intent nobody expressed.»

`cancel_visit_workflow()` — undo check-in: CANCELLED (không SKIPPED — «SKIPPED means "this step will not happen" and opens the downstream gates; an undone or cancelled arrival means the whole visit is off»), COMPLETED giữ nguyên («history is not rewritten because the front desk changed its mind»).

### Đối chiếu thesis

Đây là **Expected Journey** (Care Model §9) được vật chất hoá đúng cách: template (`node_dependency`) → instance (`work_item_dependency`) có đóng băng phiên bản (`node_version_id NOT NULL`). Và là phản xạ Level 4 số 1: «PatientArrived → tạo encounter và work item tiếp đón» (*v1 §10*).

Hai điều thesis đòi thêm mà ở đây chưa có: (a) mỗi work item sinh ra phải có `origin_event_id` (§13 Work Item: «Reason: event/policy nào tạo ra việc») — hiện `work_item_event.metadata` ghi `spawn_on` chứ không trỏ event; (b) sinh việc là *policy* (trigger = PatientArrived) — hiện là hàm được `booking_service._open_visit` gọi thẳng. [[tk-policy-engine]] chuyển nó thành policy đầu tiên trong bảng `policy`, giữ nguyên hàm SQL làm *action*.
""",
 "links": ["workflow-kernel", "journey-process-manager", "4-tang-truong-thanh", "tk-policy-engine", "7-tieu-chi-event-source"],
},
{
 "id": "dispatch", "layer": L, "order": 650, "status": "mot-phan",
 "title": "Điều phối Trưởng ca — phòng, tuyến, move_visit_to_station, ngưỡng, 4 loại cảnh báo",
 "tag": "20260804000001–003 · services/dispatch_service.py (633 dòng) · route_derivation.py",
 "summary": "Bảng ATC sơ khai đã có, đọc từ một nguồn (visit.current_*); nhưng visit_route 0 dòng và cảnh báo chỉ tồn tại lúc đọc.",
 "body": """
### Ba bảng cấu hình

- `clinic_room` (12 phòng Dr4Women: TIEPNHAN, SINHHIEU, KB01–04, SA1–3, XETNGHIEM, NHATHUOC, THUNGAN; `capacity` = «Số người phục vụ ĐỒNG THỜI, không phải sức chứa hàng chờ»; `floor`; `show_on_tv`) + `clinic_room_node` (một phòng phục vụ nhiều bước — vá cho «KB01–04 đều gắn cứng vào KHAM-PHUKHOA»).
- `route_template` (3 tuyến A/B/C = hoán vị siêu âm/lấy máu/đọc KQ + thuốc + thanh toán) và `visit_route` (append-only, «Đổi tuyến giữa chừng thì PHẢI có lý do» — CHECK `visit_route_exception_needs_reason`; unique một tuyến hiệu lực/lượt).
- `dispatch_threshold` (theo phòng hoặc mặc định phòng khám: `wait_minutes` 20, `max_waiting` 8).

### Đường ghi duy nhất — `move_visit_to_station()` SQL

> «TÌNH TRẠNG TRƯỚC MIGRATION NÀY (đo trên prod 04/08): `work_item` có 0 dòng, và `visit.current_node_code` NULL ở cả 24 lượt khám. […] Nghĩa là hôm nay hệ thống không biết bệnh nhân đang đứng ở đâu.» — *20260804000003*

Bốn việc trong một giao dịch, khoá dòng `visit FOR UPDATE`: (1) đóng **mọi** bước đang mở (`COMPLETED`) · (2) mở bước mới gắn phòng · (3) cập nhật con trỏ `visit.current_node_code/current_room_id/current_node_since` · (4) INSERT `event_log 'dispatch.moved'` payload `{from_node, to_node, from_room, to_room, reason, work_item_id}`. `v_dispatch_history` đọc lại từ `event_log` («Không tạo bảng log thứ hai»). Trước khi move, `gate_rule_service.enforce()` chạy **trong cùng transaction** ([[gate-rule]]).

### Đọc — ba truy vấn, một nguồn

`_OVERVIEW_SQL`: mỗi lượt khám sống một dòng — node/phòng/tầng hiện tại, `wait_minutes` (tại bước) ≠ `total_minutes` (trong phòng khám) («Trộn chúng làm một sẽ khiến người vừa được chuyển phòng trông như vừa mới đến»), `done_steps` từ timeline, `route_steps`, `next_step_of()`. `_STATIONS_SQL`: tải mỗi phòng — `serving` (IN_PROGRESS) ≠ `waiting` (PENDING), max/avg wait, ngưỡng, `state` ok/warning/critical («Vượt CẢ HAI ngưỡng mới là critical»). `build_alerts()` hàm thuần: `room_overloaded` · `wait_too_long` (critical khi > 2× ngưỡng) · `missing_next_step` · `no_route`.

`route_derivation.derive_route()`: suy tuyến từ chỉ định còn mở + đuôi chung của mọi tuyến mẫu — vì «trên prod hôm nay 0/25 lượt khám có tuyến».

### Đối chiếu thesis

Đây là *Encounter Board* + *Resource Load* projection (Care Model §8.1) và một nửa ATC (§19.1). Đúng ở: một nguồn sự thật, con trỏ do trigger/hàm nuôi, cảnh báo tính lúc đọc thay vì bảng cảnh báo («nó sẽ cũ đúng vào lúc Trưởng ca cần tin nó nhất»). Thiếu: cảnh báo không phải event (không owner/ack/thời điểm phát hiện), không commitment/SLA trên card, không freshness. Đo: `visit_route` **0**, `visit_gate_rule` **0**, `dispatch_threshold` 1 (mặc định). Xem [[gap-atc]], [[tk-atc-ui]].
""",
 "links": ["gate-rule", "workflow-kernel", "product-surface", "gap-atc", "tk-atc-ui", "state-la-projection", "journey-process-manager", "gap-timer"],
},
{
 "id": "gate-rule", "layer": L, "order": 660, "status": "co",
 "title": "visit_gate_rule — luật thứ tự bắt buộc 4 ô, ngoại lệ có lý do, hàm thuần kiểm được",
 "tag": "20260804000014_gate_rule.sql · services/gate_rule_service.py",
 "summary": "Mẫu chuẩn 'luật là dữ liệu có phạm vi tenant': áp cho ai · bắt buộc qua · chặn gì · ai bỏ qua được — 0 dòng trên prod.",
 "body": """
> «BA CÁCH LÀM, CHỈ MỘT CÁCH ĐÚNG. (1) `if (doctor == 'Thành')` trong code → phòng khám thứ hai phải sửa code. Không bán được. (2) Thêm cột `is_gatekeeper` vào `staff` → […] Mỗi khách một cột. (3) Khai thành LUẬT có phạm vi tenant → ba khách hàng, ba luật khác nhau, cùng một dòng code.» — *migration header*

Bốn ô: **ÁP CHO AI** (`patient_kind` NEW/RETURN, `service_type_id`, `location_id`; NULL = mọi) · **BẮT BUỘC QUA** (`required_node_code(s)`, `required_staff_id`) · **CHẶN CÁI GÌ** (`blocked_node_codes[]`, `only_when_other_staff`) · **AI BỎ QUA ĐƯỢC** (`override_roles`, mặc định TRUONG_CA/MANAGEMENT).

> «Ô thứ tư không phải phần phụ. Phòng khám thật luôn có ca ngoại lệ; hệ thống nào không cho ngoại lệ sẽ bị vượt mặt bằng giấy tay, và lúc đó nó mất luôn khả năng biết chuyện gì đã xảy ra. Nên ngoại lệ được PHÉP, nhưng bắt ghi lý do và sinh event.»

`visit_gate_override` ghi riêng «để hỏi "tháng này luật nào bị bỏ qua nhiều nhất" chỉ là một câu SELECT». Trigger `visit_gate_rule_nodes_exist` chặn mã node gõ sai («Gõ sai một mã ở đây thì luật lặng lẽ không chặn gì — đúng loại hỏng tệ nhất với một luật an toàn»).

`gate_rule_service.py`: `applies_to / satisfied / blocks / first_block / may_override` là **hàm thuần** («Đây là một chốt an toàn: nó nói "không" với một thao tác mà con người đang muốn làm, giữa ca trực, với bệnh nhân đang đứng đó. […] Cả hai đều phải kiểm được bằng bảng tình huống»). `satisfied()` kiểm **tập** node — «BS Thành phụ trách cả năm chuyên khoa, nên "đã gặp BS Thành" có năm hình dạng».

Cảnh báo dữ liệu ghi trong code: «hôm nay mới 1/7 work_item có assigned_to. Nên một luật đòi ĐÍCH DANH người sẽ coi là chưa qua bước — tức là chặn nhiều hơn thực tế.»

### Vì sao nút này quan trọng với thiết kế đích

Đây là **khuôn mẫu policy** đúng nhất trong repo: trigger (một nước đi) · điều kiện (facts của visit) · quyết định (chặn/cho) · hành động (từ chối hoặc ghi override) · audit. Thiếu duy nhất: **version/effective_from** và không phản ứng với *event* (chỉ với lệnh move). [[tk-policy-engine]] lấy đúng cấu trúc 4 ô + override này làm hình dạng cho bảng `policy`, và `docs/kien-truc-nhieu-phong-kham.md` §3 (4 tầng cấu hình) làm khung phân loại luật.
""",
 "links": ["dispatch", "policy-engine", "policy-as-data-hien-co", "tk-policy-engine", "10-principles"],
},
{
 "id": "appointment-visit-tuongtac", "layer": L, "order": 670, "status": "co",
 "title": "Lời hứa · Sự việc · Lần chạm — appointment ≠ visit ≠ tuong_tac_cskh, và máy trạng thái đặt lịch",
 "tag": "GIAI-THICH-CODE §0.4 · booking_service.py (2.037 dòng)",
 "summary": "Ba bảng, ba câu hỏi; 8 trạng thái lịch hẹn, 11 action, mỗi transition một event; visit 5 trạng thái với INCOMPLETE sinh từ sự cố thật.",
 "body": """
> «`appointment` là **lời hứa**, `visit` là **sự việc**, `tuong_tac_cskh` là **lần chạm**. Ba thứ ấy có thể lệch nhau, và chính chỗ lệch đó mới là thông tin vận hành đáng giá nhất.» — *GIAI-THICH-CODE §0.4*

Quan hệ: `appointment 0..1 ↔ 0..1 visit` («KHÔNG PHẢI 1-1»: walk-in có visit không appointment; no-show có appointment không visit); `appointment 1 ↔ N tuong_tac_cskh` («gọi 3 lần = 3 dòng»); `visit 1 ↔ N work_item`.

### Máy trạng thái lịch hẹn (`booking_service.py`)

Trạng thái: SCHEDULED → CSKH_CONFIRMED → CONFIRMED → CHECKED_IN → COMPLETED; rẽ NO_SHOW / CANCELLED / DOCTOR_DECLINED. **Lịch mới vào thẳng CONFIRMED** («Quyết định của Quang (2026-08-04): bỏ vòng gọi-xác-nhận […] Cuộc gọi ấy CHÍNH LÀ thứ sinh ra lịch hẹn này»). 11 action: confirm · decline · complete · checkin · undo_checkin · cskh_confirm · cancel · no_show · reassign · assign_doctor · reschedule — mỗi cái một `Transition(to_status, from_statuses, allowed_roles, event_type)`.

Lưới thật ở Postgres, không ở Python: trigger `enforce_slot_capacity` + `pg_advisory_xact_lock(doctor, bucket, kind)`; `uq_appointment_patient_slot_live`; RPC `check_in_appointment` cấp `queue_number` theo ngày VN. «The checks in this module run before the write purely to produce a sentence a receptionist can act on».

Lý do huỷ có cấu trúc (`LY_DO_HUY`, 6 mã): BAO_KHI_XAC_NHAN · BAO_KHI_NHAC_HEN · BAO_VAO_GIO_KHAM («Ba mã đầu là BA THỜI ĐIỂM […] mỗi thời điểm tốn của phòng khám một khoản khác nhau») · DAT_TRUNG · BAC_SI_DOI_LICH · KHAC. Đây là **Principle 4 (Exception is first-class)** làm đúng, và là Decision event có lý do (Care Model §3.3 loại Decision) — chỉ thiếu cái tên.

### `visit`

OPEN → IN_PROGRESS → FINALIZED → AMENDED, cộng **INCOMPLETE** («Khách đang khám thì có việc phải về. Trước 06/08 hệ thống không có chỗ nào ghi điều đó»; đo hôm ấy: 35 lượt OPEN/IN_PROGRESS, 18 từ những ngày trước). FINALIZED bất biến: trigger `trg_visit_finalized_block`, đính chính chỉ qua `amend_visit` RPC (ADR-0008, TT13). Cột projection: `current_node_code`, `current_room_id`, `current_node_since`, `previous_node_code`.

### Đối chiếu thesis

`appointment` đúng mô hình «State machine + domain events» của Care Model §7. `visit` là Encounter — thesis đòi «event-sourced hoặc event-centric ledger»; hiện là bảng trạng thái với event thưa (`visit.checkin` trong SQL, `visit.closed_incomplete`, `clinical.signed/amended`). `tuong_tac_cskh` là Communication stream đúng nghĩa ([[tuong-tac-cskh]]).
""",
 "links": ["event-vs-record", "ontology-9", "tuong-tac-cskh", "selective-event-sourcing", "idempotency-concurrency", "cskh-views"],
},
{
 "id": "tuong-tac-cskh", "layer": L, "order": 680, "status": "co",
 "title": "tuong_tac_cskh — sổ chỉ-thêm của mọi lần chạm khách, hoàn tác không xoá vết",
 "tag": "20260809000003 · 20260809000007 · 20260810000009 · services/tuong_tac_cskh_service.py (883 dòng)",
 "summary": "Communication stream đã có thật: loai/kenh/ket_qua với CHECK chéo, mốc quầy, huy_luc; gần PatientInformed nhất trong code.",
 "body": """
> «Nút "📞 Gọi nhắc hẹn" trên màn Quản lý khách hàng là một thẻ `<a href="tel:…">`: nó quay số rồi thôi. Gọi xong không ai biết đã gọi, gọi lần hai không ai biết là lần hai […]. Sổ này CHỈ THÊM. Không có hàm sửa, không có hàm xoá: một cuộc gọi đã xảy ra thì đã xảy ra, và bản ghi sai được sửa bằng cách ghi thêm một dòng nói rõ, không phải bằng cách viết lại quá khứ.» — *docstring*

Cột: `clinic_patient_id · appointment_id (SET NULL) · loai · kenh · ket_qua · khach_xac_nhan · noi_dung · nhan_vien_staff_id · xay_ra_luc · trang_thai_ma · huy_luc · huy_boi_staff_id`.

| Trường | Giá trị |
|---|---|
| `loai` | XAC_NHAN_LICH · NHAC_HEN · CHECK_XN · TRA_KQ · HOI_LY_DO_HUY · HOI_THAM · KHAC + mốc quầy **CHECK_IN · CHECK_OUT · THANH_TOAN · MUA_THUOC** |
| `kenh` | GOI · ZALO · SMS · TRUC_TIEP · KHONG_LIEN_HE |
| `ket_qua` | DA_LIEN_HE · CHUA_NGHE_MAY · KHONG_LIEN_LAC_DUOC · HEN_GOI_LAI · CAN_BAC_SI · TU_CHOI · BO_QUA · **GHI_NHAN** (chỉ mốc quầy) |

CHECK chéo ép ở DB và giải nghĩa ở Python: `(ket_qua='BO_QUA') = (kenh='KHONG_LIEN_HE')` («hai nửa của một việc»); mốc quầy ⇔ GHI_NHAN ⇔ TRUC_TIEP («Cho mốc mượn DA_LIEN_HE là bịa ra một cuộc gọi chưa từng có»); XAC_NHAN_LICH/NHAC_HEN/HOI_LY_DO_HUY/CHECK_IN/CHECK_OUT **bắt buộc `appointment_id`**; `TRA_KQ` chỉ với `DA_LIEN_HE`.

`nhan_vien_staff_id` **từ phiên đăng nhập, không nhận từ client**; bảng chỉ `GRANT SELECT` cho trình duyệt. CHECK_IN/CHECK_OUT «không chỉ là dòng sổ» — chạy `BookingService.apply_action` trước, ghi sổ sau («hành động lịch thất bại […] thì KHÔNG được để lại dòng sổ nói việc đã xảy ra»).

Hoàn tác (`20260810000009`): `huy_luc` + `huy_boi_staff_id` với CHECK cặp — «Dòng ở lại, chỉ thôi được tính». Vì sao không bút toán đảo: «mọi câu NOT EXISTS phải đếm cặp ghi/huỷ — mười nhánh, mỗi nhánh một câu con, chỉ cần một nhánh quên là một trạng thái sai âm thầm.» `huy_luc IS NULL` phải có ở 5 chỗ trong view.

Bài học `trang_thai_ma`: «`loai` không phải trạng thái — đó là bài học phải sửa bằng một cột mới» (bấm "Đã hỏi bác sĩ" thì mốc "Đã trả kết quả" cũng tích).

Ghi event: `cskh.tuong_tac` payload `{loai, kenh, ket_qua, by_staff_id}` — actor ở payload, không ở metadata (lệch với đa số).

### Đối chiếu thesis

Đây là **Communication Stream** (§6.5) và **structured attestation** (Work Item §8) tốt nhất repo. `TRA_KQ + DA_LIEN_HE` ≈ ResultCommunicated/PatientInformed; `XAC_NHAN_LICH + khach_xac_nhan` ≈ PatientAcknowledged; `CHUA_NGHE_MAY` ≈ CommunicationFailed; `HEN_GOI_LAI` ≈ CommunicationRetryScheduled. Thiếu cho coverage (Spec §8): `valid_until`, chủ đề rõ hơn `loai` (đang gộp "giải thích chờ" vào KHAC/HOI_THAM), và kết nối tới một *commitment*. [[tk-communication-delivery]] giữ nguyên bảng, thêm hai cột.
""",
 "links": ["appointment-visit-tuongtac", "cskh-views", "bat-dang-thuc", "reliability", "tk-communication-delivery", "experience-state", "5-loai-event"],
},
{
 "id": "cskh-views", "layer": L, "order": 690, "status": "co",
 "title": "v_viec_cskh · v_trang_thai_cskh · luat_cskh — trạng thái là hàm của dữ liệu, luật là dữ liệu",
 "tag": "20260809000005 · 20260809000007 · 20260810000004 · 20260810000009",
 "summary": "11 nhánh việc suy ra từ sự vắng mặt của một dòng sổ; đóng việc = ghi một dòng; đúng tinh thần projection — nhưng fold từ bảng trạng thái.",
 "body": """
`luat_cskh (clinic_id, loai_viec) → bat, so_ngay, cua_so_ngay, nhan` — 11 dòng trên prod: CHO_XAC_NHAN 7 ngày · NHAC_HEN_MAI 1 · GOI_LAI 0 · HOI_LY_DO_HUY 1 (cửa sổ 14) · CHO_KQ_XN 2 · CHO_BAC_SI 1 · KQ_CHUA_GUI 1 · HEN_GOI_LAI 0 · MOI_TAI_KHAM 0 · NHAC_DI_KHAM 0 · **DA_CHECKIN** 0 (ưu tiên 0). «"Gọi xác nhận trước 7 ngày" là con số của Dr4Women. […] Ghim vào SQL thì mỗi lần đổi là một lần deploy.»

`v_viec_cskh` = 11 nhánh `UNION ALL` (uu_tien 0–10), mỗi nhánh một câu hỏi và đọc ngưỡng từ `luat_cskh`:

| uu_tien | loai | Suy từ |
|---|---|---|
| 0 | DA_CHECKIN | `appointment.status = 'CHECKED_IN'` («Khách có mặt tại chỗ là sự thật gấp nhất») |
| 1 | CHO_BAC_SI | `lab_result` có giá trị, `requires_doctor_review`, chưa `reviewed_at` |
| 2 | KQ_CHUA_GUI | kết quả đã duyệt mà **chưa có** dòng `TRA_KQ` sau `created_at` |
| 3 | CHO_KQ_XN | `result_value IS NULL` |
| 4 | GOI_LAI | lần chạm gần nhất trả CHUA_NGHE_MAY/KHONG_LIEN_LAC_DUOC/HEN_GOI_LAI |
| 5 | HOI_LY_DO_HUY | CANCELLED trong cửa sổ 1–14 ngày, chưa ai hỏi |
| 6 | HEN_GOI_LAI | `hen_goi_lai.dong_luc IS NULL AND ngay_goi <= hôm nay` |
| 7/9 | NHAC_DI_KHAM / MOI_TAI_KHAM | `nhac_tai_kham.trang_thai='CHO_GOI'` theo `luot_goi` |
| 8 | NHAC_HEN_MAI | lịch ngày mai chưa có `NHAC_HEN` |
| 10 | CHO_XAC_NHAN | lịch trong N ngày chưa có `XAC_NHAN_LICH` — «Suy từ sự VẮNG MẶT của một cuộc gọi, KHÔNG từ appointment.status» |

`v_trang_thai_cskh`: `DISTINCT ON (clinic, patient) ORDER BY qua_han DESC, uu_tien, han` — «QUÁ HẠN TRƯỚC, rồi mới tới ưu tiên. Đảo hai vế này là việc trễ ba ngày nằm im sau một việc chưa tới hạn»; kèm `so_viec_mo`, `co_viec_qua_han`, `da_xac_nhan`; `security_invoker = true`.

Bẫy đã trả giá và sửa: `DISTINCT ON` theo khách gộp mọi lượt → «mốc "Đã check-in" sáng chữ "đang ở đây" trên một lượt khách chưa từng đến» (ca anh Cường) → tách `v_viec_cskh` theo `appointment_id`; ba nhánh gọi điện quên loại CHECKED_IN → «vẫn giục gọi một người vừa bước vào cửa».

### Đối chiếu thesis

Đây là **projection + policy-as-data** làm đúng nhất trong repo — và là bằng chứng team đã tự đi tới Care Model §8 trước khi đọc thesis. Điểm khác: (1) fold từ **bảng trạng thái**, không từ event; (2) đánh đổi nói thẳng trong migration: «view không giữ được "ai nhận việc này"» → không ownership/ack = vi phạm Principle 3; (3) "quá hạn" là thuộc tính lúc đọc, không phải event có thời điểm phát hiện ([[gap-timer]]). Thiết kế giữ nguyên hai view làm *Work Queue projection*, và **thêm** lớp commitment bên trên: mỗi dòng việc CSKH đủ điều kiện được policy vật chất hoá thành `work_item` có owner/ack/SLA ([[tk-work-item-protocol]]) — đúng câu «Khi thật sự cần nhận việc thì thêm một bảng mỏng» của chính migration.
""",
 "links": ["state-la-projection", "policy-engine", "tuong-tac-cskh", "nhac-tai-kham", "gap-timer", "gap-projection-rebuild", "tk-work-item-protocol", "policy-as-data-hien-co"],
},
{
 "id": "thong-bao", "layer": L, "order": 700, "status": "co",
 "title": "thong_bao — Trưởng ca gọi bộ phận: chống bấm hai lần ở DB, đọc ≠ đã xử lý, đo giây phản hồi",
 "tag": "services/thong_bao_service.py · 20260807000006",
 "summary": "Mảnh 'ownership + ack + đo thời gian' duy nhất đang chạy — nhưng là notification nội bộ, không nối với work item hay escalation.",
 "body": """
> «Màn cảnh báo của Trưởng ca đã nói được "phòng SA1 đang tắc, bốn người chờ, lâu nhất 38 phút". Nó KHÔNG nói được với ai. Không nút gọi, không endpoint, không bảng thông báo, không đường giao hàng.» — *docstring*

Ba tính chất bắt buộc (docstring): (1) «Gọi hai lần không thành hai thông báo» — unique index từng phần `uq_thong_bao_dang_mo (clinic, nguon, nguon_id, vai_nhan) WHERE da_xu_ly_luc IS NULL`, «không phải bằng nút disabled ở trình duyệt — trình duyệt thì mở hai tab là hỏng»; (2) «Có đường ĐÓNG» — `da_xu_ly()` trả `giay_phan_hoi`; (3) «Người gọi biết chuyện gì xảy ra» — bấm trùng trả `da_goi_tu_truoc: true` («KHÔNG phải lỗi, nhưng cũng KHÔNG phải "đã gửi"»).

Bốn nguồn (`NGUON`): `dispatch_alert` → `dispatch.alert_called` · `bac_si_da_xep` → `thong_bao.bac_si_da_xep` · `tuan_lich_truc` · `hen_goi_lai`. Mỗi nguồn = một event_type + một đường ghi. Nhận theo **vai** (`vai_nhan`) hoặc đích danh (`nguoi_nhan_staff_id`). `da_doc_luc` ≠ `da_xu_ly_luc`: «Nút "Đánh dấu đã đọc" phải tắt được chấm đỏ mà KHÔNG đóng việc — đóng việc hộ ở đây là làm mất một hàng đợi thật chỉ vì ai đó mở cái chuông ra xem.»

### Đối chiếu thesis

`thong_bao` là **Work Item mỏng** cho *role queue* (Protocol §5: «Bất kỳ người đủ vai trò có thể nhận — phải có cơ chế claim và queue owner»): có subject (`nguon_id`), owner-queue (`vai_nhan`), completion (`da_xu_ly`), audit, idempotency ở DB. Thiếu: acknowledge tách khỏi complete (đọc ≈ ack? — thesis bảo không: «Không tự động chuyển Active chỉ vì người dùng mở màn hình»), deadline/SLA, escalation, và không liên kết `work_item`. Và `dispatch.alert_called` là *Command* (Care Model §4) đội lốt event.

Thiết kế [[tk-work-item-protocol]]: `thong_bao` **không xoá**; nó trở thành một *assignment strategy* (Role queue) của work item — dòng `thong_bao` mang `work_item_id`, `da_xu_ly` = `complete` của work item đó. Giữ được màn chuông, thêm được SLA.
""",
 "links": ["work-item-commitment", "bat-dang-thuc", "tk-work-item-protocol", "dispatch", "metrics-thesis"],
},
{
 "id": "nhac-tai-kham", "layer": L, "order": 710, "status": "mot-phan",
 "title": "nhac_tai_kham + hen_goi_lai + follow_up_case — 'việc' sau khám, sinh lúc mở màn vì không có cron",
 "tag": "services/recall_job_service.py (338 dòng) · recall_service.py",
 "summary": "Episode/post-visit stream sơ khai: hai lượt gọi, người phụ trách, hạn; follow_up_case có bảng nhưng không ai ghi.",
 "body": """
> «`RecallService` bên cạnh trả về một PHÉP CHIẾU: mỗi lần CSKH mở trang, nó tính lại từ đầu xem ai đến hạn tái khám. Không có dòng nào trong database, nên: không ai mở trang thì không ai biết có người cần gọi; không giao được cho một người cụ thể; trưởng ca không đối soát được cuối ngày […]. File này biến nó thành VIỆC: `nhac_tai_kham`, mỗi dòng một cuộc gọi phải làm.» — *docstring*

Hai lượt là hai việc: lượt 1 «bác sĩ dặn quay lại ngày X, khách CHƯA đặt lịch — gọi trước 5–7 ngày để MỜI ĐẶT LỊCH»; lượt 2 «khách ĐÃ có lịch hẹn hôm nay — gọi buổi sáng để NHẮC ĐI KHÁM». Hàm SQL `sinh_viec_nhac_tai_kham(clinic, ngay)` idempotent; gọi từ `danh_sach(sinh_truoc=True)` — «đường chắc chắn nhất hôm nay là sinh ngay lúc CSKH mở màn […] cắm thêm cron vào ngày mai không phải đổi gì». Prod: **33 dòng**. Kết quả 4 giá trị (DA_LIEN_HE/CHUA_NGHE_MAY/CAN_BAC_SI/TU_CHOI), `nguoi_goi_staff_id`, `han_goi`, `qua_han` tính lúc đọc.

`hen_goi_lai`: việc CSKH tự hẹn («Chỗ đựng những việc hệ thống CHƯA suy được»), CHECK `(dong_luc IS NULL) = (dong_boi_staff_id IS NULL)` — «Đóng việc mà không biết ai đóng thì không truy lại được».

`follow_up_case` (kernel): «Non-blocking work that was still open when the visit closed […] such work has a named owner and a date, instead of being quietly dropped on the floor.» — **0 dòng, không có writer** (`checkout_service` không ghi).

### Đối chiếu thesis

Episode Stream (§6.3: follow-up expected · patient contacted · appointment booked) có một nửa. Điều thesis đòi mà thiếu: (a) việc sinh ra do **timer** (FollowupWindowOpened) chứ không do ai mở màn ([[gap-timer]]); (b) `PatientLeftFacility + open commitment → ContinuityRisk → follow-up work có owner` (Spec §7.3) — hiện checkout đóng lượt và cam kết mở *biến mất*, đúng thứ `follow_up_case` sinh ra để chống. [[tk-expectation-timer]] thay «sinh lúc mở màn» bằng đồng hồ; [[tk-experience-state]] policy ContinuityRisk là writer đầu tiên của `follow_up_case`.
""",
 "links": ["timer-expected-event", "gap-timer", "tk-expectation-timer", "tk-experience-state", "cskh-views", "stream-boundary"],
},
{
 "id": "realtime-sse", "layer": L, "order": 720, "status": "co",
 "title": "LISTEN/NOTIFY → ChangeBroker → SSE — 'event notification' làm đúng, và cố ý nghèo",
 "tag": "20260806000001 · core/change_broker.py · api/v1/routers/events.py · RealtimeRefresher.tsx",
 "summary": "Bỏ Supabase Realtime vì DB thuê không cấp REPLICATION; trigger bắn tên bảng + clinic_id; màn hình tự đọc lại; tab ẩn không giữ kết nối.",
 "body": """
> «Realtime đọc nhật ký WAL qua một replication slot, và tạo slot cần quyền REPLICATION. Database cho thuê không cấp quyền đó — đã đo trên Viettel IDC 06/08/2026 […]. `LISTEN`/`NOTIFY` thì là SQL thường: KHÔNG đòi quyền nào.» — *change_broker.py*

Đường đi: trigger `notify_row_change()` (AFTER INSERT/UPDATE/DELETE, 16 bảng + `event_log` chỉ INSERT) → `pg_notify('clinicai_changes', {t: bảng, c: clinic_id})` → `ChangeBroker` (một kết nối LISTEN riêng, «mượn nó từ bể là vĩnh viễn bớt một chỗ»; hàng đợi mỗi màn 8 tin, đầy thì bỏ — «tin sau cũng nói đúng điều ấy») → `GET /events/stream` SSE («SSE CHỨ KHÔNG PHẢI WEBSOCKET. Việc cần làm ở đây là một chiều») → `RealtimeRefresher` debounce 250ms → `router.refresh()`.

Tin cố ý nghèo — hai lý do trong migration: «NOTIFY có trần 8000 byte, một hàng bệnh án có thể vượt → HỎNG CẢ GIAO DỊCH GHI»; và «đẩy dữ liệu qua đường này là mở lối đọc nằm ngoài mọi lớp kiểm quyền của API».

`RealtimeRefresher.tsx`: «TAB KHÔNG AI NHÌN THÌ KHÔNG GIỮ KẾT NỐI» — trình duyệt chỉ cho 6 kết nối/origin trên HTTP/1.1, «tới tab thứ SÁU là hết sạch, trang không tải nổi (treo 300 giây) trong lúc CPU máy chủ 0.03%». Nhịp dự phòng 60s. `slot_hold` cố ý **không** vào `LIVE_TABLES` (tránh «trận mưa render»).

Relay Telegram nghe cùng kênh và chỉ thức khi `t == 'event_log' && c == clinic_id` (`nen_danh_thuc`).

### Đối chiếu thesis

Đúng cấp độ 1 «Event notification» của Care Model §2 — và làm rất sạch. Nó **không phải** và không cần là event bus: Luật 6.3 «Database bắn tin lúc ghi xong → backend đẩy về màn hình (SSE) → màn hình chỉ làm mới đúng phần bị ảnh hưởng. Hiện trạng: nửa đầu đã xong; nửa sau chưa — mỗi tin về là dựng lại cả trang.»

Với thiết kế đích, kênh này là **xương sống đánh thức** cho cả ba consumer mới (relay đã dùng; đồng hồ expectation và policy engine dùng cùng cách — [[tk-expectation-timer]], [[tk-policy-engine]]). Không hạ tầng mới.
""",
 "links": ["event-first-dao-nhan-qua", "notification-relay", "tk-expectation-timer", "tk-policy-engine", "failure-la-domain", "stack"],
},
{
 "id": "notification-relay", "layer": L, "order": 730, "status": "mot-phan",
 "title": "notification_relay — outbox poll 30s + LISTEN, advisory lock, làm giàu lúc gửi, 5 template Telegram",
 "tag": "services/notification_relay.py · worker.py · notification_templates.py",
 "summary": "Consumer duy nhất của event_log; đúng ở idempotency và data minimization; sai ở 'sent = done' và 'không template = xong'.",
 "body": """
Vòng lặp (`worker.py --relay`): bật chỉ khi `NOTIFICATION_RELAY_ENABLED=true` («MVP 15/08: mọi tin nhắn do người bấm gửi, không tự động. Muốn bật lại thì dọn event_log tồn đọng trước» — vì trước đó «208 dòng event_log chưa publish còn tồn»); `TELEGRAM_CLINIC_ID` bắt buộc («refusing a cross-tenant relay»); LISTEN `clinicai_changes` + poll 30s làm lưới; heartbeat file cho healthcheck; bot lệnh `/trangthai /homnay` cùng tiến trình. Prod: container `notification-relay` Up 13 ngày, 449/449 event đã publish.

`poll_and_deliver()`: SELECT 50 event `event_published = FALSE` theo `occurred_at` → mỗi event `pg_try_advisory_lock(hashtextextended(event_id))` (hai relay không gửi trùng) → recheck `still_unpublished` → `_lam_giau()` («`event_log.payload` cố ý chỉ mang ID […] Tra database NGAY LÚC GỬI thay vì lúc ghi: tin kể trạng thái mới nhất») → `render()` → 3 lần thử, backoff 0.5s/1s («BA LẦN THỬ LIÊN TIẾP KHÔNG NGHỈ LÀ MỘT LẦN THỬ») → `_mark_published`.

Template: `appointment.created` · `.cancelled` · `.rescheduled` · `.doctor_removed` · `roster.shift_added_cho_xep`. «KHÔNG BAO GIỜ đưa số điện thoại / CCCD / địa chỉ vào tin: Telegram là máy chủ bên thứ ba.» Người nhận là **nhóm vận hành**, không phải khách («Bản đầu soạn tin cho KHÁCH […] đổ vào nhóm nội bộ thì ai đọc cũng thấy sai vai»).

### Ba chỗ lệch thesis

1. **Sent = done** (§20.9), và còn nhẹ hơn thế: `_mark_published` chạy cả khi **không gửi gì** (không có template, `:205-214`) lẫn khi nhà cung cấp trả ok (`:238`). Không MessageDeliveryConfirmed, không ai đọc.
2. **Không template → đánh dấu xong**: «relay đánh dấu đã-xử-lý và đi tiếp (render trả None) — im lặng có chủ ý». Với 281 `slot_hold` thì đúng là nên bỏ; nhưng cơ chế này cũng nuốt mọi event tương lai không có mẫu — thesis §15.6 đòi quarantine.
3. **Một cờ, mọi consumer**: `event_published` là "đã gửi Telegram". Consumer thứ hai (policy engine) không dùng chung cờ này được — `pos_outbox` đã phải tách vì thế. Thiết kế [[tk-communication-delivery]]: `notification_delivery` per channel (đúng ADR-0002), relay đọc bảng đó; `event_log.event_published` **ngừng mang nghĩa**, thay bằng `consumer_cursor` per consumer.

Mẫu tốt giữ nguyên: advisory lock + recheck; làm giàu lúc gửi; không PII; heartbeat; cờ bật tường minh.
""",
 "links": ["reliability", "bat-dang-thuc", "anti-patterns", "gap-communication", "tk-communication-delivery", "tk-reliability-playbook", "pos-outbox", "event-log-table"],
},
{
 "id": "pos-outbox", "layer": L, "order": 740, "status": "co",
 "title": "pos_outbox — outbox riêng có attempts/backoff/DEAD, vì 'một cờ không phục vụ được hai consumer'",
 "tag": "20260730000007 · ADR-0010 · services/pos_relay.py",
 "summary": "Mẫu outbox đúng nhất trong repo, đang chạy với NullPosAdapter; dead-letter là kết cục trung thực.",
 "body": """
> «WHY A SEPARATE TABLE, rather than reusing event_log: `event_published` is a single boolean shared by every consumer. The notification relay already claims events by flipping it, so a second relay reading the same flag would steal notifications and have its own deliveries marked done by the notifier. One flag cannot serve two consumers.» — *migration header*

Cột: `kind (invoice/invoice_void/stock_movement) · subject_id · payload · status PENDING/SENT/DEAD · attempts · max_attempts 5 · next_attempt_at · last_error · external_ref · sent_at`; `UNIQUE (clinic_id, kind, subject_id)` («enqueueing twice for the same subject is a no-op rather than a double invoice»); index `WHERE status='PENDING'` cho câu duy nhất của relay.

Ghi **trong cùng transaction với payment** (ADR-0010: «payment commit thì push chắc chắn đã vào hàng đợi; payment rollback thì không có gì trong hàng đợi»). Relay: claim từng dòng bằng advisory lock, backoff 1′→5′→25′→125′, hết `max_attempts` → **DEAD** («Dead-letter là kết cục trung thực: tiền đã thu, POS chưa biết, phải có người nhìn. Im lặng hoặc retry vô hạn đều giấu chuyện đó đi»). `KiotVietAdapter` cố ý chưa hiện thực HTTP → `PosDeliveryError(retryable=False)` → DEAD ngay.

Ranh giới có test: `test_pos_port.py::TestBoundary` — `services/` không import `adapters/`; `payment_service` không biết chữ "kiotviet".

### Vì sao nút này ở đây

Đây là **§15.5 outbox/inbox + §15.6 dead-letter** làm đúng. Thiết kế [[tk-communication-delivery]] và [[tk-reliability-playbook]] không phát minh gì: chúng **nhân bản khuôn `pos_outbox`** cho notification (`notification_delivery`) và cho policy side-effects — cùng cột attempts/next_attempt_at/DEAD, cùng cách claim. Và câu «Generalising event_log to per-consumer delivery tracking is worth doing when a third consumer appears» — consumer thứ ba (policy engine) chính là lúc đó.
""",
 "links": ["reliability", "notification-relay", "tk-communication-delivery", "tk-reliability-playbook", "10-principles"],
},
{
 "id": "idempotency-concurrency", "layer": L, "order": 750, "status": "co",
 "title": "Bất biến ép ở Postgres — idempotency_key, advisory lock, CAS, version, RPC",
 "tag": "ADR-0003 · api/idempotency.py · 20260714000002 · 20260717000002",
 "summary": "Bậc thang UNIQUE/CHECK → CAS → trigger+lock → RPC; đây là phần thesis §15.1/15.3 đã đạt và thiết kế đích chỉ mở rộng.",
 "body": """
> «**Luật 6.2** — Mọi bất biến có kẽ hở tranh chấp phải ép ở Postgres, theo bậc thang: ràng buộc UNIQUE/CHECK → `UPDATE … WHERE status IN (…)` một câu → trigger + khoá tư vấn → hàm RPC khi cần nhiều câu lệnh nguyên khối. Không tự cài khoá trong Python.» — *SO-LUAT*

Đang chạy:

| Bất biến | Cơ chế | Ở đâu |
|---|---|---|
| Bấm hai lần ≠ hai bản ghi | `idempotency_key (key, endpoint, actor_id)` DB-backed, TTL, trả khoá khi 4xx | `api/idempotency.py`; 17 dòng prod |
| Ghế 2+1 mỗi bác sĩ mỗi khung | trigger `enforce_slot_capacity` + `pg_advisory_xact_lock(doctor, bucket, kind)` | `20260714000002` (per-clinic từ `20260803000001`) |
| Một khách một lịch sống mỗi mốc | `uq_appointment_patient_slot_live` | `20260805000007` |
| Số thứ tự ngày VN không trùng | RPC `check_in_appointment` SECURITY DEFINER + advisory lock theo ngày | `20260717000002` |
| Work item không bị ghi đè | `version` + `UPDATE … WHERE status=$cur AND version=$exp` → 409 | `work_item_service.issue()` |
| Một vị trí một lượt | `move_visit_to_station` `FOR UPDATE` | `20260804000003` |
| Một tuyến hiệu lực/lượt | `uq_visit_route_one_active` | `20260804000002` |
| Một thông báo mở/nguồn/vai | `uq_thong_bao_dang_mo` partial unique | `20260807000006` |
| Hai relay không gửi trùng | `pg_try_advisory_lock(hashtextextended(event_id))` | `notification_relay.py` |
| Bộ kiểm dưới tranh chấp | `kiem-duong-ghi.py`: 15 người đua 2 ghế → đúng 2 thắng, 0×500; trùng khách ×5 → 1 lịch | DANG-LAM §0 (staging) |

Ràng buộc kèm theo (ADR-0003): backend nối qua session mode; relay dùng session-level lock nên «KHÔNG được chuyển transaction-mode nếu chưa refactor relay».

### Nghĩa cho thiết kế

Thesis §15.1 «idempotency key = event_id + policy_id + action_type» và §13 Work Item «Cùng origin_event + policy_version + work_type + subject chỉ tạo một Work Item» → đúng bậc thang này: **UNIQUE index** trên `work_item (origin_event_id, policy_id, node_code, subject)` ([[tk-work-item-protocol]]), và `expectation (registered_by_event_id, expected_event_type)` ([[tk-expectation-timer]]). Không cần Redis lock, không cần dedup store — Postgres đủ, như ADR-0005.
""",
 "links": ["reliability", "adr-so-luat", "tk-work-item-protocol", "tk-expectation-timer", "workflow-kernel", "appointment-visit-tuongtac"],
},
{
 "id": "multi-tenant-rls", "layer": L, "order": 760, "status": "co",
 "title": "Multi-tenant thật — clinic_id trên 69 bảng, 45 policy, backend bỏ qua RLS nên CI đếm mọi câu lệnh",
 "tag": "ADR-0009 · 20260730000003/4 · scripts/tests/tenant-scope-audit.py",
 "summary": "Governance ở tầng DB đã đúng; bài học 'RLS không bảo vệ backend' sinh ra audit ceiling = 0.",
 "body": """
Bất biến CI đếm (GIAI-THICH-CODE §9.7): bảng có `clinic_id` = **69** · `NOT NULL` 0 ngoại lệ · FK tới `clinic` 0 ngoại lệ · `clinic_id` là cột dẫn đầu ít nhất một index · 7 bảng dùng chung không có `clinic_id` (`province, ward, staff, staff_capability, idempotency_key, schema_migrations, clinic`) · policy `%_select_own_clinic` = **45** · policy có `cmd <> 'SELECT'` = **0** · còn `USING (true)` = **0**.

Ba hàm danh tính `STABLE SECURITY DEFINER`: `current_staff_id()` → `current_clinic_ids()` → `current_clinic_roles(clinic)`. `default_clinic_id()` trả NULL ngay khi có tenant thứ hai — «gán nhầm sẽ báo lỗi chứ không âm thầm».

> «**RLS không bảo vệ được backend.** Tiến trình FastAPI nối DB bằng chủ sở hữu database, nên policy ở trên không áp cho nó: một câu lệnh đọc rộng đúng bằng mệnh đề WHERE của chính nó. Vì vậy mọi câu lệnh trong `src/clinicai` chạm bảng có tenant đều phải tự lọc `clinic_id`. Đã đưa từ 71 → 0; `tenant-scope-audit.py --check` chạy trong CI với ceiling = 0.» — *ADR-0009 W8*

Ba relay quét mọi tenant *có chủ đích* được liệt kê tường minh (`pos_relay`, `notification_relay`, `event_service`). `event_log` RLS: MANAGEMENT và trong tenant. `idempotency_key`, `clinic_secret`, `pos_outbox`, `mpi_merge_queue`, `staff_capability`: RLS bật, 0 policy = chỉ backend.

Bài học ghi trong ADR-0012 và GIAI-THICH-CODE: «RLS ENABLE mà không có policy nào = bảng rỗng, không phải bảng mở»; «View thiếu `security_invoker = true` là rò rỉ im lặng».

### Nghĩa cho thiết kế

Mọi bảng mới trong lớp 5 (`event_catalog`, `policy`, `expectation`, `experience_state`, `notification_delivery`, `event_quarantine`, `projection_checkpoint`) đi đúng khuôn: `clinic_id NOT NULL` + FK + index dẫn đầu + policy select own clinic (hoặc 0 policy nếu chỉ backend) + tự lọc trong mọi câu lệnh Python để audit ceiling giữ 0. [[tk-governance]] ghi rõ.
""",
 "links": ["governance-event", "tk-governance", "adr-so-luat", "ci-guards", "stack"],
},
{
 "id": "policy-as-data-hien-co", "layer": L, "order": 770, "status": "co",
 "title": "Luật là dữ liệu — kiểm kê 9 bảng luật và 4 tầng cấu hình",
 "tag": "docs/kien-truc-nhieu-phong-kham.md §3 · đo prod 05/09",
 "summary": "Tài sản lớn nhất so với thesis: Policy/SLA đã là bảng theo tenant; thiếu version, effective_from, owner, và 'luật phản ứng'.",
 "body": """
Bốn tầng cấu hình (`docs/kien-truc-nhieu-phong-kham.md` §3): **Tầng 0** hằng số sản phẩm (bệnh án khoá sau ký, một người không ở hai phòng, RLS) · **Tầng 1** danh mục của tenant (cơ sở, tầng, phòng, chuyên khoa, dịch vụ, giá, nhân sự, vai) · **Tầng 2** luật vận hành (quản lý chỉnh, không cần dev) · **Tầng 3** ngoại lệ có ghi lý do.

Kiểm kê tầng 2 trên prod:

| Bảng | Luật | Dòng | Thi hành |
|---|---|---|---|
| `luat_cskh` | 11 loại việc CSKH: số ngày, nhãn, bật/tắt | 11 | view (lúc đọc) |
| `doctor_booking_override` / `slot_booking_override` | sức chứa 3 tầng theo bác sĩ/khung, theo phút | 6 / 0 | trigger (lúc ghi) |
| `clinic.settings` | `hours`, `booking`, `ca_lam_viec` (3 ca), `display`, `feature_mode` | 1 | service (lúc ghi/đọc) |
| `luat_bac_si_bat_buoc` | dịch vụ X + khách mới → bác sĩ Y; 3 cách tính "mới"; `chan_han` | 2 | booking (lúc ghi) |
| `dispatch_threshold` | ngưỡng chờ/số người theo phòng | 1 | `build_alerts` (lúc đọc) |
| `visit_gate_rule` (+`_override`) | thứ tự bắt buộc 4 ô | 0 | `gate_enforce` (lúc ghi) |
| `route_template` | tuyến sau khám | 3 | `apply_route` (tay) |
| `node_definition` (+`_version`) / `node_dependency` | luồng khám, vai, gate | 41 / 18 | kernel |
| `clinic_room` / `clinic_room_node` / `vai_duoc_vao_tram` / `staff_node` | phòng ↔ node, vai ↔ trạm | 12 / 28 | dispatch |

Tầng 3 có ghi lý do: `visit_route.reason`, `visit_gate_override.reason`, `ly_do_huy_ma`, `ly_do_lam_lai` (`20260817000001`), `ly_do_vuot_khung_gio` (CD). TAM-NHIN luật 2: «Case ngoại lệ là thức ăn của lv5; ngoại lệ không ghi lại là bài học vứt đi.»

### Đối chiếu thesis

Care Model §10 đòi policy có **version, owner, test case, audit**. Chỉ `node_definition_version` có version. Không bảng nào có `effective_from`/`owner_role`. Đổi `luat_cskh` không sinh event (`PolicyVersionActivated` — Catalog §13). Test có nhưng là test *hàm* (gate_rule 100% thuần), không phải test *dòng luật*.

Và cả 9 bảng là luật **tĩnh** (điều kiện trên trạng thái) — không có luật loại «event X xảy ra → làm Y → đóng bằng Z». [[tk-policy-engine]] thêm đúng một bảng cho loại ấy và bốn cột version cho các bảng cũ; không gộp 9 bảng thành một (chúng có hình khác nhau vì câu hỏi khác nhau — `luat_bac_si_service` docstring: «Hai câu hỏi khác nhau, hai bảng khác nhau»).
""",
 "links": ["policy-engine", "gate-rule", "cskh-views", "tk-policy-engine", "ontology-9", "4-tang-truong-thanh"],
},
{
 "id": "ai-hien-co", "layer": L, "order": 780, "status": "mot-phan",
 "title": "AI đang có — lab triage với hard-block GROUP_C, brief, orchestrator LangGraph, tất cả tĩnh và có provenance",
 "tag": "graphs/lab_triage · orchestrator/ · ADR-0005 · design v5 §5.7",
 "summary": "AI đúng chỗ Interpretation (phân loại kết quả) với cổng an toàn; scheduling graph tắt vì chưa nối tool thật.",
 "body": """
Bốn graph (`src/clinicai/graphs/`): `lab_triage` (receive → fetch → classify → **persist** → advise | hard_block → create_review_tasks) · `pre_visit_brief` · `scheduling` · `task_manager` (trên `staff_task`, đã 0 dòng). `orchestrator/graph.py` định tuyến theo intent (scheduling/lab/communication/task/previsit/general) với stub khi thiếu pool/LLM. Checkpointer ở schema `langgraph` (ADR-0007: «disposable state»).

Cổng an toàn (`lab_triage/graph.py`): «The GROUP_C → hard_block routing is the safety gate: patient-facing responses are suppressed and an escalation note is set for BS review. […] enqueues exactly one URGENT LAB_REVIEW staff task with SLA=4h.» Không LLM → «safety-falls back to PENDING + requires_doctor_review=True and routes to hard_block». Classifier phải **persist trước khi phản hồi** («Classifier output must be durable before it can drive a response»).

Provenance trên `lab_result`: `triage_group`, `triage_reason`, `triage_classified_at`, `triage_model`, `requires_doctor_review`, `reviewed_by_staff_id`, `reviewed_at`, `is_finalized`. `clinical_release` + `clinical_sign_service`: bác sĩ ký mới cho phép gửi (`clinical.signed`, `clinical.released`).

Quyết định giữ (design v5 §5.7): «Kiến trúc là STATIC ROUTING, không phải agentic tool-use»; «GROUP_C chưa review thì KHÔNG một response nào tới BN»; D012 không chatbot tư vấn lâm sàng; D013 không risk-scoring. ADR-0005: LLM qua Anthropic API 2-tier, không local reasoning, chỉ voice STT on-prem (NĐ13).

Đo: `lab_result` prod **0 dòng** → lab triage chưa chạy thật ngoài test.

### Đối chiếu thesis

- Đúng vị trí: Interpretation (§5.1 «state không thể xác định chỉ bằng rule đơn giản») + Act có guardrail chặn.
- Provenance §20.10 ✅ (model + lý do + thời điểm). Thiếu `confidence` số và `expires_at`.
- Thesis xếp tóm tắt/brief, phát hiện nghẽn, ETA, đề xuất phân bổ lại là «vai trò AI ưu tiên» (§5.1) — chỉ brief có.
- Tổng-Quan §9 «Tầng 2 — Operations Copilot: đọc event/state projection → phát hiện nghẽn → GỢI Ý điều phối — shadow mode trước» chưa có, và **không thể có** trước khi có projection đáng tin (TAM-NHIN luật 1).

[[tk-ai-placement]] giữ nguyên tất cả và chỉ thêm: derived event có `evidence_level='inferred'` + `confidence` + `rule_or_model` khi AI phát hiện; allowlist work type cho system agent.
""",
 "links": ["3-muc-quyen-ai", "tk-ai-placement", "gap-ai", "10-principles", "governance-event"],
},
{
 "id": "man-hinh-theo-vai", "layer": L, "order": 790, "status": "co",
 "title": "55 màn theo 13 vai — NAV_ROLES, 5 màn Trưởng ca, /home gói một vòng, /display",
 "tag": "src/dashboard/app · lib/roles.ts · services/man_trang_chu_service.py",
 "summary": "Lớp Human Interfaces dày nhất sản phẩm; đọc roles.ts chứ đừng đọc bảng trong tài liệu.",
 "body": """
Vai (`api/identity.py ClinicRole`, 13): DOCTOR · ULTRASOUND_DOCTOR · NURSE_ULTRASOUND · RECEPTION · CSKH · MANAGEMENT · CASHIER · CASHIER_THUOC · CASHIER_DV · TKYK · TRUONG_CA · PHARMACIST · DISPLAY («Không phải người — cái TV treo tường; backend từ chối vai này ở mọi endpoint trừ bảng gọi số»).

Ranh giới nghiệp vụ (`roles.ts`, mirror ở `identity.py`): `canWriteClinical` = BS + ĐD + TKYK · chỉ bác sĩ **ký** · CSKH không tự phát hành kết quả · `canWriteIntake` = CSKH/Lễ tân/QL/Trưởng ca · `canCheckin` = Lễ tân/QL/CSKH («sản phẩm MVP này là cskh thao tác được hết mà»).

Màn hình theo nhóm (55 route):
- **CSKH** `/customers` (1.184 dòng server component, Lát 2 gói 10 vòng thành `GET /cskh/man-khach-hang`), `/cskh-tasks`, `/nhac-tai-kham`, `/lich-do-ve`
- **Lễ tân** `/home` (Lát 3: `GET /home/bang-dieu-khien` — «khối theo vai do backend quyết từ identity»), `/patients/new`, `/reception/queue`, `/reception/checkout`
- **Trưởng ca** `/truong-ca` · `/hang-doi` · `/canh-bao` · `/lich-su` · `/tv` — «bị siết từ 28/36 mục xuống còn 5 màn điều phối (Quang, 04/08)»
- **Bác sĩ** `/tasks`, `/doctor/board`, `/doctor/orders/[visitId]`, `/result-review`, `/sieu-am`, `/sono`
- **Điều dưỡng** `/lab-queue`, `/service-queue`
- **Thu ngân / Dược** `/cashier/*`, `/pharmacy/*`
- **Quản lý** `/settings/*` (booking-policy, clinic-config, tai-khoan), `/ops`, `/reports`, `/audit-log`, `/nhan-su`, `/work-sessions`
- **TV** `/display`; in `/print/*`

Nợ đo được: SO-LUAT Luật 4.1 «route còn chạm thẳng database hôm nay là 42» (ratchet CI, chỉ được giảm); ADR-0012 nói cutover đã xong 30/07 và allowlist service-role còn 2 — hai con số nói hai chuyện, GIAI-THICH-CODE ghi «Chưa rõ con số hiện tại — cần kiểm».

### Đối chiếu thesis

Thesis §19 đòi ATC/My Work/Team Queue/Patient panel/Timeline với các trường cụ thể ([[product-surface]]). Các màn trên **có khung đúng** (Trưởng ca = ATC, `/tasks` = My Work, `/display` = Patient panel, `/audit-log` = Timeline) — [[tk-atc-ui]] chỉ thêm trường, không thêm màn.
""",
 "links": ["product-surface", "tk-atc-ui", "6-lop-san-pham", "dispatch", "gap-atc"],
},
{
 "id": "adr-so-luat", "layer": L, "order": 800, "status": "co",
 "title": "13 ADR + Sổ luật — quyết định đã chốt, cái nào đã thi hành",
 "tag": "docs/adr/ · docs/SO-LUAT.md Phần 9",
 "summary": "Bảng trạng thái thi hành đo 13/08: modular monolith ❌, outbox/bỏ RabbitMQ ❌, còn lại ✅ — thiết kế đích không đè lên ADR nào.",
 "body": """
| ADR | Quyết định | Thi hành (SO-LUAT Phần 9, 13/08) |
|---|---|---|
| 0001 | Modular monolith + manifest 7 mục + import-linter | ❌ «không có thư mục `modules/`, không manifest, `services/` vẫn phẳng» |
| 0002 | Outbox polling là đường async duy nhất; xoá RabbitMQ; bảng `notification_delivery` | ❌ «`event_bus/` vẫn còn, `RabbitMQPublisher.publish()` vẫn `raise NotImplementedError`, `notification_delivery` chưa có migration» |
| 0003 | Bất biến concurrency ở Postgres | ✅ |
| 0004 | Auth 2 lớp fail-closed; RLS chỉ đọc | ✅ Accepted 30/07 |
| 0005 | Không hạ tầng stateful mới; LLM qua API | ✅ |
| 0006 | Ngân sách RAM; voice tách | ⚠️ phần Mac lỗi thời |
| 0007 | LangGraph checkpointer schema riêng | ✅ |
| 0008 | Đính chính bệnh án qua RPC + event_log | ✅ |
| 0009 | Multi-tenant từ đầu | ✅ |
| 0010 | KiotViet: port + adapter, outbox | ✅ (NullPosAdapter) |
| 0011 | Kernel workflow V2 ngay | ✅ dựng; «Chưa có routing tự động» (sau đó có ở `20260731000003`) |
| 0012 | Backend sở hữu hợp đồng | ⚠️ «42 route vẫn chạm thẳng database» |
| 0013 | Chạy Mac, sẵn sàng VPS | ✅ đã lên VPS |

Sổ luật, những luật thiết kế này phải tuân: **2.1** chỉ `main`; **3.1** không luật nghiệp vụ chỉ ở frontend; **4.1** ratchet 42 route; **4.4** một bảng một người ghi («Cách khai: mỗi tính năng một trang […] máy cũng đọc được» — chính là manifest ADR-0001); **5.1** một màn hình một lượt gọi; **6.2** bất biến ở Postgres; **7.1/7.2** không hạ tầng mới nếu không có phép đo; **8.1** ghi vết cùng transaction; **8.2** trong vết chỉ mã số; **11.2** code chạy phải có bản sao ngoài máy; **12.2** vá phải liệt kê mọi chỗ cùng mẫu, test phải đếm; **12.5** quy tắc chỉ đáng tin khi nằm trong CI.

### Thiết kế đích đối với ADR

- Thi hành nốt **0001** ([[tk-modular-monolith]]) và **0002** ([[tk-communication-delivery]]) — hai ADR còn nợ chính là hai mảnh thesis cần.
- Không ADR nào bị supersede. Sẽ cần **ADR-0014** (event envelope v2 + một cửa ghi), **ADR-0015** (Work Item Protocol), **ADR-0016** (expectation timer trong tiến trình relay) — [[lo-trinh-tong]] ghi thời điểm.
""",
 "links": ["stack", "kien-truc-toi-thieu", "tk-modular-monolith", "tk-communication-delivery", "lo-trinh-tong", "ci-guards", "macro-v3"],
},
{
 "id": "ci-guards", "layer": L, "order": 810, "status": "co",
 "title": "CI — 5 job, ratchet chỉ được hạ, 24 SQL test, 163 pytest, 63 test dashboard",
 "tag": ".github/workflows/ci.yml · SO-LUAT Luật 12.5",
 "summary": "'Luật không có người canh thì không phải luật' — đây là người canh; mọi bất biến mới của thiết kế đích phải có một dòng ở đây.",
 "body": """
Năm job:
- **backend**: ruff lint + `ruff format --check` (hay quên) · mypy `src/` · `tenant-scope-audit.py --check` (ceiling **0**) · pytest unit `--cov-fail-under=80` (hiện ~79,8%, cổng thực 79,5 vì làm tròn).
- **frontend**: tsc · eslint `--max-warnings=0` · `test:audit` · `test:ops` · **`test:boundary`** (service-role allowlist trần 2, chỉ được hạ; ratchet `[..px]` trần 102; route chạm DB trần 42) · `next build`.
- **infra-safety**: smoke test hạ tầng.
- **portability**: cấm `/Users/…` trong compose/env · compose resolve từ example · build 2 image `linux/amd64` · chạy thật `/health` + `/health/db`.
- **database**: Postgres 17 dùng một lần · «Migrations and seed must be plain SQL» (chặn `\\restrict`, `FROM stdin`) · áp toàn bộ migration · **áp lần hai** mọi migration từ `20260730` (idempotent) · 24 SQL assertion (`multi_tenant_foundation.sql` đếm 69/45/0, `tenant_scoped_rls.sql`, `role_scoped_clinical_read.sql`, `workflow_kernel.sql`…).

Test đáng nhớ: `test_middleware_order` (Starlette đăng ký ngược); `test_doc_dung_cot_da_chon.py` («capacity_service đọc cột không SELECT, cả bộ test xanh, staging vỡ»); `test_ly_do_huy_drift.py`, `test_audit_labels_drift.py`; `px-tu-che-ratchet-boundary.test.mts`; `kiem-vang.sh` 286 test/1,3s flow sống còn.

> «Canh chuỗi cứng thì đổi code là biểu thức trượt, và bài kiểm ngừng kiểm mà vẫn xanh […]. Canh quan hệ thì sống qua thay đổi: "router nào cầm idempotency_guard phải có chốt thả khoá" bắt được cả endpoint thứ năm chưa ra đời. Mỗi bài kiểm mới phải thử ngược.» — *SO-LUAT Luật 12.5*

### Bất biến mới thiết kế đích sẽ đưa vào đây

1. `event_log` không có INSERT trực tiếp ngoài `ghi_su_kien()` — grep ceiling từ 29 → 0 ([[tk-emit-function]]).
2. Mọi `event_type` xuất hiện trong code phải có dòng `event_catalog` (mở rộng drift test).
3. Mỗi UPDATE `status` của `appointment/visit/work_item` phải đi kèm đúng một event cùng transaction — SQL test đếm cặp trên fixture.
4. `work_item` PENDING/IN_PROGRESS không có `owner` hoặc `assigned_queue` = 0 (sau Phase A).
5. Timer: SQL test «expectation quá hạn không FIRED sau một vòng worker = đỏ».
6. Projection rebuild: test xoá view rồi dựng lại cho kết quả bằng nhau.
Chi tiết: [[chung-minh-event-driven]].
""",
 "links": ["adr-so-luat", "chung-minh-event-driven", "tk-emit-function", "tk-event-catalog-table", "multi-tenant-rls", "decision-checklist"],
},
{
 "id": "so-cai-phan-manh", "layer": L, "order": 820, "status": "mot-phan",
 "title": "Bảy sổ cái rời — event_log, work_item_event, tuong_tac_cskh, visit_route, visit_gate_override, inventory_txn, pos_outbox",
 "tag": "kiểm kê lược đồ prod",
 "summary": "Mỗi sổ đúng cho việc của nó; nhưng 'timeline của một lượt khám' phải join 5 khoá — thesis đòi một stream.",
 "body": """
| Sổ | Ghi gì | Append-only? | Vào `event_log`? |
|---|---|---|---|
| `event_log` | 17 loại nghiệp vụ + slot_hold | ✅ trigger | — |
| `work_item_event` | create/start/complete/skip/cancel/reassign | ✅ (không trigger, theo thiết kế) | ❌ (chỉ `audit_labels` có nhãn `work_item.*`) |
| `tuong_tac_cskh` | mọi lần chạm khách + mốc quầy | ✅ + `huy_luc` | ✅ `cskh.tuong_tac` |
| `visit_route` | tuyến áp cho lượt, superseded_at | ✅ | ✅ `dispatch.route_applied` |
| `visit_gate_override` | bỏ qua luật, lý do, người | ✅ | ❌ (chỉ log) |
| `inventory_txn` | xuất nhập kho theo lô | ✅ `inventory_txn_append_only` | ✅ `pharmacy.*` |
| `pos_outbox` | đẩy POS, attempts, DEAD | ❌ (trạng thái) | — |
| `thong_bao` | gọi bộ phận, đã đọc/đã xử lý | ❌ | ✅ lúc tạo, ❌ lúc xử lý |
| `visit_amendment` | (retired, còn ở prod) | | |
| `v_audit_log` | view đọc event_log có nhãn | | |

Điểm mạnh: mỗi sổ có ràng buộc đúng cho câu hỏi của nó (ví dụ `huy_luc` cặp; `visit_route` unique một hiệu lực). `v_dispatch_history` đọc lại từ `event_log` — «Không tạo bảng log thứ hai: hai nguồn sự thật cho cùng một câu chuyện là cách chắc chắn để chúng lệch nhau» — nguyên tắc đúng nhưng chưa áp toàn bộ.

Điểm yếu theo thesis §6: không có `stream_id` nên không trả lời được «mọi thứ xảy ra với lượt khám X theo thứ tự» bằng một câu SELECT; `work_item_event` — sổ quan trọng nhất cho ownership — **không** vào ledger chung; `visit_gate_override` (một Decision event đúng nghĩa) cũng không.

Thiết kế [[tk-mot-so-cai]]: **giữ nguyên bảy sổ** (chúng là bảng chuyên biệt có CHECK riêng), thêm trigger AFTER INSERT ở `work_item_event`, `visit_gate_override`, `thong_bao` (xử lý) đổ vào `event_log` với `stream_id` + `causation_id` — cùng transaction, không hàng chờ (Luật 8.1).
""",
 "links": ["stream-boundary", "tk-mot-so-cai", "event-log-table", "tuong-tac-cskh", "workflow-kernel", "gap-projection-rebuild"],
},
]
