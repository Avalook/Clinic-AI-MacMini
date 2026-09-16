---
title: "Khoảng cách 1 — Envelope: 9/17 trường có chỗ, 0% correlation, actor chìm trong JSON, 62% nhiễu"
lop: 4
lop_ten: Khoảng cách
tag_nguon: "event_envelope ↔ event_log"
trang_thai: Một phần
tags: [clinicai, lop4-khoang-cach]
---

# Khoảng cách 1 — Envelope: 9/17 trường có chỗ, 0% correlation, actor chìm trong JSON, 62% nhiễu

> [!abstract] Bảng có hình đúng nhưng không ai điền; không có evidence_level nên không phân biệt được suy luận với quan sát.

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

Đóng bằng: [[tk-event-envelope-v2|Envelope v2]] (một migration cộng thêm, backfill được từ dữ liệu có sẵn), [[tk-event-catalog-table|event_catalog]] (đuổi `slot_hold` sang telemetry), [[tk-emit-function|ghi_su_kien()]] (một cửa ghi điền đủ).

## Nối tới
- [[event-envelope|Event envelope chuẩn]]
- [[event-log-table|event_log]]
- [[tk-event-envelope-v2|Envelope v2]]
- [[tk-event-catalog-table|event_catalog]]
- [[tk-emit-function|ghi_su_kien()]]

## Được dẫn từ
- [[ontology-9|Ontology]]
- [[10-principles|10 nguyên tắc sản phẩm]]
- [[5-loai-event|Năm loại event]]
- [[event-envelope|Event envelope chuẩn]]
- [[event-log-table|event_log]]
- [[tk-event-envelope-v2|Envelope v2]]
