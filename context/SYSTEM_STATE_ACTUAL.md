# SYSTEM_STATE_ACTUAL — Ảnh chụp hiện trạng THẬT

> Mục đích: đồng bộ với AI Planner. **Mọi số liệu đếm/đọc THẬT từ code + DB** (read-only),
> KHÔNG chép từ doc canon (doc đã lệch nhiều lần).
> Khảo sát LẦN ĐẦU: 2026-05-25. **REFRESH lần 2: 2026-06-03** (sau khi LOAD wet sync + 17 migration 021–038 đã apply). Các con số ở dưới đã được CẬP NHẬT theo DB ngày 03/06; phần lịch sử 25/5 vẫn giữ ở §1.5 + ghi chú để truy vết.

---

## ⚡ TÓM TẮT THAY ĐỔI TỪ 25/5 → 03/06

| Trục | 25/5 | 03/06 |
|---|---|---|
| BASE TABLE | 19 (17 canon + mpi_merge_queue + 1 view) | **27** (26 domain + schema_migrations) |
| Migration đã apply | 20 (001–020) | **schema_migrations bảng có 24 row, nhưng files 021–038 đã chạy thật trên DB** (runner ghi log sót — xem §1.6) |
| patient | 30 demo | **5.524** (đã LOAD từ Notion clone) |
| appointment | 0 | **9.177** (status: COMPLETED 5168 / NO_SHOW 3145 / SCHEDULED 857 / CONFIRMED 5 / CHECKED_IN 1 / DOCTOR_DECLINED 1; range 1989-04-27 → 2027-04-09) |
| visit · clinical_record · lab_result | 0/0/0 | **5.583 / 5.583 / 4.724** |
| prescription | bảng CHƯA tạo (PARKED) | **14.300** (bảng đã có — migration 031, LOAD xong) |
| cskh_action · service_log · cskh_log | 0 (3 bảng CHƯA tạo) | **31.179 / 15.075 / 1.301** (3 bảng đã có — migration 029/030/037) |
| booking_channel | bảng KHÔNG tồn tại | **7 row** (migration 026) |
| patient_contact_channel | bảng KHÔNG tồn tại | **5.518 row** (migration 027) |
| patient_next_of_kin | bảng KHÔNG tồn tại | **0 row** (migration 028 — bảng có, data chưa import) |
| service_type | 1 | **14** ✓ |
| staff | 0 | **41** (40 từ Notion + 1) |
| work_roster | bảng KHÔNG tồn tại | **88 row** (migration 035) |
| Voice-to-EMR | 0% | **vẫn 0%** (không thay đổi) |
| Vẫn rỗng | — | `patient_medical_profile`, `pregnancy`, `patient_next_of_kin`, `staff_task`, `staff_capability`, `work_session`, `work_session_staff`, `ultrasound_record`, `visit_amendment`, `mpi_merge_queue` |

→ **3 nợ Phase-1 (PatientContactChannel/BookingChannel/PatientNextOfKin) đã được tạo bảng + LOAD data** (trừ next_of_kin chưa có data nguồn — defer được). Nợ §2.1 bên dưới **đã giải**.

---

## STEP 0 — Git state

| | |
|---|---|
| Branch | `feat/t-transform-01` |
| Last commit | `ef538d5` — feat(migration): T-TRANSFORM-01 Notion CSV → staged files (no DB write) |
| Trạng thái | **DIRTY** — 2 file modified (`context/CURRENT_PROGRESS.md`, `worklog/CURRENT_PROGRESS.md`) + 1 untracked (`.ai/worklog/20260522.md`) |
| Nhánh đã push? | CHƯA (commit ef538d5 còn local) |

---

## STEP 1 — Database THẬT (CẬP NHẬT 03/06)

### 1.1 Bảng tồn tại (read THẬT từ `information_schema.tables` 03/06)

- **27 BASE TABLE** trong schema `public` (= 26 domain + `schema_migrations`).
- Toàn bộ 27 bảng: `appointment`, `booking_channel`, `clinic_location`, `clinical_record`, `cskh_action`, `cskh_log`, `event_log`, `lab_result`, `mpi_merge_queue`, `patient`, `patient_contact_channel`, `patient_medical_profile`, `patient_next_of_kin`, `pregnancy`, `prescription`, `schema_migrations`, `service_log`, `service_type`, `staff`, `staff_capability`, `staff_task`, `ultrasound_record`, `visit`, `visit_amendment`, `work_roster`, `work_session`, `work_session_staff`.
- Files migration thư mục `src/migrations/` (`.sql` forward, không tính `.down.sql`): tới `038`. Trong `schema_migrations` chỉ có 24 row (tới `037`); **gap** 021–032 + 034 + 038 không có trong bảng nhưng bảng đích thật sự đã được tạo + có data → runner ghi log SÓT, KHÔNG phải thiếu migration thật. Xem §1.6.

