---
title: "audit_labels.EVENT_LABELS — danh mục event de-facto (~80 tên) với nhãn tiếng Việt"
lop: 3
lop_ten: Code đang chạy
tag_nguon: "src/clinicai/services/audit_labels.py"
trang_thai: Đã có
tags: [clinicai, lop3-code]
---

# audit_labels.EVENT_LABELS — danh mục event de-facto (~80 tên) với nhãn tiếng Việt

> [!abstract] Đã có 'event catalog' dưới dạng dict Python + drift test; thiếu payload schema, category, privacy.

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

[[tk-event-catalog-table|event_catalog]] đưa dict này vào bảng `event_catalog` (seed từ chính `EVENT_LABELS`), giữ drift test hai chiều (dict ↔ bảng).

## Nối tới
- [[event-catalog|Event Catalog v1]]
- [[event-log-table|event_log]]
- [[tk-event-catalog-table|event_catalog]]
- [[5-loai-event|Năm loại event]]

## Được dẫn từ
- [[governance-event|Security, privacy, governance ở cấp event]]
- [[event-catalog|Event Catalog v1]]
- [[event-log-table|event_log]]
- [[tk-event-catalog-table|event_catalog]]
