---
title: "Lời hứa · Sự việc · Lần chạm — appointment ≠ visit ≠ tuong_tac_cskh, và máy trạng thái đặt lịch"
lop: 3
lop_ten: Code đang chạy
tag_nguon: "GIAI-THICH-CODE §0.4 · booking_service.py (2.037 dòng)"
trang_thai: Đã có
tags: [clinicai, lop3-code]
---

# Lời hứa · Sự việc · Lần chạm — appointment ≠ visit ≠ tuong_tac_cskh, và máy trạng thái đặt lịch

> [!abstract] Ba bảng, ba câu hỏi; 8 trạng thái lịch hẹn, 11 action, mỗi transition một event; visit 5 trạng thái với INCOMPLETE sinh từ sự cố thật.

> «`appointment` là **lời hứa**, `visit` là **sự việc**, `tuong_tac_cskh` là **lần chạm**. Ba thứ ấy có thể lệch nhau, và chính chỗ lệch đó mới là thông tin vận hành đáng giá nhất.» — *GIAI-THICH-CODE §0.4*

Quan hệ: `appointment 0..1 ↔ 0..1 visit` («KHÔNG PHẢI 1-1»: walk-in có visit không appointment; no-show có appointment không visit); `appointment 1 ↔ N tuong_tac_cskh` («gọi 3 lần = 3 dòng»); `visit 1 ↔ N work_item`.

### Máy trạng thái lịch hẹn (`booking_service.py`)

Trạng thái: SCHEDULED → CSKH_CONFIRMED → CONFIRMED → CHECKED_IN → COMPLETED; rẽ NO_SHOW / CANCELLED / DOCTOR_DECLINED. **Lịch mới vào thẳng CONFIRMED** («Quyết định của Quang (2026-08-04): bỏ vòng gọi-xác-nhận […] Cuộc gọi ấy CHÍNH LÀ thứ sinh ra lịch hẹn này»). 11 action: confirm · decline · complete · checkin · undo_checkin · cskh_confirm · cancel · no_show · reassign · assign_doctor · reschedule — mỗi cái một `Transition(to_status, from_statuses, allowed_roles, event_type)`.

Lưới thật ở Postgres, không ở Python: trigger `enforce_slot_capacity` + `pg_advisory_xact_lock(doctor, bucket, kind)`; `uq_appointment_patient_slot_live`; RPC `check_in_appointment` cấp `queue_number` theo ngày VN. «The checks in this module run before the write purely to produce a sentence a receptionist can act on».

Lý do huỷ có cấu trúc (`LY_DO_HUY`, 6 mã): BAO_KHI_XAC_NHAN · BAO_KHI_NHAC_HEN · BAO_VAO_GIO_KHAM («Ba mã đầu là BA THỜI ĐIỂM […] mỗi thời điểm tốn của phòng khám một khoản khác nhau») · DAT_TRUNG · BAC_SI_DOI_LICH · KHAC. Đây là **Principle 4 (Exception is first-class)** làm đúng, và là Decision event có lý do (Care Model §3.3 loại Decision) — chỉ thiếu cái tên.

### `visit`

OPEN → IN_PROGRESS → FINALIZED → AMENDED, cộng **INCOMPLETE** («Khách đang khám thì có việc phải về. Trước 06/08 hệ thống không có chỗ nào ghi điều đó»; đo hôm ấy: 35 lượt OPEN/IN_PROGRESS, 18 từ những ngày trước). FINALIZED bất biến: trigger `trg_visit_finalized_block`, đính chính chỉ qua `amend_visit` RPC (ADR-0008, TT13). Cột projection: `current_node_code`, `current_room_id`, `current_node_since`, `previous_node_code`.

### Đối chiếu thesis

`appointment` đúng mô hình «State machine + domain events» của Care Model §7. `visit` là Encounter — thesis đòi «event-sourced hoặc event-centric ledger»; hiện là bảng trạng thái với event thưa (`visit.checkin` trong SQL, `visit.closed_incomplete`, `clinical.signed/amended`). `tuong_tac_cskh` là Communication stream đúng nghĩa ([[tuong-tac-cskh|tuong_tac_cskh]]).

## Nối tới
- [[event-vs-record|Event khác record]]
- [[ontology-9|Ontology]]
- [[tuong-tac-cskh|tuong_tac_cskh]]
- [[selective-event-sourcing|Selective event sourcing]]
- [[idempotency-concurrency|Bất biến ép ở Postgres]]
- [[cskh-views|v_viec_cskh · v_trang_thai_cskh · luat_cskh]]

## Được dẫn từ
- [[ontology-9|Ontology]]
- [[event-vs-record|Event khác record]]
- [[selective-event-sourcing|Selective event sourcing]]
- [[tuong-tac-cskh|tuong_tac_cskh]]
- [[idempotency-concurrency|Bất biến ép ở Postgres]]