**Map vs canon 35 bảng:** 26 domain table / 35 canon. Bù lại còn 3 bảng "ngoài canon nhưng cần thật": `cskh_action`, `cskh_log`, `service_log` (data từ Notion). + `mpi_merge_queue` (hỗ trợ MPI dedup). + `work_roster` (lịch trực hàng tuần).

### 1.2 Map theo 9 domain (CẬP NHẬT 03/06)

| Domain | Canon | Có (table) | Thiếu | Phase phần thiếu |
|---|---|---|---|---|
| D1 Master Data | 3 | `clinic_location`, `service_type`, **`booking_channel`** ✅ | — | ✅ 3/3 |
| D2 Patient | 5 | `patient`, `patient_medical_profile`, `pregnancy`, **`patient_contact_channel`** ✅, **`patient_next_of_kin`** ✅ | — | ✅ 5/5 (next_of_kin bảng có, data 0) |
| D3 Clinical | 5 | `visit`, `clinical_record`, `visit_amendment`, `ultrasound_record`, **`prescription`** ✅ | — | ✅ 5/5 |
| D4 Staff & Sched | 5 | `staff`, `staff_capability`, `work_session`, `work_session_staff`, `appointment` | — | ✅ 5/5 |
| D5 Lab | 3 | `lab_result` | **LabPartner**, **LabOrder** | P2 |
| D6 Task | 2 | `staff_task` (= Task, đổi tên) | **TaskEvent** | P2 |
| D7 Finance | 2 | — | **Invoice**, **InvoiceLineItem** | P2 |
| D8 Inventory | 6 | — | Drug, DrugBatch, DrugInvTxn, Supply, ServiceSupplyMapping, SupplyInvTxn | P3 |
| D9 Infra | 4 | `event_log` | **KBPage**, **KBChunk**, **KBPolicyRule** | P2 |
| **Tổng** | **35** | **23/35 canon** | **12 thiếu** | 8×P2 + 6×P3 (đã hết bảng P1) |

**Ngoài canon nhưng đã có:** `cskh_action` (31k row), `cskh_log` (1.3k), `service_log` (15k), `mpi_merge_queue` (0), `work_roster` (88) — phục vụ Phase-1 dashboard + MPI dedup.

### 1.3 Bảng/đối tượng NGOÀI 35 canon (giữ nguyên)

- `mpi_merge_queue` — Human Review Queue cho MPI dedup (canon §3.2 mô tả logic, không liệt kê bảng). Count 03/06 = 0 (chưa có conflict cần review tay).
- `patient_summary` — VIEW (không phải table); Q-19 hiện thực theo on-demand.
- `cskh_action` (31.179), `cskh_log` (1.301), `service_log` (15.075), `work_roster` (88) — bảng ngoài canon nhưng cần cho Phase-1 dashboard.

### 1.4 Row counts THẬT (03/06 — đọc trực tiếp Supabase)

| Bảng | Count 25/5 | Count 03/06 | Phân loại |
|---|---|---|---|
| `schema_migrations` | 20 | **24** | runner sót log cho 021–032, 034, 038 (xem §1.6) |
| `clinic_location` | 2 | 2 | seed KN+HN ✓ |
| `service_type` | 1 | 14 | seed Notion ✓ |
| `booking_channel` | — | **7** | bảng mới (mig 026) |
| `staff` | 0 | **41** | seed Notion lib 3 ✓ |
| `patient` | 30 demo | **5.524** | **WET SYNC ĐÃ CHẠY**: 1 row đủ DOB+gender / 5.523 skeleton (đủ phone) |
| `patient_contact_channel` | — | **5.518** | bảng mới (mig 027) — đã LOAD phone từ clone |
| `patient_medical_profile` | 0 | 0 | rỗng (dashboard sẽ ghi dần) |
| `patient_next_of_kin` | — | 0 | bảng mới (mig 028), data nguồn không có |
| `pregnancy` | 0 | 0 | rỗng |
| `appointment` | 0 | **9.177** | COMPLETED 5168 / NO_SHOW 3145 / SCHEDULED 857 / CONFIRMED 5 / CHECKED_IN 1 / DOCTOR_DECLINED 1; range 1989-04-27 → 2027-04-09 |
| `visit` | 0 | **5.583** | bằng số clinical_record (mỗi visit gắn 1 record) |
| `clinical_record` | 0 | **5.583** | ghi qua LOAD wet sync |
| `lab_result` | 0 | **4.724** | đã LOAD |
| `prescription` | — | **14.300** | bảng mới (mig 031) — đã LOAD (PARKED giải xong) |
| `cskh_action` | — | **31.179** | bảng mới (mig 029) — file CSKH 31k đã import |
| `service_log` | — | **15.075** | bảng mới (mig 030) — file Dịch vụ 15k đã import |
| `cskh_log` | — | **1.301** | bảng mới (mig 037) |
| `event_log` | 0 | **20** | bắt đầu có log thật |
| `work_roster` | — | **88** | bảng mới (mig 035) — lịch trực tuần |
| `mpi_merge_queue` | 0 | 0 | chưa có conflict tay |
| `ultrasound_record`, `visit_amendment`, `staff_task`, `staff_capability`, `work_session`, `work_session_staff` | 0 | 0 | rỗng (Phase 2+ scope) |

