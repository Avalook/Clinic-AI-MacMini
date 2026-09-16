---
title: "Sensing — thứ tự nguồn event theo 7 tiêu chí: thao tác có sẵn → một chạm → callback → thiết bị (sau pilot)"
lop: 5
lop_ten: Thiết kế đích
tag_nguon: "Thesis v2 §3.4 · Pilot §7 · Catalog §6"
tags: [clinicai, lop5-thiet-ke]
---

# Sensing — thứ tự nguồn event theo 7 tiêu chí: thao tác có sẵn → một chạm → callback → thiết bị (sau pilot)

> [!abstract] Không thêm ô nhập nào ở Phase 0–A; mọi event suy từ thao tác đang có; PatientLocationObserved để dành cho cảm biến.

Xếp hạng theo «Value per unit of data-entry burden»:

| Hạng | Nguồn | Event sinh ra | Thao tác thêm | Trạng thái |
|---|---|---|---|---|
| 1 | Chuyển trạng thái lịch hẹn (`apply_action`) | appointment.* | 0 | có, đổi cửa ghi |
| 1 | Mốc quầy `tuong_tac_cskh` (CHECK_IN/OUT/THANH_TOAN/MUA_THUOC) | PatientArrived/Left, PaymentCompleted | 0 (đã bấm) | có |
| 1 | `move_visit_to_station` | QueueEntered/Exited, PatientLocationObserved{method:'staff'} | 0 (Trưởng ca đã bấm) | có |
| 1 | Ký/duyệt bệnh án, nhập kết quả, thu tiền | clinical.signed, lab_result.entered, payment.recorded | 0 | có |
| 2 | Work item start/complete | ServiceStarted/Completed | 1 chạm/bước | có API, chưa ai bấm |
| 2 | Attestation «đã giải thích» | PatientInformed | 1 form ngắn | thêm ở Phase B |
| 3 | Đồng hồ | time.* | 0 | Phase A |
| 4 | Callback Zalo OA | MessageDelivered/PatientAcknowledged | 0 | sau pilot |
| 5 | LIS/HIS callback | ResultReady | 0 (tích hợp) | chưa có đối tác |
| 6 | Thiết bị (BLE/camera) | PatientLocationObserved{method:'ble', confidence} | 0 vận hành / đắt tích hợp + pháp lý (NĐ13 biometric) | **ngoài pilot** (Pilot §5) |

Hai luật sensing đưa vào code:
1. **Không đòi nhân viên bấm để xác nhận điều DB đã biết** (bài học `LUOTKHAM-01 born COMPLETED`). Policy `SPAWN_SPINE` đánh dấu `LUOTKHAM-02` COMPLETED khi lễ tân check-in *và* hồ sơ đã xác minh (có CCCD) — suy, không hỏi.
2. **Tín hiệu thủ công phải ghi `evidence_level='self_reported'` khi là lời khách** (Zalo «tôi đã đến»), `observed` khi là thao tác nhân viên, `inferred` khi là đồng hồ/policy. Card ATC hiện khác nhau (Spec §3).

Fallback (Pilot §7): mỗi tín hiệu có nguồn ưu tiên + fallback một chạm; bảng `signal_source (clinic_id, signal, primary, fallback, reliability_note)` là tài liệu sống — có thể chỉ là mục trong `event_catalog.producer`.

Cảm biến khi nào: theo 7 tiêu chí — khi pilot cho thấy `presence không tin cậy` là lý do suppression nhiều nhất của `unexplained_wait_risk` (đo `dismiss_reason`), lúc đó mới có phép đo để mở lại (Luật 7.2).

## Nối tới
- [[7-tieu-chi-event-source|Bảy tiêu chí cho mọi nguồn event]]
- [[pilot-scope|Partner Pilot Proposal]]
- [[event-catalog|Event Catalog v1]]
- [[tuong-tac-cskh|tuong_tac_cskh]]
- [[instantiate-visit|Check-in sinh việc]]
- [[tk-experience-state|experience_state]]
- [[fhir-mapping|Quan hệ với chuẩn y tế]]

## Được dẫn từ
- [[7-tieu-chi-event-source|Bảy tiêu chí cho mọi nguồn event]]
- [[pilot-scope|Partner Pilot Proposal]]
- [[fhir-mapping|Quan hệ với chuẩn y tế]]
