---
title: "Khoảng cách 15 — Wedge: thesis nói in-visit, người dùng thật là CSKH trước buổi khám"
lop: 4
lop_ten: Khoảng cách
tag_nguon: "wedge ↔ số liệu prod"
trang_thai: Một phần
tags: [clinicai, lop4-khoang-cach]
---

# Khoảng cách 15 — Wedge: thesis nói in-visit, người dùng thật là CSKH trước buổi khám

> [!abstract] Không phải lỗi kỹ thuật — là quyết định sản phẩm chưa được nói thành lời; thiết kế đích trung lập với cả hai đường.

Số đo prod 04–05/09 *(chưa xác minh lại ở vòng đính chính này)*: 65 lịch thật / 66 hồ sơ, **5 tài khoản CSKH** đặt 100%; 0 lịch kênh walk-in tại thời điểm đo (ảnh chụp bảng lịch hẹn, không phải lịch sử thực thi); 1 lượt khám qua kernel; `visit_route` 0; `visit_gate_rule` 0; `lab_result` 0; `payment` 0.

Bốn thứ khác nhau, trước đây tôi gộp làm một và kết luận quá tay:

| | Đo/đọc được gì | Kết luận cho phép rút |
|---|---|---|
| **Ai tạo lịch** | 5 tài khoản CSKH, 100% | Đường vào của lịch hẹn là CSKH, không có khách tự đặt |
| **Code hỗ trợ chặng nào** | `tuong_tac_cskh` phủ cả trong buổi khám (`CHECK_IN`, `CHECK_OUT`, `THANH_TOAN`, `MUA_THUOC` — `tuong_tac_cskh_service.py:62`) và sau khám (`TRA_KQ`, `:71`) | **Không** kết luận được là code chỉ phục vụ trước buổi khám |
| **Mức dùng thật từng chặng** | 16 dòng `tuong_tac_cskh` tổng, **chưa tách theo `loai`** | Chưa đủ dữ liệu để nói chặng nào tạo giá trị |
| **Chọn wedge** | quyết định sản phẩm | Của Quang, không phải suy ra từ số đo |

Nên câu cũ «toàn bộ giá trị nằm ở chặng 1» bị rút. Phép đo còn thiếu để nói được điều gì đó chắc chắn: `tuong_tac_cskh` tách theo `loai` (biết CSKH đang chạm chặng nào), và đối soát check-in theo từng cặp `(clinic_id, appointment_id)` có xét hoàn tác. *Chưa chạy.*

Thesis v1 §11.2 chọn wedge in-visit vì «dữ liệu có tần suất cao, ROI có thể đo». Pilot §4.2 cũng chọn journey in-visit. Nhưng thesis v2 §3.5 cũng nói: «Wedge ban đầu phải tạo giá trị ngay cả khi dữ liệu và kỷ luật vận hành chưa hoàn hảo: giúp CSKH nhập hoặc cập nhật nhanh hơn; […] giảm việc nhân viên phải nhớ» — chính là thứ code đang làm.

TAM-NHIN: «CSKH là bãi thử lv4 tự nhiên» và «Trước mắt cứ làm việc mình nghĩ là có ích đã».

Hai đường không loại trừ nhau về **kiến trúc**: Work Item Protocol, expectation timer, policy engine, communication delivery dùng được cho việc CSKH (gọi xác nhận, nhắc hẹn, trả kết quả) y hệt cho việc in-visit (sinh hiệu, siêu âm, review). Chỉ khác *node nào sinh việc* và *ai là owner*.

Điều phải quyết (không phải kỹ thuật): pilot đo cái gì trước — «unexplained waiting minutes» (in-visit) hay «open commitments không owner» + «manual status-check contacts» (CSKH)? Pilot §13.3 liệt cả hai. Đề xuất của tôi trong [[cau-hoi-mo|Câu hỏi mở]]: Phase A áp Work Item Protocol lên **việc CSKH đang có dữ liệu** (33 `nhac_tai_kham`, 16 `tuong_tac`), Phase B mới mở in-visit khi Trưởng ca dùng thật — vì đo được ngay trên người dùng đang có.

## Nối tới
- [[wedge|Wedge]]
- [[cau-hoi-mo|Câu hỏi mở]]
- [[tk-work-item-protocol|Work Item Protocol trên kernel]]
- [[phase-a-closed-loop|Phase A]]
- [[workflow-kernel|Workflow kernel]]
- [[pilot-scope|Partner Pilot Proposal]]

## Được dẫn từ
- [[6-lop-san-pham|Product map 6 lớp]]
- [[wedge|Wedge]]
- [[workflow-kernel|Workflow kernel]]
- [[lo-trinh-tong|Lộ trình]]
- [[phase-a-closed-loop|Phase A]]
- [[cau-hoi-mo|Câu hỏi mở]]
