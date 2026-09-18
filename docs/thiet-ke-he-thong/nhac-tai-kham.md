---
title: "nhac_tai_kham + hen_goi_lai + follow_up_case — 'việc' sau khám, sinh lúc mở màn vì không có cron"
lop: 3
lop_ten: Code đang chạy
tag_nguon: "services/recall_job_service.py (338 dòng) · recall_service.py"
trang_thai: Một phần
tags: [clinicai, lop3-code]
---

# nhac_tai_kham + hen_goi_lai + follow_up_case — 'việc' sau khám, sinh lúc mở màn vì không có cron

> [!abstract] Episode/post-visit stream sơ khai: hai lượt gọi, người phụ trách, hạn; follow_up_case có bảng nhưng không ai ghi.

> «`RecallService` bên cạnh trả về một PHÉP CHIẾU: mỗi lần CSKH mở trang, nó tính lại từ đầu xem ai đến hạn tái khám. Không có dòng nào trong database, nên: không ai mở trang thì không ai biết có người cần gọi; không giao được cho một người cụ thể; trưởng ca không đối soát được cuối ngày […]. File này biến nó thành VIỆC: `nhac_tai_kham`, mỗi dòng một cuộc gọi phải làm.» — *docstring*

Hai lượt là hai việc: lượt 1 «bác sĩ dặn quay lại ngày X, khách CHƯA đặt lịch — gọi trước 5–7 ngày để MỜI ĐẶT LỊCH»; lượt 2 «khách ĐÃ có lịch hẹn hôm nay — gọi buổi sáng để NHẮC ĐI KHÁM». Hàm SQL `sinh_viec_nhac_tai_kham(clinic, ngay)` idempotent; gọi từ `danh_sach(sinh_truoc=True)` — «đường chắc chắn nhất hôm nay là sinh ngay lúc CSKH mở màn […] cắm thêm cron vào ngày mai không phải đổi gì». Prod: **33 dòng**. Kết quả 4 giá trị (DA_LIEN_HE/CHUA_NGHE_MAY/CAN_BAC_SI/TU_CHOI), `nguoi_goi_staff_id`, `han_goi`, `qua_han` tính lúc đọc.

`hen_goi_lai`: việc CSKH tự hẹn («Chỗ đựng những việc hệ thống CHƯA suy được»), CHECK `(dong_luc IS NULL) = (dong_boi_staff_id IS NULL)` — «Đóng việc mà không biết ai đóng thì không truy lại được».

`follow_up_case` (kernel): «Non-blocking work that was still open when the visit closed […] such work has a named owner and a date, instead of being quietly dropped on the floor.» — **0 dòng, không có writer** (`checkout_service` không ghi).

### Đối chiếu thesis

Episode Stream (§6.3: follow-up expected · patient contacted · appointment booked) có một nửa. Điều thesis đòi mà thiếu: (a) việc sinh ra do **timer** (FollowupWindowOpened) chứ không do ai mở màn ([[gap-timer|Khoảng cách 4]]); (b) `PatientLeftFacility + open commitment → ContinuityRisk → follow-up work có owner` (Spec §7.3) — hiện checkout đóng lượt và cam kết mở *biến mất*, đúng thứ `follow_up_case` sinh ra để chống. [[tk-expectation-timer|expectation + đồng hồ]] thay «sinh lúc mở màn» bằng đồng hồ; [[tk-experience-state|experience_state]] policy ContinuityRisk là writer đầu tiên của `follow_up_case`.

## Nối tới
- [[timer-expected-event|Thời gian và 'sự kiện không xảy ra']]
- [[gap-timer|Khoảng cách 4]]
- [[tk-expectation-timer|expectation + đồng hồ]]
- [[tk-experience-state|experience_state]]
- [[cskh-views|v_viec_cskh · v_trang_thai_cskh · luat_cskh]]
- [[stream-boundary|Năm stream]]

## Được dẫn từ
- [[timer-expected-event|Thời gian và 'sự kiện không xảy ra']]
- [[cskh-views|v_viec_cskh · v_trang_thai_cskh · luat_cskh]]
- [[gap-timer|Khoảng cách 4]]
- [[gap-process-manager|Khoảng cách 7]]
- [[tk-work-item-protocol|Work Item Protocol trên kernel]]
- [[tk-expectation-timer|expectation + đồng hồ]]
- [[phase-a-closed-loop|Phase A]]
