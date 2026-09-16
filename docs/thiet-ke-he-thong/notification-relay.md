---
title: "notification_relay — outbox poll 30s + LISTEN, advisory lock, làm giàu lúc gửi, 5 template Telegram"
lop: 3
lop_ten: Code đang chạy
tag_nguon: "services/notification_relay.py · worker.py · notification_templates.py"
trang_thai: Một phần
tags: [clinicai, lop3-code]
---

# notification_relay — outbox poll 30s + LISTEN, advisory lock, làm giàu lúc gửi, 5 template Telegram

> [!abstract] Consumer duy nhất của event_log; đúng ở idempotency và data minimization; sai ở 'sent = done' và 'không template = xong'.

Vòng lặp (`worker.py --relay`): bật chỉ khi `NOTIFICATION_RELAY_ENABLED=true` («MVP 15/08: mọi tin nhắn do người bấm gửi, không tự động. Muốn bật lại thì dọn event_log tồn đọng trước» — vì trước đó «208 dòng event_log chưa publish còn tồn»); `TELEGRAM_CLINIC_ID` bắt buộc («refusing a cross-tenant relay»); LISTEN `clinicai_changes` + poll 30s làm lưới; heartbeat file cho healthcheck; bot lệnh `/trangthai /homnay` cùng tiến trình. Prod: container `notification-relay` Up 13 ngày, 449/449 event đã publish.

`poll_and_deliver()`: SELECT 50 event `event_published = FALSE` theo `occurred_at` → mỗi event `pg_try_advisory_lock(hashtextextended(event_id))` (hai relay không gửi trùng) → recheck `still_unpublished` → `_lam_giau()` («`event_log.payload` cố ý chỉ mang ID […] Tra database NGAY LÚC GỬI thay vì lúc ghi: tin kể trạng thái mới nhất») → `render()` → 3 lần thử, backoff 0.5s/1s («BA LẦN THỬ LIÊN TIẾP KHÔNG NGHỈ LÀ MỘT LẦN THỬ») → `_mark_published`.

Template: `appointment.created` · `.cancelled` · `.rescheduled` · `.doctor_removed` · `roster.shift_added_cho_xep`. «KHÔNG BAO GIỜ đưa số điện thoại / CCCD / địa chỉ vào tin: Telegram là máy chủ bên thứ ba.» Người nhận là **nhóm vận hành**, không phải khách («Bản đầu soạn tin cho KHÁCH […] đổ vào nhóm nội bộ thì ai đọc cũng thấy sai vai»).

### Ba chỗ lệch thesis

1. **Sent = done** (§20.9), và còn nhẹ hơn thế: `_mark_published` chạy cả khi **không gửi gì** (không có template, `:205-214`) lẫn khi nhà cung cấp trả ok (`:238`). Không MessageDeliveryConfirmed, không ai đọc.
2. **Không template → đánh dấu xong**: «relay đánh dấu đã-xử-lý và đi tiếp (render trả None) — im lặng có chủ ý». Với 281 `slot_hold` thì đúng là nên bỏ; nhưng cơ chế này cũng nuốt mọi event tương lai không có mẫu — thesis §15.6 đòi quarantine.
3. **Một cờ, mọi consumer**: `event_published` là "đã gửi Telegram". Consumer thứ hai (policy engine) không dùng chung cờ này được — `pos_outbox` đã phải tách vì thế. Thiết kế [[tk-communication-delivery|notification_delivery]]: `notification_delivery` per channel (đúng ADR-0002), relay đọc bảng đó; `event_log.event_published` **ngừng mang nghĩa**, thay bằng `consumer_cursor` per consumer.

Mẫu tốt giữ nguyên: advisory lock + recheck; làm giàu lúc gửi; không PII; heartbeat; cờ bật tường minh.

## Nối tới
- [[reliability|Reliability semantics]]
- [[bat-dang-thuc|Sáu bất đẳng thức]]
- [[anti-patterns|10 anti-pattern cần cấm]]
- [[gap-communication|Khoảng cách 8]]
- [[tk-communication-delivery|notification_delivery]]
- [[tk-reliability-playbook|Reliability playbook]]
- [[pos-outbox|pos_outbox]]
- [[event-log-table|event_log]]

## Được dẫn từ
- [[event-first-dao-nhan-qua|Event-first]]
- [[bat-dang-thuc|Sáu bất đẳng thức]]
- [[timer-expected-event|Thời gian và 'sự kiện không xảy ra']]
- [[reliability|Reliability semantics]]
- [[failure-la-domain|Failure là một phần của domain]]
- [[stack|Stack đang chạy]]
- [[event-log-table|event_log]]
- [[realtime-sse|LISTEN/NOTIFY → ChangeBroker → SSE]]
- [[pos-outbox|pos_outbox]]
- [[gap-timer|Khoảng cách 4]]
- [[gap-communication|Khoảng cách 8]]
- [[gap-reliability|Khoảng cách 10]]
- [[gap-failure-domain|Khoảng cách 11]]
- [[tk-expectation-timer|expectation + đồng hồ]]
- [[tk-communication-delivery|notification_delivery]]
