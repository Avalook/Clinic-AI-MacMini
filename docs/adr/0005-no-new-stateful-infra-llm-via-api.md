# ADR-0005 — Không thêm hạ tầng stateful mới (không Redis, không vector DB riêng, không local LLM reasoning); Postgres làm idempotency/cache/rate-limit; LLM qua Anthropic API 2-tier

| | |
|---|---|
| **Status** | Proposed |
| **Date** | 2026-07-18 |
| **Deciders** | Quang |
| **Liên quan** | Design doc v5 §5.7, §7 |
| **Affected decisions (canon 06)** | Supersedes: FAD-6 (Qwen3-14B local), FAD-7 (MiniLM/BGE embeddings — chỉ dùng pgvector khi KB thật sự cần, model chọn lúc đó), phần Qwen + MiniLM của D014 (tech stack locked), D015 (cost routing "trivial → Qwen local" → thay bằng rule-first + Haiku/Sonnet 2-tier), D037 (failover "Qwen down → Haiku → Sonnet" → thành "Anthropic down → rule/template + safety-bias"). Giữ nguyên: FAD-5 (Sonnet+Haiku), D011/FAD-12 (PhoWhisper on-prem), D016 (LangGraph chỉ là orchestration) |

## Context
Quy mô 1 RPS, RTT Supabase Seoul 30–80ms, đội vận hành = 1 người + AI. Mỗi hệ stateful
thêm vào (Redis, broker, vector DB, model server) là một thứ phải backup/monitor/vá.
LLM cost thực tế $1–5/ngày với routing Haiku/Sonnet; PhoWhisper STT bắt buộc on-prem
theo NĐ13 (audio không rời phòng khám) — nhưng reasoning thì không có ràng buộc đó
(text đã redact PII trong log, hợp đồng xử lý dữ liệu qua API).

## Decision
1. **Postgres là hạ tầng stateful duy nhất phía app**: idempotency (bảng
   `idempotency_key`), outbox/notify (`event_log` + `notification_delivery`), rate-limit
   in-process (slowapi, không cần store phân tán vì 1 node), "cache" = index + RPC/view
   khi có bằng chứng chậm. pgvector trong chính Supabase nếu KB cần semantic search.
2. **LLM reasoning qua Anthropic API**, 2 tier giữ nguyên: Haiku 4.5 (gateway) /
   Sonnet 4.6 (main_brain); model id chuyển thành env config. Batch API cho brief đêm.
   Cost guard theo ngày trong `platform/ai`.
3. **Voice STT (PhoWhisper) là ngoại lệ on-prem duy nhất**, chạy container/service riêng
   (ADR-0006), CPU int8; không bao giờ gửi audio ra ngoài.
4. Không local LLM reasoning (Qwen) dù 48GB đủ chạy — quyết định lại bằng ADR mới chỉ khi
   có yêu cầu pháp lý mới hoặc API không đạt chất lượng tiếng Việt y tế.

## Considered Options
| Phương án | Ưu | Nhược |
|---|---|---|
| **A (chọn) Postgres-only + API LLM** | 0 hạ tầng mới; đủ xa nhu cầu; tiền LLM không đáng kể | mất "độc lập vendor"; rate-limit chỉ per-process (đủ vì 1 process) |
| B Thêm Redis | idempotency/cache nhanh hơn | thêm 1 service phải sống 24/7 cho lợi ích 0 đo được ở 1 RPS |
| C Local Qwen (canon FAD-6) | data không rời máy; 48GB RAM đủ | chất lượng y tế thấp hơn; vận hành model + đánh giá = việc mới; Docker macOS không Metal → phải native |

## Consequences
**Tích cực:** bề mặt vận hành nhỏ nhất có thể; lift-and-shift VPS chỉ mang 1 DB ngoài.
**Tiêu cực:** nếu sau này cần queue latency thấp hoặc cache nóng, phải thêm ADR mở lại;
phụ thuộc Anthropic uptime — đã có fallback rule/template + safety-bias.
