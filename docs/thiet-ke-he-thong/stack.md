---
title: "Stack đang chạy — Caddy → Next.js → FastAPI → Postgres 17, một VPS, một người vận hành"
lop: 3
lop_ten: Code đang chạy
tag_nguon: "CLAUDE.md · SO-LUAT Phần 1 · docker ps 04/09"
trang_thai: Đã có
tags: [clinicai, lop3-code]
---

# Stack đang chạy — Caddy → Next.js → FastAPI → Postgres 17, một VPS, một người vận hành

> [!abstract] Quy mô thật quyết định kiến trúc: ~1 lượt gọi/giây, 50–80 BN/ngày, 4 vCPU/8 GB, Postgres cùng máy.

Đo `docker ps` trên `clinic-vps` 04/09/2026 — 23 container, 2 môi trường:

```
prod    (:80)   clinicai_prod-{api, dashboard, caddy, notification-relay, uptime-kuma, dozzle}
                clinicai_{db, auth, rest, realtime, supabase_gateway, auth_guard}
staging (:8080) cùng bộ, tiền tố clinicai_staging-* / clinicai_stg_*
```

| | |
|---|---|
| Máy | VPS Vietnix, 4 vCPU AMD EPYC, 8 GB, 48 GB đĩa (dùng 26%) |
| Tải đo được | ~1 lượt gọi/giây (SO-LUAT Phần 1) |
| Database | Postgres 17 tự dựng, **cùng máy** với backend — «một truy vấn nóng dưới 1 ms», «một lượt đi hỏi tốn ~4 ms» (Phần 5) |
| Đội | 1 dev + AI |
| Backend | FastAPI, 212 file Python; `services/` 69 file, 23.049 dòng — phẳng, không module (ADR-0001 chưa thi hành) |
| Frontend | Next.js, 326 file TS/TSX, 55 route màn hình, 62 route BFF |
| DB | 79 bảng public, 119 migration, 9 view, 24 SQL test |
| Realtime | LISTEN/NOTIFY → SSE (không Supabase Realtime từ 06/08) |
| Async | 1 tiến trình `worker --relay` (Telegram) + `--pos-relay` (profile) |
| AI | Anthropic API (Haiku/Sonnet), LangGraph, checkpointer schema `langgraph` |
| Auth | GoTrue tự dựng + PostgREST (chỉ đọc) + JWT → `staff.auth_user_id` |

Ba luật nền chi phối thiết kế đích (SO-LUAT):

> «**Luật 7.1** — Postgres là hạ tầng có trạng thái duy nhất phía ứng dụng. Idempotency, hàng chờ gửi tin, giữ chỗ, giới hạn truy cập, "cache" = index + view.»

> «**Luật 7.2** — Trước khi đề xuất bất kỳ hạ tầng nào: đưa ra phép đo chứng minh thứ đang có không đủ.»

> «**Luật 8.1** — Ghi vết đi cùng transaction với việc nó mô tả.» (và Phần 7: đẩy nhật ký qua hàng chờ «Sai với y tế»)

Đây chính là lý do thiết kế đích không có Kafka/Redis/broker — và thesis cũng không đòi ([[kien-truc-toi-thieu|Kiến trúc logic tối thiểu]] §23).

## Nối tới
- [[kien-truc-toi-thieu|Kiến trúc logic tối thiểu]]
- [[adr-so-luat|13 ADR + Sổ luật]]
- [[realtime-sse|LISTEN/NOTIFY → ChangeBroker → SSE]]
- [[notification-relay|notification_relay]]
- [[multi-tenant-rls|Multi-tenant thật]]
- [[ci-guards|CI]]

## Được dẫn từ
- [[kien-truc-toi-thieu|Kiến trúc logic tối thiểu]]
- [[realtime-sse|LISTEN/NOTIFY → ChangeBroker → SSE]]
- [[multi-tenant-rls|Multi-tenant thật]]
- [[adr-so-luat|13 ADR + Sổ luật]]
- [[tk-nguyen-tac|Nguyên tắc thiết kế đích]]
- [[tk-modular-monolith|Thi hành ADR-0001]]
