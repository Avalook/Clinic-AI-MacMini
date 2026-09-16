---
title: "pos_outbox — outbox riêng có attempts/backoff/DEAD, vì 'một cờ không phục vụ được hai consumer'"
lop: 3
lop_ten: Code đang chạy
tag_nguon: "20260730000007 · ADR-0010 · services/pos_relay.py"
trang_thai: Đã có
tags: [clinicai, lop3-code]
---

# pos_outbox — outbox riêng có attempts/backoff/DEAD, vì 'một cờ không phục vụ được hai consumer'

> [!abstract] Mẫu outbox đúng nhất trong repo, đang chạy với NullPosAdapter; dead-letter là kết cục trung thực.

> «WHY A SEPARATE TABLE, rather than reusing event_log: `event_published` is a single boolean shared by every consumer. The notification relay already claims events by flipping it, so a second relay reading the same flag would steal notifications and have its own deliveries marked done by the notifier. One flag cannot serve two consumers.» — *migration header*

Cột: `kind (invoice/invoice_void/stock_movement) · subject_id · payload · status PENDING/SENT/DEAD · attempts · max_attempts 5 · next_attempt_at · last_error · external_ref · sent_at`; `UNIQUE (clinic_id, kind, subject_id)` («enqueueing twice for the same subject is a no-op rather than a double invoice»); index `WHERE status='PENDING'` cho câu duy nhất của relay.

Ghi **trong cùng transaction với payment** (ADR-0010: «payment commit thì push chắc chắn đã vào hàng đợi; payment rollback thì không có gì trong hàng đợi»). Relay: claim từng dòng bằng advisory lock, backoff 1′→5′→25′→125′, hết `max_attempts` → **DEAD** («Dead-letter là kết cục trung thực: tiền đã thu, POS chưa biết, phải có người nhìn. Im lặng hoặc retry vô hạn đều giấu chuyện đó đi»). `KiotVietAdapter` cố ý chưa hiện thực HTTP → `PosDeliveryError(retryable=False)` → DEAD ngay.

Ranh giới có test: `test_pos_port.py::TestBoundary` — `services/` không import `adapters/`; `payment_service` không biết chữ "kiotviet".

### Vì sao nút này ở đây

Đây là **§15.5 outbox/inbox + §15.6 dead-letter** làm đúng. Thiết kế [[tk-communication-delivery|notification_delivery]] và [[tk-reliability-playbook|Reliability playbook]] không phát minh gì: chúng **nhân bản khuôn `pos_outbox`** cho notification (`notification_delivery`) và cho policy side-effects — cùng cột attempts/next_attempt_at/DEAD, cùng cách claim. Và câu «Generalising event_log to per-consumer delivery tracking is worth doing when a third consumer appears» — consumer thứ ba (policy engine) chính là lúc đó.

## Nối tới
- [[reliability|Reliability semantics]]
- [[notification-relay|notification_relay]]
- [[tk-communication-delivery|notification_delivery]]
- [[tk-reliability-playbook|Reliability playbook]]
- [[10-principles|10 nguyên tắc sản phẩm]]

## Được dẫn từ
- [[10-principles|10 nguyên tắc sản phẩm]]
- [[reliability|Reliability semantics]]
- [[notification-relay|notification_relay]]
- [[gap-reliability|Khoảng cách 10]]
- [[tk-communication-delivery|notification_delivery]]
- [[tk-reliability-playbook|Reliability playbook]]
