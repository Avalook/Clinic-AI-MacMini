# ADR-0002 — Outbox polling relay là đường async duy nhất; xoá skeleton RabbitMQ; tách bảng notification_delivery

| | |
|---|---|
| **Status** | Proposed |
| **Date** | 2026-07-18 |
| **Deciders** | Quang |
| **Liên quan** | Design doc v5 §5.5–5.6 |
| **Affected decisions (canon 06)** | Supersedes: FAD-4 + phần RabbitMQ của D014 (event bus). Supersede CÓ RÀO + TẠM THỜI: A-15 ("Zalo only, cấm Telegram fallback") — Telegram được dùng làm kênh **staff nội bộ tạm** vì đã chạy thật còn Zalo OA Internal chưa build; BN tuyệt đối chỉ Zalo OA (nửa BN của D010 giữ nguyên); Telegram nghỉ khi Zalo OA Internal live (đợt 4) |

## Context
Đường RabbitMQ hiện chết end-to-end: `RabbitMQPublisher` raise NotImplementedError,
queue `clinicai.events` không bind vào exchange, handler chỉ log — cần 3 mảnh sửa để nó
làm được *bất kỳ điều gì*, và thêm ~150MB + 1 SPOF. Trong khi đó relay poll outbox
(`event_log`, partial index unpublished, 30s) + Telegram đã chạy và đủ cho mọi nhu cầu
notify/audit ở 50–80 BN/ngày. Nhưng cờ `event_published` đang bị **2 nghĩa**: EventService
coi là "đã lên MQ", relay coi là "đã gửi notify" — hai writer giẫm nhau; relay cũng chưa
có backoff/poison-handling (3 retry/30s mãi mãi, batch 50 có thể bị starve).

## Decision
1. **Xoá** `event_bus/` RabbitMQ skeleton, service `rabbitmq` + `worker` (mode consume)
   khỏi compose, `docker/rabbitmq/`. Outbox polling relay là đường async duy nhất.
2. `event_log` chỉ còn là **audit + outbox gốc** (append-only, giữ nguyên trigger).
3. Thêm bảng **`notification_delivery`** (event_id, channel, status, attempts,
   next_retry_at, dedup_key): mỗi kênh 1 row; relay claim bằng advisory lock như cũ;
   backoff lũy tiến; quá N attempts → status FAILED + alert (thay DLQ).
4. Semantics: at-least-once, consumer idempotent (dedup_key); template thiếu → row
   SKIPPED (không chặn batch).

## Considered Options
| Phương án | Ưu | Nhược |
|---|---|---|
| **A (chọn) Outbox + polling relay + delivery table** | 0 hạ tầng mới, đã chạy, multi-relay an toàn (advisory lock) | latency notify ≤30s (chấp nhận cho nhắc lịch) |
| B Hoàn thiện RabbitMQ | chuẩn, latency thấp | 3 mảnh phải xây + broker phải vận hành; không có nhu cầu latency |
| C Supabase Realtime/webhooks làm bus | tận dụng sẵn | không kiểm soát retry/ordering; coupling vendor sâu thêm |

## Consequences
**Tích cực:** bớt 1 container + toàn bộ dead code; delivery có trạng thái quan sát được;
mở kênh Zalo OA sau này = thêm channel row, không đổi kiến trúc. **Tiêu cực:** nếu một
ngày cần fan-out tới nhiều consumer tốc độ cao (chưa thấy kịch bản), phải dựng lại broker
— chấp nhận, quyết định lại bằng ADR mới khi có bằng chứng.
