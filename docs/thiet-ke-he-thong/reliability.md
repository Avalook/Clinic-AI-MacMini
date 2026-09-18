---
title: "Reliability semantics — at-least-once, ordering theo stream, correction không sửa lịch sử, outbox/inbox, replay"
lop: 2
lop_ten: Kiến trúc hướng sự kiện
tag_nguon: "Care Model §15"
tags: [clinicai, lop2-kien-truc]
---

# Reliability semantics — at-least-once, ordering theo stream, correction không sửa lịch sử, outbox/inbox, replay

> [!abstract] Healthcare không chấp nhận giả định 'message đến đúng một lần đúng thứ tự'; sáu quy tắc và code đã đạt được mấy.

> «Healthcare operations không chấp nhận giả định "message chắc chỉ đến một lần và đúng thứ tự".» — *§15*

| Quy tắc (thesis) | Nguyên văn | Code hôm nay |
|---|---|---|
| 15.1 At-least-once + idempotency | «Mỗi side effect cần idempotency key, thường dựa trên event_id + policy_id + action_type.» | ✅ `idempotency_key` cho request (17 dòng prod); relay claim event bằng `pg_try_advisory_lock(hashtextextended(event_id))` → hai relay không gửi trùng. ❌ side effect của *policy* chưa có vì chưa có policy. |
| 15.2 Ordering | «Chỉ bảo đảm thứ tự trong boundary hợp lý […] dùng occurred_at để hiểu reality, recorded_at để audit latency; projection phải hỗ trợ recompute.» | ❌ không stream_version; `occurred_at = recorded_at` luôn; relay `ORDER BY occurred_at` toàn clinic. |
| 15.3 Optimistic concurrency | «Command ghi vào một stream phải nêu expected version.» | ✅ `work_item.version` + `CommandRequest.expected_version`; `move_visit_to_station` `FOR UPDATE`; booking CAS `WHERE status = $from`. |
| 15.4 Correction, không sửa lịch sử | «Event đã ghi không bị sửa. Sai sót được xử lý bằng event hiệu chỉnh: ArrivalRecordCorrected · ResultAssociationCorrected · WorkCompletionRevoked.» | ✅ mẫu đúng có sẵn: `tuong_tac_cskh.huy_luc` («Dòng ở lại, chỉ thôi được tính») + event `cskh.tuong_tac_hoan_tac`; `visit` FINALIZED → `amend_visit` RPC (ADR-0008); `event_log` có trigger chặn UPDATE/DELETE. |
| 15.5 Outbox và inbox | «dùng outbox để tránh "DB đã commit nhưng event thất lạc". Consumer dùng inbox/deduplication.» | 🟡 outbox = `event_log.event_published` **một cờ cho mọi consumer** (ADR-0002, `pos_outbox` comment: «One flag cannot serve two consumers»). `pos_outbox` riêng có attempts/backoff/DEAD ✅. |
| 15.6 Replay và quarantine | «projection phải rebuild được; event lỗi schema được quarantine; dead-letter có owner; replay không lặp side effect; mỗi projection ghi checkpoint.» | ❌ không quarantine; relay bỏ qua event không template bằng cách đánh dấu xong; không checkpoint. `pos_outbox.DEAD` là dead-letter thật ✅. |

Kết: **3/6 đạt, 1 nửa, 2 chưa.** Cái nửa (outbox một cờ) là nợ đã được chính ADR-0002 ghi từ 18/07 mà chưa trả: bảng `notification_delivery` per-channel. Thiết kế [[tk-reliability-playbook|Reliability playbook]] + [[tk-communication-delivery|notification_delivery]].

## Nối tới
- [[notification-relay|notification_relay]]
- [[pos-outbox|pos_outbox]]
- [[idempotency-concurrency|Bất biến ép ở Postgres]]
- [[tuong-tac-cskh|tuong_tac_cskh]]
- [[gap-reliability|Khoảng cách 10]]
- [[tk-reliability-playbook|Reliability playbook]]
- [[tk-communication-delivery|notification_delivery]]

## Được dẫn từ
- [[stream-boundary|Năm stream]]
- [[15-invariant|15 bất biến cấp 'hiến pháp']]
- [[tuong-tac-cskh|tuong_tac_cskh]]
- [[notification-relay|notification_relay]]
- [[pos-outbox|pos_outbox]]
- [[idempotency-concurrency|Bất biến ép ở Postgres]]
- [[gap-reliability|Khoảng cách 10]]
- [[tk-reliability-playbook|Reliability playbook]]
