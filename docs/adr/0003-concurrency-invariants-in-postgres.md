# ADR-0003 — Invariant concurrency enforce tại Postgres (trigger + advisory lock + RPC); app chỉ dịch SQLSTATE

| | |
|---|---|
| **Status** | Proposed (đã chạy thật cho 2+1 và số thứ tự — ADR này chốt thành nguyên tắc chung) |
| **Date** | 2026-07-18 |
| **Deciders** | Quang |
| **Liên quan** | Design doc v5 §5.6; migrations 20260714000002, 20260717000002; Bài 35 (ticket booking) |

## Context
Hai race đã gặp thật: overbook slot 2+1 và trùng số thứ tự (client MAX+1). Cả hai đã
fix bằng net Postgres: trigger `enforce_slot_capacity` + `pg_advisory_xact_lock`
(doctor, bucket 15', kind) và RPC `check_in_appointment` service_role-only + advisory
lock theo ngày VN. Python/TS check trước chỉ để UX. Trong khi đó vẫn còn pattern xấu:
`confirm/cancel_appointment` check-then-update không CAS; side-effects check-in/complete
là 7 UPDATE "best-effort" rời rạc trong Next route.

## Decision
**Mọi invariant có race window enforce ở Postgres**, theo bậc thang: (1) UNIQUE/CHECK
constraint → (2) CAS `UPDATE ... WHERE status IN (from...)` trong 1 statement → (3)
trigger + `pg_advisory_xact_lock` → (4) RPC SECURITY DEFINER khi cần multi-statement
atomic. Service layer: precondition check (UX) + dịch SQLSTATE → HTTP 409/422; KHÔNG
tự cài lock trong Python. Side-effects đa bảng của một command đi trong **một
transaction**; side-effects không-critical (notify, audit ngoài) đi outbox.
**Ràng buộc hạ tầng đi kèm:** backend nối Supabase qua **Supavisor session mode :5432**
— `pg_advisory_xact_lock` sống theo transaction (an toàn), nhưng relay dùng
session-level `pg_try_advisory_lock` nên KHÔNG được chuyển transaction-mode :6543 nếu
chưa refactor relay.

## Considered Options
| Phương án | Ưu | Nhược |
|---|---|---|
| **A (chọn) DB-authoritative** | đúng dưới mọi client (Next, FastAPI, psql); multi-process an toàn; đã chứng minh | luật nằm ở SQL — cần test SQL riêng (fixture bootstrap_plain_postgres đã có) |
| B Lock trong Python (asyncio/redis lock) | dễ đọc | chỉ đúng trong 1 process; thêm Redis; sai khi có 2 đường ghi |
| C Serializable isolation | tổng quát | retry storm, khó vận hành hơn advisory lock chọn điểm |

## Consequences
**Tích cực:** API scale ngang sau này không phải nghĩ lại; mọi đường ghi (kể cả tay)
đều bị net chặn. **Tiêu cực:** logic SQL phải có test tầng DB (bổ sung test cho slot
guard / checkin / idempotency — hiện chỉ có test RLS event_log); message lỗi tiếng Việt
trong trigger là một phần hợp đồng — đổi phải kèm đổi mapping ở service.
