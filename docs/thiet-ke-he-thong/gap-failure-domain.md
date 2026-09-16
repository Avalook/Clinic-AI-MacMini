---
title: "Khoảng cách 11 — Failure không phải event: relay hỏng chỉ có log, SSE rớt màn hình im lặng"
lop: 4
lop_ten: Khoảng cách
tag_nguon: "failure-la-domain ↔ ops_status / relay"
trang_thai: Chưa có
tags: [clinicai, lop4-khoang-cach]
---

# Khoảng cách 11 — Failure không phải event: relay hỏng chỉ có log, SSE rớt màn hình im lặng

> [!abstract] Có health view hạ tầng; không có failure event nghiệp vụ; card không có data freshness.

Có: `ops_status.py` (DB probe + snapshot host + `unknown` state), heartbeat worker cho compose healthcheck, Uptime Kuma 4 monitor + sao lưu đêm, Dozzle. Đây là quan sát **hạ tầng** tốt cho 1 người vận hành.

Không có ở tầng **nghiệp vụ**:
- `NotificationDeliveryFailed` — relay `logger.error("relay_delivery_failed")` rồi thôi.
- `ProjectionLagThresholdExceeded` — không có projector nên không có lag, nhưng SSE rớt = màn hình cũ 60s mà không ai biết.
- `IntegrationUnavailable` — chưa có integration, nhưng Telegram token revoke 01/09 chính là IntegrationUnavailable và không ai được báo trong app (chỉ khi mở Kuma).
- `AutomationBlockedByPolicy` — lab hard-block ghi `escalation_note` nhưng không event.
- `data_freshness` trên card ATC (§19.1) — không có; `_OVERVIEW_SQL` tính `wait_minutes` từ `now()` nên luôn "tươi" kể cả khi dữ liệu nguồn không được cập nhật (bệnh nhân đã đi mà không ai bấm move).

Thesis §16: «ClinicAI không chỉ hiển thị state. ClinicAI phải hiển thị khi nó không còn đủ bằng chứng để tin state đó.» Tổng-Quan §14.6 gọi mất internet là «lỗ hổng kiến trúc lớn nhất» — và freshness chính là cách nói ra điều đó trên màn hình thay vì im lặng.

Đóng bằng: [[tk-reliability-playbook|Reliability playbook]] — 4 failure event vào `event_log` stream `sys:<clinic>`; `ops_status` đọc thêm từ đó; card ATC có `last_event_at` + `freshness` = `now() − last_event_at` của stream ([[tk-atc-ui|Giao diện]]).

## Nối tới
- [[failure-la-domain|Failure là một phần của domain]]
- [[notification-relay|notification_relay]]
- [[realtime-sse|LISTEN/NOTIFY → ChangeBroker → SSE]]
- [[tk-reliability-playbook|Reliability playbook]]
- [[tk-atc-ui|Giao diện]]

## Được dẫn từ
- [[10-principles|10 nguyên tắc sản phẩm]]
- [[failure-la-domain|Failure là một phần của domain]]
- [[15-invariant|15 bất biến cấp 'hiến pháp']]
- [[tk-reliability-playbook|Reliability playbook]]
