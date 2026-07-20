# ADR-0007 — LangGraph checkpointer ở schema `langgraph` trên Supabase: ngoại lệ có kiểm soát của quy tắc "schema chỉ qua Supabase CLI"

| | |
|---|---|
| **Status** | Proposed |
| **Date** | 2026-07-18 |
| **Deciders** | Quang |
| **Liên quan** | Design doc v5 §5.5; `orchestrator/checkpointer.py`; CLAUDE.md rule "DB đổi CHỈ qua Supabase CLI" |

## Context
Hội thoại multi-turn của orchestrator cần checkpoint bền (MemorySaver mất khi restart).
`AsyncPostgresSaver` của LangGraph tự tạo/migrate 4 bảng của nó qua `saver.setup()` lúc
boot — không phát hành file SQL để đưa vào `supabase/migrations/`. Điều này vênh quy tắc
dự án "schema chỉ đổi qua CLI migration".

## Decision
Chấp nhận **ngoại lệ có rào**: checkpointer dùng Postgres của chính Supabase project,
nhưng bị **giới hạn trong schema riêng `langgraph`** (code đã CREATE SCHEMA IF NOT
EXISTS + setup() ở boot). Quy tắc kèm theo: (1) schema `public` tuyệt đối không bị
setup() đụng; (2) không code nghiệp vụ nào JOIN sang `langgraph.*`; (3) backup/restore
coi `langgraph` là **disposable state** (mất = mất hội thoại đang dở, không mất nghiệp
vụ) — pg_dump đêm không cần cover; (4) `CHECKPOINTER_BACKEND` default trong code đổi
từ `memory` → đọc bắt buộc từ env ở production (fail-fast nếu thiếu) để tránh
silent-degrade về MemorySaver.

## Considered Options
| Phương án | Ưu | Nhược |
|---|---|---|
| **A (chọn) Schema riêng trên Supabase, tự-setup, disposable** | 0 hạ tầng mới; RPO nghiệp vụ không đổi | ngoại lệ quy tắc migration (được rào + ghi nhận tại đây) |
| B Vendor hoá DDL của LangGraph vào migrations | 100% đúng quy tắc | phải track DDL nội bộ của thư viện, gãy khi upgrade langgraph |
| C SQLite/file local cho checkpoint | tách khỏi Supabase | state nằm trên Mac → mất khi Mac chết, vênh nguyên tắc "Mac chết không mất gì" |

## Consequences
**Tích cực:** multi-turn bền qua restart; ranh giới rõ ràng public vs langgraph.
**Tiêu cực:** một pool psycopg thứ hai (max 10) tính vào ngân sách kết nối Supabase
(đã tính ở design doc §4); người mới cần đọc ADR này để hiểu vì sao có schema không
nằm trong `supabase/migrations/`.