### 1.5 TRANSFORM đã LOAD vào DB chưa? → **ĐÃ LOAD (03/06 confirmed)**

- 25/5: T-TRANSFORM-01 xuất 5728 patient ra file staged (`scripts/data_migration/output/`, gitignored) — chưa load.
- 29/5: bỏ CSV, viết `scripts/data_import/notion_to_sources.py` + `sync_to_supabase.py` (commit 30c7028) đọc thẳng Notion clone (LINK_NOTION_PAGE_ID). Wet sync full chạy nền.
- **03/06 confirmed (đọc DB thật):** đã LOAD vào DB — patient 5.524, appointment 9.177, visit 5.583, clinical_record 5.583, lab_result 4.724, prescription 14.300, cskh_action 31.179, service_log 15.075, cskh_log 1.301, patient_contact_channel 5.518. **NHỊP 2 LOAD = ĐÃ XONG về cơ bản.**
- Phần còn lệch nhẹ: file transform ban đầu 5.728 BN, DB có 5.524 → chênh 204 (có thể là dòng reject 415 lọc bớt + dedup MPI). CHƯA so chi tiết.
- Lab=4.724 trong khi dry-run 29/5 ra 0 → wet sync sau đã extract được lab từ nguồn khác (cần khảo lại path).

### 1.6 Gap `schema_migrations` (runner ghi log sót)

- Files forward trong `src/migrations/`: 001 → 038 (có 037 + 038, bỏ qua 033 trong files cũ nhưng `033_append_only_guard` có).
- Bảng `schema_migrations` chỉ có 24 row: 001–020 + 033, 035, 036, 037 → **gap** 021–032 (12 row) + 034 + 038.
- **Bằng chứng các migration "gap" đã chạy thật:**
  - 026/027/028 (booking_channel/patient_contact_channel/patient_next_of_kin) — 3 bảng có tồn tại + data.
  - 029/030 (cskh_action/service_log) — bảng tồn tại + data (31k + 15k).
  - 031 (prescription) — bảng tồn tại + 14.300 row.
  - 034 (appointment doctor_declined) — status DOCTOR_DECLINED đã xuất hiện trong appointment.
  - 038 (patient admin fields) — cột gender/ethnicity/.../guardian_name có trong patient.
- → Runner apply trực tiếp psql/tay nhưng quên INSERT vào `schema_migrations`. **KHÔNG ảnh hưởng schema thật**, nhưng làm script idempotency có thể chạy lại nhầm. NỢ: backfill 14 row vào `schema_migrations` cho khớp.

---

## STEP 2 — Nợ kỹ thuật (CẬP NHẬT 03/06)

### 2.1 Ba nợ Phase-1 → **ĐÃ GIẢI cả 3**

| Entity canon | Tình trạng 25/5 | Tình trạng 03/06 |
|---|---|---|
| **PatientContactChannel** | thiếu bảng, chỉ có `phone_primary`/`phone_secondary` TEXT | ✅ `patient_contact_channel` 5.518 row (mig 027) |
| **BookingChannel** | TEXT trần không FK | ✅ `booking_channel` 7 row + appointment FK (mig 026) |
| **PatientNextOfKin** | không tồn tại | ✅ bảng có (mig 028), data 0 — defer ok |

### 2.2 Prescription → **ĐÃ GIẢI**

- ✅ Bảng `prescription` đã tạo (mig 031), LOAD 14.300 row. PARKED hết.

### 2.3 Các lệch doc-vs-thực-tế (cập nhật)

- ✅ **`service_type` seed**: từ 1 → 14 row (mig 003 seed Notion đã apply 29/5).
- ✅ **`staff` seed**: từ 0 → 41 row (mig 005 seed Notion lib 3 đã apply 29/5).
- **`patient.phone_primary` nullable** — vẫn lệch CÓ CHỦ ĐÍCH (hợp skeleton). Giữ nguyên.
- **3 lệch schema cho LOAD** đã được xử lý trong `sync_to_supabase.py` (visit tạo trước clinical_record, lab dùng `triage_group`).
- **MỚI phát sinh:** gap `schema_migrations` (§1.6).
- **MỚI phát sinh:** chỉ 1/5524 patient có cả DOB + gender — 5.523 dòng skeleton thiếu DOB hoặc gender. Bình thường với data Notion (gender ít khai); nhưng nếu form hồ sơ bắt buộc cần xử lý.

