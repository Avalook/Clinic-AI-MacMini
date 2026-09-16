---
title: "Thời gian và 'sự kiện không xảy ra' — timer tạo ra sự kiện quan sát được"
lop: 2
lop_ten: Kiến trúc hướng sự kiện
tag_nguon: "Care Model §11 · Catalog §11 · Work Item §7"
tags: [clinicai, lop2-kien-truc]
---

# Thời gian và 'sự kiện không xảy ra' — timer tạo ra sự kiện quan sát được

> [!abstract] Sự vắng mặt không phải event; scheduler phải phát ExpectedEventDeadlineReached; timer huỷ được và idempotent.

> «Một phần quan trọng của vận hành y tế là phát hiện điều đáng lẽ xảy ra nhưng chưa xảy ra. Sự vắng mặt tự nó không phải event. ClinicAI cần timer/scheduler tạo ra một sự kiện quan sát được.» — *§11*

Event thời gian: ExpectedEventDeadlineReached · AcknowledgementTimeoutOccurred · WaitingThresholdExceeded · FollowupWindowOpened · MissingExpectedEventDetected.

Chuỗi mẫu (*§11*): «(1) LabOrderPlaced tạo expectation: cần LabResultReady trước 11:00; (2) timer được đăng ký; (3) 11:00 chưa có result; (4) hệ thống phát ExpectedEventDeadlineReached; (5) policy kiểm tra lại stream; (6) nếu vẫn thiếu, phát LabResultDelayDetected; (7) tạo Work Item điều tra và communication task.»

> «Timer phải có thể hủy khi outcome đến sớm, và phải idempotent nếu bị kích hoạt lại.» — *§11*

Catalog §11 tách hai bước: `ExpectedEventDeadlineReached` («Timer đến hạn — chưa kết luận outcome bị thiếu») và `MissingExpectedEventDetected` («Recheck xác nhận outcome vẫn chưa có — Derived fact»). Work Item §7: bốn mốc `claim_by · acknowledge_by · start_by · complete_by`; «Timer phát event, không trực tiếp sửa status.»

### Code: không có bộ hẹn giờ — và tự khai điều đó ở hai chỗ

`recall_job_service.py` docstring: «Dự án chưa có bộ hẹn giờ nào (đã tìm: không apscheduler, không croniter, không repeat_every). Nên đường chắc chắn nhất hôm nay là sinh ngay lúc CSKH mở màn — `danh_sach()` gọi `sinh()` trước khi đọc.» Migration `20260809000005` chọn VIEW cũng vì «Dự án không có bộ hẹn giờ».

Hệ quả: mọi "quá hạn" hôm nay là **thuộc tính lúc đọc** (`qua_han` trong view, `wait_minutes > threshold` trong `build_alerts`). Không ai mở màn = không ai biết. Không có event = không có owner, không có ack, không có thời điểm phát hiện để đo.

Nhưng **hạ tầng để làm timer đã có sẵn**: `worker.py --relay` là một tiến trình sống 24/7 với vòng poll 30s + LISTEN. Thiết kế [[tk-expectation-timer|expectation + đồng hồ]] thêm bảng `expectation` và một vòng "đồng hồ" **trong cùng tiến trình đó** — 0 hạ tầng mới, đúng Luật 7.1 và ADR-0005.

## Nối tới
- [[gap-timer|Khoảng cách 4]]
- [[tk-expectation-timer|expectation + đồng hồ]]
- [[work-item-commitment|Work Item là commitment]]
- [[nhac-tai-kham|nhac_tai_kham + hen_goi_lai + follow_up_case]]
- [[notification-relay|notification_relay]]

## Được dẫn từ
- [[journey-process-manager|Patient Journey là Process Manager]]
- [[policy-engine|Policy Engine]]
- [[experience-state|Experience State]]
- [[work-item-commitment|Work Item là commitment]]
- [[nhac-tai-kham|nhac_tai_kham + hen_goi_lai + follow_up_case]]
- [[gap-timer|Khoảng cách 4]]
- [[tk-expectation-timer|expectation + đồng hồ]]
