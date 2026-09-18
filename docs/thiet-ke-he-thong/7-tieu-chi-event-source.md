---
title: "Bảy tiêu chí cho mọi nguồn event — value per unit of data-entry burden"
lop: 1
lop_ten: Hiến pháp sản phẩm
tag_nguon: "Thesis v2 §3.4"
tags: [clinicai, lop1-hien-phap]
---

# Bảy tiêu chí cho mọi nguồn event — value per unit of data-entry burden

> [!abstract] Điều kiện khả thi quan trọng nhất: thu được reality mà không bắt người làm thư ký; thước đo cho IoT, camera, nhập tay.

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

Nguồn **đắt nhất theo tiêu chí 5**: bắt điều dưỡng bấm `start`/`complete` từng work item. Migration `20260731000003` đã thấy điều này và cho `LUOTKHAM-01` sinh ra ở trạng thái `COMPLETED` ngay lúc check-in: «pressing check-in IS performing tiếp nhận người bệnh». Thiết kế đích ([[tk-sensing|Sensing]]) đi đúng hướng ấy: **suy event từ thao tác đã có** trước, hỏi người sau cùng.

## Nối tới
- [[tk-sensing|Sensing]]
- [[event-catalog|Event Catalog v1]]
- [[pilot-scope|Partner Pilot Proposal]]
- [[kill-criteria|Kill criteria, proof plan và baseline Excel + Zalo]]
- [[tuong-tac-cskh|tuong_tac_cskh]]

## Được dẫn từ
- [[kill-criteria|Kill criteria, proof plan và baseline Excel + Zalo]]
- [[pilot-scope|Partner Pilot Proposal]]
- [[instantiate-visit|Check-in sinh việc]]
- [[tk-sensing|Sensing]]