---

## STEP 3 — Code đã build

### 3.1 Sub-graphs (`src/clinicai/graphs/` + orchestrator wiring)

| Sub-graph | Module thật? | Wired vào orchestrator | Trạng thái |
|---|---|---|---|
| **scheduling** | ✅ `graphs/scheduling/` (graph 86 + nodes 238 dòng + parsers + session_mapper) | real khi `pool` present, else stub | **DONE** (có fallback stub) |
| **lab_triage** | ✅ `graphs/lab_triage/` (graph 107 + nodes 347 dòng) | real-wrapper khi pool present | **DONE** (lưu ý: CURRENT_PROGRESS cũ ghi "P9.4 chưa code" — doc lệch, code ĐÃ có) |
| **task_manager** | ✅ `graphs/task_manager/` (graph 52 + nodes 187 dòng) | real-wrapper khi pool present | **DONE** |
| **pre_visit_brief** | ✅ `graphs/pre_visit_brief/` (graph 50 + nodes 106 dòng) | trong orchestrator vẫn hardwire **STUB**; expose qua API `/brief` | **DONE standalone**, chưa nối orchestrator |
| **communication** | ❌ chỉ có `communication_stub_node` | **STUB** | **CHƯA build** |

- Orchestrator route 5 intent: scheduling / lab / communication / task / previsit (+ general→respond).
- **4 module sub-graph thật + 1 stub-only (communication).**
- Services thật: `mpi_service`, `patient_service`, `patient_context_service`, `scheduling_service`, `staff_service`, `event_service`. Golden record engine: `golden_record/engine.py`.
- API routers: `brief`, `lab`, `orchestrator`, `scheduling`, `staff`, `tools`.

### 3.2 Test

- **71 file test**, **412 test function**, **12 skip marker**.
- Kết quả pass gần nhất (ghi nhận từ worklog, chưa chạy lại full ở phiên này): T-TRANSFORM-01 **20/20 pass** (ruff + mypy strict), safety-gate 017 **5/5 pass** (chặn thật).

### 3.3 Voice-to-EMR → **CHƯA CÓ NHẬN GIỌNG NÓI**

- **0 file Python** match `whisper|PhoWhisper|speech|transcribe|stt`.
- DB chỉ có **cột placeholder** trong `clinical_record`: `voice_note_url`, `voice_transcript`, `voice_note_reviewed` (migration 017).
- KHÔNG có speech-to-text, KHÔNG có pipeline transcription, KHÔNG có sub-graph clinical/EMR write nối vào orchestrator.
- **Kết luận: Voice-to-EMR chưa làm — kể cả nhánh text-EMR cũng chưa wired. Mới có schema cột chờ data.**

---

## ĐỒNG BỘ VỚI PLANNER (5 dòng — refresh 03/06)

1. **DB: 23/35 bảng canon** đã hiện thực (D1/D2/D3/D4 đủ 5/5; D5 còn LabPartner+LabOrder; D6 còn TaskEvent; D7 Finance + D8 Inventory + KB của D9 = chưa). **Hết bảng Phase-1**, 3 nợ trước đã giải.
2. **Data THẬT đã vào DB** — patient 5.524, appointment 9.177, visit/clinical_record 5.583, lab 4.724, prescription 14.300, cskh_action 31.179, service_log 15.075. NHỊP 2 LOAD ĐÃ XONG.
3. **Code: vẫn 4/5 sub-graph thật** (scheduling, lab_triage, task_manager, pre_visit_brief); communication còn stub; pre_visit_brief chưa nối orchestrator. (Test count chưa kiểm lại ở phiên này.)
4. **Voice-to-EMR vẫn 0%** (chưa có speech-to-text, chỉ có cột DB chờ).
5. **Việc tiếp theo:** (a) backfill 14 row vào `schema_migrations` cho khớp 021–032/034/038; (b) Phase-1 dashboard — đang làm "Hồ sơ lâm sàng" + "trang chủ 2 bảng" + roles; (c) Phase-2 còn lại: LabPartner/LabOrder, TaskEvent, Invoice (sau khi Phase-1 production); (d) communication stub → thật; (e) voice (chờ team).

---

*SYSTEM_STATE_ACTUAL.md · khảo sát read-only 2026-05-25 + REFRESH 2026-06-03 (chỉ đọc DB, không sửa code, không chạy migration, không ghi DB).*
