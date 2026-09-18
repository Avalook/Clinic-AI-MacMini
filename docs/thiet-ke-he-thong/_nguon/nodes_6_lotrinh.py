# -*- coding: utf-8 -*-
"""Lớp 6 — LỘ TRÌNH: thứ tự, cổng đo, bài kiểm, câu hỏi mở."""

L = 6

NODES = [
{
 "id": "lo-trinh-tong", "layer": L, "order": 1300,
 "title": "Lộ trình — nền trước, ownership sau, ngoại lệ rồi mới thông minh; mỗi phase một cổng đo",
 "tag": "Thesis v1 §11.1 · Catalog §18 · TAM-NHIN · Pilot §8",
 "summary": "Phase 0 (2 tuần) → A (3 tuần) → B (3 tuần) → C (sau khi B đo được); tổng ≈ 8–10 tuần khớp Pilot Proposal; không phase nào cần hạ tầng mới.",
 "body": """
Thứ tự lấy từ ba nguồn cùng nói một điều: v1 §11.1 («1 Nhìn thấy reality · 2 Tạo ownership · 3 Situational awareness · 4 Đóng communication loop · 5 Intelligence · 6 Tự động hoá có kiểm soát · 7 Học xuyên cơ sở»), Catalog §18 (Phase A closed-loop core → B exceptions & time → C capacity & intelligence), TAM-NHIN («lv4 chỉ đọc được state mà lv3 đã bắt đầy đủ và đáng tin»).

| Phase | Tuần | Mảnh | Cổng để sang phase sau (đo, không ước) |
|---|---|---|---|
| **0 — Nền** | 1–2 | envelope v2 · catalog · `ghi_su_kien` · một sổ cái · timeline view · baseline metric | `correlation_id` ≥ 95% event mới; INSERT trực tiếp = 0; `v_visit_state_tu_su_kien` drift = 0 trên staging 7 ngày; baseline 2 tuần đã ghi |
| **A — Vòng khép kín** | 3–5 | Work Item Protocol · expectation + đồng hồ · policy engine + 2 policy (spawn, ack-escalate) · notification_delivery · My Work/Team Queue có ack | ≥ 80% work item ack trong SLA; ≥ 90% có owner (Pilot §13.2); duplicate event → 0 việc trùng; ack timeout → escalation trong ≤ 60s (đo trên staging) |
| **B — Ngoại lệ & thời gian** | 6–8 | experience_state (3 state) · coverage · wait_threshold thành event · ContinuityRisk + follow_up_case · ATC card đủ 9 trường · failure event · freshness | false alarm ≤ ngưỡng thoả thuận; unexplained waiting minutes đo được và giảm so baseline; 0 privacy incident |
| **C — Năng lực & trí tuệ** | 9–10+ | overload event · metric đầy đủ · Recommend redistribution (shadow) · replay review · modules/ dời xong | Recommend precision > rule; Trưởng ca dùng «Vì sao» (Pilot §2 câu 2) |

Mỗi phase: **1 migration idempotent** (áp hai lần trong CI) → **2–4 PR** (nhánh ≤ 2 ngày, Luật 4.2) → **1 SQL test + 1 pytest thử ngược** ([[chung-minh-event-driven]]) → staging tự động → prod bấm 1h–4h → **kiểm hậu-deploy chỉ đọc** (DANG-LAM). ADR-0014/15/16 viết cùng migration của phase tương ứng.

Ba luật giữ trong suốt lộ trình:
1. **Không thêm ô nhập** cho tuyến đầu ở Phase 0–A (v2 §3.4). Chỉ Phase B thêm một form attestation ngắn.
2. **Baseline trước policy** (v2 §3.3): Phase 0 đo 2 tuần *trước khi* Phase A bật policy nào.
3. **Kill switch bằng dữ liệu**: `policy.is_active`, `authority_level` — tắt một luật là một UPDATE, không rollback deploy.

Về wedge ([[gap-wedge-mismatch]]): lộ trình **không chọn hộ**. Phase A áp Protocol lên node CSKH (`THEODOI-*`, nhắc tái khám) *và* node in-visit (`LUOTKHAM-*`) cùng lúc vì cùng bảng; policy nào bật trước là quyết định trong [[cau-hoi-mo]].

Nhân sự: 1 dev + AI. Ước công theo phase (không phải cam kết): Phase 0 ≈ 6–8 ngày làm việc, A ≈ 10–12, B ≈ 10–12, C mở. Song song vẫn phải trả nợ lv3 (42 route) — mỗi phase kèm 3–5 route dời về backend theo ratchet.
""",
 "links": ["phase-0-nen", "phase-a-closed-loop", "phase-b-exceptions", "phase-c-intelligence", "chung-minh-event-driven", "cau-hoi-mo", "4-tang-truong-thanh", "pilot-scope", "kill-criteria", "gap-wedge-mismatch"],
},
{
 "id": "phase-0-nen", "layer": L, "order": 1310,
 "title": "Phase 0 — Nền (tuần 1–2): sổ sự kiện đáng tin trước mọi thứ",
 "tag": "tk-event-envelope-v2 · tk-event-catalog-table · tk-emit-function · tk-mot-so-cai",
 "summary": "Không tính năng nào người dùng thấy; kết thúc bằng timeline một lượt khám đọc được và baseline 2 tuần.",
 "body": """
**Migration `202609xx_phase0_nen.sql`** (một file, idempotent): cột envelope v2 + trigger fill + backfill 449 dòng · `event_catalog` + seed từ `EVENT_LABELS` · `ghi_su_kien()` · trigger ledger cho `work_item_event`/`visit_gate_override`/`thong_bao.da_xu_ly` · `v_timeline_luot_kham` · `v_visit_state_tu_su_kien`. **Không** dựng `consumer_checkpoint` ở đợt này: giao thức con trỏ `seq > last_seq` đang bị chặn vì chưa an toàn (xem [[tk-event-envelope-v2]]) — cần giao thức xác nhận theo từng event và test commit đảo thứ tự trước đã. Áp staging → chạy `kiem-vang.sh` + `kiem-duong-ghi.py` (6/6) → prod trong khung.

**PR** (mỗi cái ≤ 2 ngày):
1. `engine/su_kien.py` + đổi cụm **booking** (`booking_service`, `slot_hold_service`, `booking_override_service`) sang `su_kien.ghi` với `causation` xuyên chuỗi create → hold release → checked_in → spine. Ratchet INSERT 29 → ~20.
2. Cụm **cskh + dispatch** (`tuong_tac_cskh`, `thong_bao`, `phan_hoi_khach`, `dispatch_service`, hai hàm SQL). Ratchet → ~10.
3. Cụm **clinical + config + patient + payment + pharmacy**. Ratchet → 0. `audit_labels.py` đọc từ DB (giữ dict làm fallback test).
4. `v_audit_log` đọc `event_catalog.nhan`; `/audit-log` thêm filter `category`; `VungLamViecKhach` đọc `v_timeline_luot_kham`.
5. Metric Phase 0: `v_metric_coverage`, `v_metric_freshness`, `metric_daily` + đồng hồ rollup **chưa cần** (chạy tay cuối ngày bằng script trong 2 tuần baseline).

**Xoá**: `event_bus/`, RabbitMQ mode trong `worker.py`, service `rabbitmq` trong compose (ADR-0002).

**PR template** thêm 4 câu của [[decision-checklist]] (event nào · việc nào · ai sở hữu · vòng đóng ở đâu).

**Cổng sang A**: `correlation_id IS NOT NULL` ≥ 95% event 7 ngày gần nhất · INSERT trực tiếp = 0 · drift `v_visit_state_tu_su_kien` = 0 trên staging 7 ngày liên tục (chạy `kiem-duong-ghi` mỗi đêm) · `slot_hold.*` không còn trong timeline · baseline metric 14 ngày ghi ra file trong `docs/`.

**Rủi ro**: trigger fill làm chậm INSERT? Đo: `pg_advisory_xact_lock` + 1 SELECT max — ở 2.400 dòng/ngày không đo được (Luật 5.2 «cuối bảng»); vẫn đo p95 `/appointments` trước/sau trên staging bằng `tai.py` sẵn có.
""",
 "links": ["lo-trinh-tong", "tk-event-envelope-v2", "tk-event-catalog-table", "tk-emit-function", "tk-mot-so-cai", "tk-projections", "decision-checklist", "phase-a-closed-loop"],
},
{
 "id": "phase-a-closed-loop", "layer": L, "order": 1320,
 "title": "Phase A — Vòng khép kín (tuần 3–5): việc có chủ, có nhận, có hạn, có leo thang",
 "tag": "Catalog §18 Phase A · tk-work-item-protocol · tk-expectation-timer · tk-policy-engine · tk-communication-delivery",
 "summary": "Kết thúc khi WorkAssigned ≠ WorkAcknowledged tồn tại thật trong dữ liệu và ack timeout tự leo thang mà không ai mở màn.",
 "body": """
**Migration `202609xx_phase_a.sql`**: cột/trạng thái Work Item Protocol (`work_item_open_needs_owner NOT VALID`) · `expectation` + trigger MET · `policy` + `policy_case` + seed 2 policy (SPAWN_SPINE_ON_CHECKIN, ACK_TIMEOUT_ESCALATE) · `notification_delivery` + `notification_route` (seed 1 dòng Telegram nhóm) · version/effective_from cho 6 bảng luật · SLA mặc định vào `node_definition.config` cho 41 node (từ Notion §13 ưu tiên P0 → ack 5′/complete 30′, P1 → 10′/60′, P2 → 30′/240′ — **con số để quản lý sửa**, không phải hằng).

**PR**:
1. `engine/viec.py`: 8 lệnh, completion contract, `uq_work_item_origin`; API `commands/{assign|claim|acknowledge|block|resume|reassign|escalate|reject_completion}`; `list_worklist` thêm trường. Test transition thuần + SQL owner.
2. `engine/dong_ho.py` trong `worker.py`: FIRED loop + đăng ký expectation từ `viec.assign()` (ack/complete) và từ `move_visit_to_station` (wait_threshold — chưa dùng cho experience, chỉ ghi event). Test idempotent.
3. `engine/luat.py`: evaluator thuần + runner đọc checkpoint; 2 policy; `policy_case` chạy trong pytest (`test_policy_cases.py` load từ seed).
4. `engine/tin_nhan.py`: relay đọc `notification_delivery`; DEAD; `notification.failed`. Bỏ `event_published` khỏi relay.
5. Giao diện: `/tasks` nút **Nhận việc** + «Vì sao tôi nhận»; `/work-items` tab overdue/unclaimed; `thong_bao` mang `work_item_id`; `work-item-status.ts` thêm từ vựng.
6. **CSKH**: policy thứ 3 `NHAC_TAI_KHAM_THANH_VIEC` — mỗi `nhac_tai_kham CHO_GOI` → work item THEODOI-03 owner queue CSKH, completion `required_event cskh.tuong_tac[NHAC_HEN|XAC_NHAN_LICH]`; expectation thay `sinh_viec` lúc mở màn. Đây là mảnh cho người dùng đang có (5 CSKH) thấy khác biệt ngay: việc **xuất hiện dù không ai mở màn**, và Trưởng ca thấy ai chưa nhận.

**Kịch bản bấm thử (Luật 12.4)**: (1) tạo nhắc tái khám cho ngày mai → sáng mai việc có trong `/tasks` CSKH với hạn; (2) CSKH A bấm Nhận → B thấy «A đã nhận»; (3) không ai nhận 5′ (giả lập bằng cấu hình 1′) → Trưởng ca có thông báo + việc ESCALATED; (4) A ghi «Đã gọi nhắc» → việc tự COMPLETED, timeline khách có 5 dòng đúng thứ tự, không dòng nào trùng khi bấm hai lần.

**Cổng sang B** (Pilot §13.2): ≥ 80% ack trong SLA · ≥ 90% có owner · ≥ 85% completion có evidence (`required_event`/`attestation`) · không tăng thao tác tuyến đầu (đếm click qua telemetry `slot_hold`-style riêng) · `VALIDATE CONSTRAINT work_item_open_needs_owner` chạy được.
""",
 "links": ["lo-trinh-tong", "phase-0-nen", "phase-b-exceptions", "tk-work-item-protocol", "tk-expectation-timer", "tk-policy-engine", "tk-communication-delivery", "nhac-tai-kham", "gap-wedge-mismatch"],
},
{
 "id": "phase-b-exceptions", "layer": L, "order": 1330,
 "title": "Phase B — Ngoại lệ & thời gian (tuần 6–8): chờ vô định thành việc có chủ; rời cơ sở không rơi khỏi hệ",
 "tag": "Catalog §18 Phase B · tk-experience-state · tk-atc-ui · tk-reliability-playbook",
 "summary": "Ba experience state, coverage, ATC card đủ 9 trường, failure event; đo unexplained waiting minutes so baseline.",
 "body": """
**Migration `202609xx_phase_b.sql`**: `experience_state` + `experience_config` · `tuong_tac_cskh.chu_de/hieu_luc_den` + hàm `co_coverage` · `patient.khong_lam_phien_den` · `follow_up_case` writer qua policy · `event_quarantine` · seed policy UNEXPLAINED_WAIT, CONTINUITY_ON_CHECKOUT, HANDOFF_UNCERTAINTY (đổi ACK_TIMEOUT thành experience có state) · `station_load_sample`.

**PR**:
1. `engine/trai_nghiem.py`: lifecycle + commands confirm/dismiss + auto resolve/expire; event `experience.*`.
2. Policy 3 state + `policy_case` cho từng nhánh Spec §7 (điều kiện kích hoạt **và** 4 điều kiện không kích hoạt).
3. ATC card 9 trường + cảnh báo có id/ack/why; `/display` bước tiếp theo.
4. `tin_nhan` + `ops_status` + failure event; freshness chip.
5. Attestation form «Đã giải thích cho khách» (chủ đề + nội dung tối thiểu) — **ô nhập duy nhất thêm mới** trong cả lộ trình.
6. Metric Phase B + rollup đồng hồ.

**Kịch bản bấm thử**: (1) Trưởng ca chuyển khách vào SA2, cấu hình ngưỡng 2′; (2) sau 2′ card đỏ «chưa được giải thích», việc GIAI_THICH_CHO đến CSKH; (3) CSKH ghi attestation chủ đề «chờ» → risk resolved, card xanh «đã báo lúc 10:05, hiệu lực 15′»; (4) qua 15′ chưa xong → risk mở lại (informed_wait hết hạn); (5) checkout khi còn kết quả chưa xem → `follow_up_case` + việc THEODOI-01 cho CSKH có hạn; (6) rút token Telegram trên staging → `/ops` báo degraded + DEAD, không ai phải mở Kuma.

**Cổng sang C** (Pilot §13.3–4): unexplained waiting minutes giảm ≥ 20% so baseline Phase 0 (hoặc: đo được và có xu hướng, vì baseline có thể là 0 nếu chưa ai chuyển phòng — nói thật trong báo cáo); false alarm (dismissed/detected) ≤ 30%; notification burden ≤ N/vai/ca thoả thuận; 0 privacy incident; nhân viên không quay lại Zalo cho việc «đã giải thích» (đếm attestation/ngày > 0).
""",
 "links": ["lo-trinh-tong", "phase-a-closed-loop", "phase-c-intelligence", "tk-experience-state", "tk-atc-ui", "tk-reliability-playbook", "tk-metrics", "experience-state"],
},
{
 "id": "phase-c-intelligence", "layer": L, "order": 1340,
 "title": "Phase C — Năng lực & trí tuệ (tuần 9+): overload thành event, Recommend có người duyệt, replay để học",
 "tag": "Catalog §18 Phase C · tk-ai-placement · tk-metrics · tk-modular-monolith",
 "summary": "Chỉ bắt đầu khi B có số; mọi thứ ở đây tắt được bằng UPDATE; kết thúc = 12 bằng chứng event-driven đều xanh.",
 "body": """
**Mảnh**: `StaffOverloadDetected`/`NodeCongestionDetected`/`CapacityRestored` từ `station_load_sample` (derived, theo **phòng**) · policy `RECOMMEND_REDISTRIBUTION` (authority recommend, shadow 2 tuần) · lab triage phát derived event có confidence · replay review script + trang «xem lại ca» đọc timeline theo ca trực · metric đủ 4 nhóm · dời nốt `services/` vào `modules/` + import-linter + manifest checker · `event_log` partition ngưỡng.

**Cổng kết thúc pilot** (Pilot §16 Go/Iterate/No-go): observability + adoption gate đạt · ≥ 1 outcome cải thiện đáng tin · không vi phạm guardrail · «phần lớn capability có thể reuse cho journey tiếp theo» — kiểm bằng cách **seed tenant giả thứ hai** với catalog/policy/threshold khác và chạy `policy_case` của nó xanh mà không sửa code (v3 §2.9 «chứng minh ontology có khả năng cấu hình»).

**Nếu C không tăng giá trị so với B** (v2 §3.10): tắt `authority_level` về `observe`, giữ B — «nên bỏ bớt AI chứ không nhất thiết bỏ ClinicAI».

**Sau C** (ngoài phạm vi thiết kế này, ghi để không quên): Zalo OA channel (D010) · LIS adapter theo khuôn PosPort · ký số EMR + CCCD (TT13/2025, hạn 31/12/2026 — Tổng-Quan §14.1) · cơ sở thứ hai Hào Nam khi có mô tả vận hành (`kien-truc-nhieu-phong-kham.md` §5 «Chưa nên làm: đa cơ sở đầy đủ»).
""",
 "links": ["lo-trinh-tong", "phase-b-exceptions", "tk-ai-placement", "tk-metrics", "tk-modular-monolith", "chung-minh-event-driven", "macro-v3", "kill-criteria"],
},
{
 "id": "chung-minh-event-driven", "layer": L, "order": 1350,
 "title": "12 bằng chứng 'event-driven thật' — mỗi cái một test trong CI hoặc một kịch bản staging",
 "tag": "Care Model §26 · SO-LUAT Luật 12.5",
 "summary": "Pilot chỉ được gọi event-driven nếu 12 điều này chứng minh được; đây là bảng nghiệm thu kỹ thuật của toàn thiết kế.",
 "body": """
| # | Bằng chứng (Care Model §26) | Test | Phase |
|---|---|---|---|
| 1 | Một event nguồn cập nhật nhiều projection nhất quán | SQL: sau `dispatch.moved`, `v_timeline`, `_OVERVIEW_SQL`, `v_visit_state_tu_su_kien` cùng node | 0 |
| 2 | Mở event timeline của một encounter và hiểu vì sao state hiện tại tồn tại | Kịch bản staging: timeline có causation liền từ `appointment.created` → `checked_in` → `work_item.create` × 7 | 0 |
| 3 | Rebuild một projection từ lịch sử | `v_visit_state_tu_su_kien` == `visit` (drift 0); `rebuild-metric.py` cho cùng số | 0 / C |
| 4 | Duplicate event không tạo duplicate work | pytest: gọi policy hai lần cùng event → 1 work item (`uq_work_item_origin`) | A |
| 5 | Event đến trễ được xử lý mà không phá lịch sử | pytest: `ghi` với `occurred_at` quá khứ → `stream_version` mới, `recorded_at` = now, projection recompute; outcome đã đóng không tự mở | A |
| 6 | Timeout phát hiện một expected event bị thiếu | SQL: expectation quá hạn → sau một vòng đồng hồ có `time.*` event; chạy lại → 0 | A |
| 7 | Work Item không đóng ở "notification sent" | pytest: relay SENT → work_item vẫn ASSIGNED (thử ngược đỏ) | A |
| 8 | Journey rẽ nhánh dựa trên event thực tế | pytest policy_case: `dispatch.checkout` + lab chưa review → follow_up_case + THEODOI-01 | B |
| 9 | Experience Risk có evidence và resolution event | SQL CHECK `es_resolved_needs_event`; pytest resolve tự động khi attestation tới | B |
| 10 | Integration failure được nhìn thấy | pytest: provider 401 → DEAD + `integration.unavailable` + ops degraded | B |
| 11 | Policy change có version và không viết lại lịch sử | SQL: UPDATE `luat_cskh` → `policy.version_activated`; work item cũ giữ `policy_version` cũ | A |
| 12 | Một ca vận hành có thể replay để học | script dry-run replay không tạo delivery; trang xem lại ca đọc được «bottleneck bắt đầu từ event nào» | C |

Cộng bốn bất biến của repo giữ nguyên: tenant audit ceiling 0 · service-role allowlist 2 · route chạm DB ratchet 42↓ · coverage ≥ 80.

Mỗi test mới **thử ngược trước khi tin** (Luật 12.5): cố ý bỏ trigger/unique/guard → phải đỏ đúng chỗ.
""",
 "links": ["lo-trinh-tong", "ci-guards", "15-invariant", "tk-projections", "tk-work-item-protocol", "tk-expectation-timer", "tk-experience-state", "tk-reliability-playbook", "pilot-scope"],
},
{
 "id": "cau-hoi-mo", "layer": L, "order": 1360,
 "title": "Câu hỏi mở — 8 quyết định không phải kỹ thuật, cần Quang/Tuyền chốt trước Phase A",
 "tag": "để debate, không tự trả lời",
 "summary": "Wedge · tên canonical · ai sở hữu luật · ngưỡng · Zalo · journey pilot · Hào Nam · KPI cá nhân.",
 "body": """
1. **Wedge trước: CSKH hay in-visit?** Thesis nói in-visit; người dùng thật là CSKH; kiến trúc trung lập. Đề xuất: Phase A bật policy cho **cả hai** nhưng đo CSKH trước (có dữ liệu ngay). Cần Quang gật vì nó đổi câu chuyện với chị Thu/Sáng Ý.
2. **Tên event canonical**: giữ `appointment.created` (tiếng Anh snake, đang chạy) + cột `canonical` PascalCase, hay đổi hẳn sang thesis ngay? Tôi chọn giữ + ánh xạ (rủi ro 0). Quang có muốn tài liệu đối tác dùng tên thesis không?
3. **Ai sở hữu luật?** `policy.owner_role` mặc định MANAGEMENT; Trưởng ca được sửa ngưỡng (`dispatch_threshold` đã cho) nhưng có được sửa SLA ack không? Pilot §11 nói Operational Owner sở hữu policy — là ai ở Dr4Women?
4. **Ngưỡng ban đầu**: ack 5′/10′ leo thang (Protocol §11 ví dụ), chờ 20′/8 người (`dispatch_threshold` mặc định), coverage 15′ — số nào là của Dr4Women? Cần workshop theo Journey §11 với Trưởng ca thật.
5. **Zalo OA**: bao giờ có? Trước đó, «PatientInformed» chỉ có bằng attestation của CSKH — chấp nhận ở pilot (Tuyền đã chốt 14/08), nhưng nói rõ trong báo cáo pilot.
6. **Journey pilot** (Pilot §4.2): chọn 1–2 loại encounter tần suất cao — Phụ khoa + siêu âm? Ảnh hưởng node nào được seed SLA và policy nào bật.
7. **Hào Nam**: `is_active=false`, chưa mô tả vận hành. Không thiết kế gì cho đa cơ sở ngoài `location_id` đã có — đúng chưa?
8. **KPI cá nhân**: Pilot §5 và Protocol §17 cấm chấm điểm bằng số task. Quản lý phòng khám có đồng ý *không* có bảng «ai làm nhiều việc nhất» không? Nếu không đồng ý, đó là kill criterion §3.10 cuối («tăng visibility làm tăng giám sát») và phải nói trước.

Hai câu kỹ thuật tôi **đã tự quyết** và ghi lý do (đảo được nếu Tuyền không đồng ý): (a) không tạo bảng `domain_event` mới — cộng cột vào `event_log` ([[tk-event-envelope-v2]]); (b) đồng hồ + policy engine chạy **trong tiến trình relay** chứ không tiến trình riêng ([[tk-expectation-timer]]) — tách khi có phép đo.
""",
 "links": ["gap-wedge-mismatch", "wedge", "tk-event-catalog-table", "tk-policy-engine", "tk-communication-delivery", "pilot-scope", "humane-ops", "tk-event-envelope-v2", "tk-expectation-timer", "lo-trinh-tong"],
},
]
