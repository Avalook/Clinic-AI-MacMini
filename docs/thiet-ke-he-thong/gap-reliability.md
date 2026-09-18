---
title: "Khoảng cách 10 — Reliability: một cờ cho mọi consumer, không quarantine, không replay, không checkpoint"
lop: 4
lop_ten: Khoảng cách
tag_nguon: "reliability ↔ event_published / pos_outbox"
trang_thai: Một phần
tags: [clinicai, lop4-khoang-cach]
---

# Khoảng cách 10 — Reliability: một cờ cho mọi consumer, không quarantine, không replay, không checkpoint

> [!abstract] ADR-0002 (07/2026) đã chẩn đúng và kê đơn notification_delivery; đơn chưa lấy.

Từ [[reliability|Reliability semantics]]: 3/6 đạt (idempotency ✓, optimistic concurrency ✓, correction ✓), 1 nửa (outbox), 2 chưa (ordering, replay/quarantine).

Cụ thể chưa:
- `event_log.event_published` gộp «đã lên hàng chờ» + «đã gửi Telegram» (ADR-0002 §Context). Consumer thứ hai không dùng được → mỗi consumer mới lại đẻ một bảng outbox riêng như `pos_outbox` — hoặc, tệ hơn, dùng chung cờ và ăn trộm event của nhau.
- Không `consumer_checkpoint`: nếu policy engine ra đời, nó đọc từ đâu, đã xử lý đến event nào?
- Event không template → đánh dấu xong (không quarantine). Event lỗi validate → không có chỗ nằm.
- Relay lỗi vĩnh viễn (ví dụ token revoke như 01/09) → mỗi 30s thử lại 3 lần mãi mãi, log đầy, không DEAD, không ai được báo — trái với `pos_outbox` có DEAD.
- Không có công cụ replay có kiểm soát; replay thủ công = bật `event_published=FALSE` → bắn lại Telegram (side effect lặp — §15.6 cấm).
- Ordering: relay `ORDER BY occurred_at` toàn clinic; event cùng giây không có thứ tự ổn định; không stream_version.

Đóng bằng: [[tk-reliability-playbook|Reliability playbook]] — một giao thức tiêu thụ có xác nhận **theo từng event** (con trỏ `seq > last_seq` đơn thuần đã bị đánh dấu chưa an toàn, xem [[tk-event-envelope-v2|Envelope v2]]); `event_quarantine`; DEAD cho notification; replay tool có guard `dry_run`/`no_side_effects`; và [[tk-communication-delivery|notification_delivery]].

## Nối tới
- [[reliability|Reliability semantics]]
- [[notification-relay|notification_relay]]
- [[pos-outbox|pos_outbox]]
- [[tk-reliability-playbook|Reliability playbook]]
- [[tk-communication-delivery|notification_delivery]]
- [[tk-event-envelope-v2|Envelope v2]]

## Được dẫn từ
- [[reliability|Reliability semantics]]
- [[tk-communication-delivery|notification_delivery]]
- [[tk-reliability-playbook|Reliability playbook]]
