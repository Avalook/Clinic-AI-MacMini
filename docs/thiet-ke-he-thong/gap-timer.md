---
title: "Khoảng cách 4 — Không bộ hẹn giờ: 'sự kiện không xảy ra' là vô hình"
lop: 4
lop_ten: Khoảng cách
tag_nguon: "timer-expected-event ↔ (không có gì)"
trang_thai: Chưa có
tags: [clinicai, lop4-khoang-cach]
---

# Khoảng cách 4 — Không bộ hẹn giờ: 'sự kiện không xảy ra' là vô hình

> [!abstract] Mọi 'quá hạn' là thuộc tính lúc đọc; không ai mở màn = không ai biết; việc sau khám sinh khi CSKH mở trang.

Code tự khai ở hai chỗ: `recall_job_service.py` («Dự án chưa có bộ hẹn giờ nào (đã tìm: không apscheduler, không croniter, không repeat_every)») và `20260809000005` («Dự án không có bộ hẹn giờ»).

Hậu quả cụ thể:
- `v_viec_cskh.qua_han` = `han < hôm nay` **lúc SELECT**. Không có thời điểm "phát hiện quá hạn", không có ai được giao khi quá hạn.
- `build_alerts()` `wait_too_long` sống trong response HTTP của `/truong-ca/canh-bao`. Đóng tab = cảnh báo biến mất; không ack; không đo «thời gian từ phát hiện đến can thiệp» (Spec §14).
- `nhac_tai_kham` sinh lúc `danh_sach(sinh_truoc=True)` — CSKH nghỉ một ngày, việc lượt 1 sinh trễ một ngày.
- `slot_hold` hết hạn 10 phút: giải phóng lúc có người khác đặt (`release_on_booking`) hoặc view `v_slot_hold_active` lọc — đúng cho giữ chỗ, nhưng là cùng một mẫu "hết hạn lúc đọc".
- Không có `AcknowledgementTimeoutOccurred` vì không có acknowledge; không `ExpectedEventDeadlineReached` vì không có expectation.

Thesis §11: «Sự vắng mặt tự nó không phải event. ClinicAI cần timer/scheduler tạo ra một sự kiện quan sát được.» Và v1 §10 Level 4 phản xạ số 6: «MissingExpectedEvent → hệ thống chủ động hỏi hoặc escalation thay vì giả định mọi thứ bình thường.»

Vì sao chưa làm: SO-LUAT 7.2 đúng — đừng thêm hạ tầng. Nhưng câu trả lời không phải cron/Celery/pg_cron: **`worker.py --relay` đã là một tiến trình sống 24/7 có poll 30s + LISTEN + heartbeat**. Thêm một vòng "đồng hồ" đọc bảng `expectation` vào đó là 0 hạ tầng mới. [[tk-expectation-timer|expectation + đồng hồ]].

## Nối tới
- [[timer-expected-event|Thời gian và 'sự kiện không xảy ra']]
- [[tk-expectation-timer|expectation + đồng hồ]]
- [[cskh-views|v_viec_cskh · v_trang_thai_cskh · luat_cskh]]
- [[nhac-tai-kham|nhac_tai_kham + hen_goi_lai + follow_up_case]]
- [[dispatch|Điều phối Trưởng ca]]
- [[notification-relay|notification_relay]]

## Được dẫn từ
- [[vong-lap|Vòng lặp Reality → Event → State → Interpretation → Decision → Action]]
- [[timer-expected-event|Thời gian và 'sự kiện không xảy ra']]
- [[kien-truc-toi-thieu|Kiến trúc logic tối thiểu]]
- [[dispatch|Điều phối Trưởng ca]]
- [[cskh-views|v_viec_cskh · v_trang_thai_cskh · luat_cskh]]
- [[nhac-tai-kham|nhac_tai_kham + hen_goi_lai + follow_up_case]]
- [[gap-experience-state|Khoảng cách 5]]
- [[tk-expectation-timer|expectation + đồng hồ]]
