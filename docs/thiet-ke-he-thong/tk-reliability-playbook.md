---
title: "Reliability playbook — seq + checkpoint, quarantine, DEAD, failure event vào ledger, replay có guard"
lop: 5
lop_ten: Thiết kế đích
tag_nguon: "migration 202609xx_reliability · scripts/phat-lai-su-kien.py"
tags: [clinicai, lop5-thiet-ke]
---

# Reliability playbook — seq + checkpoint, quarantine, DEAD, failure event vào ledger, replay có guard

> [!abstract] Trả lời §15.6 và §16 bằng ba bảng nhỏ và một quy tắc: side effect ngoài không bao giờ chạy trong replay.

### Ba bảng

- `consumer_checkpoint (consumer PK, last_seq, updated_at, clinic_id NULL = toàn hệ)` — ⚠ **chưa an toàn dưới dạng này**: đọc `event_log.seq > last_seq` bỏ sót event của transaction cấp seq sớm mà commit muộn (xem [[tk-event-envelope-v2|Envelope v2]]). Phải đổi sang xác nhận theo từng event và consumer idempotent trước khi thay cờ `event_published`. Ghi ở đây như *yêu cầu*, không phải thiết kế đã chốt.
- `event_quarantine (id, event_id, consumer, reason, attempts, first_at, last_at, resolved_at, resolved_by, resolution)` — consumer lỗi N lần trên một event → ghi vào đây, **checkpoint vẫn tiến** (không kẹt cả hàng vì một event hỏng), `ghi_su_kien('event.quarantined', reliability)`. «dead-letter item phải có owner và resolution event» (§15.6) → `resolved_by` bắt buộc khi đóng.
- `notification_delivery.DEAD` (xem [[tk-communication-delivery|notification_delivery]]).

### Failure event nghiệp vụ (stream `sys:<clinic>`, category `reliability`)

| Event | Ai phát | Khi |
|---|---|---|
| `notification.failed` | relay | delivery → DEAD |
| `integration.unavailable` / `.restored` | relay (Telegram 401/403), adapter POS, sau này LIS | lần lỗi đầu / lần thành công đầu sau lỗi |
| `projection.lag_exceeded` | đồng hồ | số event chưa được consumer xác nhận > 200, hoặc checkpoint cũ > 2′ (⚠ **không** dùng `max(seq) − last_seq`: sequence có khoảng trống) |
| `projection.drift` | đồng hồ (giờ) | `v_visit_state_tu_su_kien` ≠ `visit` |
| `automation.blocked_by_policy` | policy engine | authority không đủ, hoặc lab GROUP_C chặn |
| `event.validation_failed` | `ghi_su_kien` (RAISE) → caller ghi vào quarantine với payload | event_type lạ / schema sai |

`ops_status.collect()` đọc thêm: số `sys:` event 24h theo loại, DEAD/quarantine đang mở → `degraded` nếu > 0 chưa resolved. Kuma monitor `GET /health/features` (design v5 §5.6 đã đề xuất: «báo từng nhánh real|stub|disabled»).

### Replay có guard

`scripts/phat-lai-su-kien.py --consumer policy --from-seq N --dry-run` (⚠ phụ thuộc giao thức con trỏ đang bị chặn ở trên) : đặt `consumer_checkpoint` lùi lại **trong một transaction** với biến session `SET LOCAL clinicai.replay = on`; mọi action có side effect ngoài (`notify_queue` tạo delivery, adapter POS) kiểm `current_setting('clinicai.replay', true) = 'on'` → **không** tạo dòng delivery mới (chỉ ghi `policy.decided` với `payload.replay = true`). «replay không được lặp lại external side effect nếu không có guard» (§15.6). Ghi `ghi_su_kien('projection.rebuilt', …)` cuối. Quyền: MANAGEMENT + audit (§17).

### Ordering

`stream_version` cho đúng đắn trong stream; `occurred_at` cho reality. `seq` chỉ dùng để **sắp xếp khi đọc**, không dùng làm con trỏ tiêu thụ chừng nào giao thức xác nhận theo từng event chưa có và chưa có test commit đảo thứ tự (xem [[tk-event-envelope-v2|Envelope v2]]). Late event (ghi bù với `occurred_at` quá khứ): policy đọc `recorded_at` để biết là tin muộn và **không** tự đảo outcome đã đóng (Protocol §13) — chỉ ghi `experience.reevaluate` nếu cần.

### Kiểm

test consumer: event gây exception 3 lần → quarantine + checkpoint tiến; replay dry-run → 0 dòng `notification_delivery` mới; ops_status với 1 DEAD → `degraded`.

## Nối tới
- [[reliability|Reliability semantics]]
- [[gap-reliability|Khoảng cách 10]]
- [[gap-failure-domain|Khoảng cách 11]]
- [[failure-la-domain|Failure là một phần của domain]]
- [[tk-communication-delivery|notification_delivery]]
- [[tk-projections|Projection có kỷ luật]]
- [[tk-policy-engine|policy + policy_case]]
- [[pos-outbox|pos_outbox]]
- [[tk-event-envelope-v2|Envelope v2]]

## Được dẫn từ
- [[reliability|Reliability semantics]]
- [[failure-la-domain|Failure là một phần của domain]]
- [[notification-relay|notification_relay]]
- [[pos-outbox|pos_outbox]]
- [[gap-reliability|Khoảng cách 10]]
- [[gap-failure-domain|Khoảng cách 11]]
- [[gap-atc|Khoảng cách 12]]
- [[tk-policy-engine|policy + policy_case]]
- [[tk-communication-delivery|notification_delivery]]
- [[tk-projections|Projection có kỷ luật]]
- [[tk-atc-ui|Giao diện]]
- [[tk-governance|Governance ở cấp event]]
- [[phase-b-exceptions|Phase B]]
- [[chung-minh-event-driven|12 bằng chứng 'event-driven thật']]
