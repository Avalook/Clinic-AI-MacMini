---
title: "thong_bao — Trưởng ca gọi bộ phận: chống bấm hai lần ở DB, đọc ≠ đã xử lý, đo giây phản hồi"
lop: 3
lop_ten: Code đang chạy
tag_nguon: "services/thong_bao_service.py · 20260807000006"
trang_thai: Đã có
tags: [clinicai, lop3-code]
---

# thong_bao — Trưởng ca gọi bộ phận: chống bấm hai lần ở DB, đọc ≠ đã xử lý, đo giây phản hồi

> [!abstract] Mảnh 'ownership + ack + đo thời gian' duy nhất đang chạy — nhưng là notification nội bộ, không nối với work item hay escalation.

> «Màn cảnh báo của Trưởng ca đã nói được "phòng SA1 đang tắc, bốn người chờ, lâu nhất 38 phút". Nó KHÔNG nói được với ai. Không nút gọi, không endpoint, không bảng thông báo, không đường giao hàng.» — *docstring*

Ba tính chất bắt buộc (docstring): (1) «Gọi hai lần không thành hai thông báo» — unique index từng phần `uq_thong_bao_dang_mo (clinic, nguon, nguon_id, vai_nhan) WHERE da_xu_ly_luc IS NULL`, «không phải bằng nút disabled ở trình duyệt — trình duyệt thì mở hai tab là hỏng»; (2) «Có đường ĐÓNG» — `da_xu_ly()` trả `giay_phan_hoi`; (3) «Người gọi biết chuyện gì xảy ra» — bấm trùng trả `da_goi_tu_truoc: true` («KHÔNG phải lỗi, nhưng cũng KHÔNG phải "đã gửi"»).

Bốn nguồn (`NGUON`): `dispatch_alert` → `dispatch.alert_called` · `bac_si_da_xep` → `thong_bao.bac_si_da_xep` · `tuan_lich_truc` · `hen_goi_lai`. Mỗi nguồn = một event_type + một đường ghi. Nhận theo **vai** (`vai_nhan`) hoặc đích danh (`nguoi_nhan_staff_id`). `da_doc_luc` ≠ `da_xu_ly_luc`: «Nút "Đánh dấu đã đọc" phải tắt được chấm đỏ mà KHÔNG đóng việc — đóng việc hộ ở đây là làm mất một hàng đợi thật chỉ vì ai đó mở cái chuông ra xem.»

### Đối chiếu thesis

`thong_bao` là **Work Item mỏng** cho *role queue* (Protocol §5: «Bất kỳ người đủ vai trò có thể nhận — phải có cơ chế claim và queue owner»): có subject (`nguon_id`), owner-queue (`vai_nhan`), completion (`da_xu_ly`), audit, idempotency ở DB. Thiếu: acknowledge tách khỏi complete (đọc ≈ ack? — thesis bảo không: «Không tự động chuyển Active chỉ vì người dùng mở màn hình»), deadline/SLA, escalation, và không liên kết `work_item`. Và `dispatch.alert_called` là *Command* (Care Model §4) đội lốt event.

Thiết kế [[tk-work-item-protocol|Work Item Protocol trên kernel]]: `thong_bao` **không xoá**; nó trở thành một *assignment strategy* (Role queue) của work item — dòng `thong_bao` mang `work_item_id`, `da_xu_ly` = `complete` của work item đó. Giữ được màn chuông, thêm được SLA.

## Nối tới
- [[work-item-commitment|Work Item là commitment]]
- [[bat-dang-thuc|Sáu bất đẳng thức]]
- [[tk-work-item-protocol|Work Item Protocol trên kernel]]
- [[dispatch|Điều phối Trưởng ca]]
- [[metrics-thesis|Bốn nhóm chỉ số]]

## Được dẫn từ
- [[bat-dang-thuc|Sáu bất đẳng thức]]
- [[gap-work-item|Khoảng cách 3]]
- [[gap-communication|Khoảng cách 8]]
- [[gap-atc|Khoảng cách 12]]
- [[tk-work-item-protocol|Work Item Protocol trên kernel]]
