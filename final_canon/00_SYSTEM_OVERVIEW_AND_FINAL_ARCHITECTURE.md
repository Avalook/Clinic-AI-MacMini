# 00 — System Overview & Final Architecture (Kiến trúc cuối cùng)

> File này là **nguồn tổng quan duy nhất** cho dự án ClinicAI. Khi mâu thuẫn với file cũ → file này thắng.
> Cập nhật: 2026-05-20 · Owner: Tuyền (Sáng Ý / Avalook) · Status: **CANON**

---

## 1. ClinicAI là gì

ClinicAI là **agentic operations platform** (nền tảng vận hành dùng tác tử AI) cho phòng khám sản phụ khoa tư nhân **Dr4women** tại Hà Nội (2 cơ sở: Kim Ngưu — chính, Hào Nam — mở sau).

Hệ thống giải quyết bốn vấn đề cốt lõi:

1. **Xoá nhập liệu trùng lặp** — hiện tại CSKH nhập cùng dữ liệu vào Sheet Đặt lịch + Sheet Check lịch + Notion. Đây là pain point #1 từ co-founder của phòng khám.
2. **Thống nhất danh tính bệnh nhân (patient identity)** — cùng người có 2 SĐT (mẹ + cá nhân) → merge thủ công, không nhất quán. Cần Master Patient Index (MPI) tự động.
3. **Phân công việc tự động theo ca trực** (work session) — hiện tại task giao qua Zalo + miệng, "không nhắc thì nhân viên tưởng khỏi làm." Cần auto-assign + escalation theo SLA.
4. **Enforce safety gate (cổng an toàn) y tế** — hiện tại CSKH đôi khi báo KQ XN bất thường cho BN trước khi BS xem → rủi ro lâm sàng. Cần gate cứng GROUP_C tại application layer.

## 2. ClinicAI KHÔNG phải gì

- **Không** phải chatbot tư vấn y tế tự do cho bệnh nhân. Ranh giới pháp lý.
- **Không** phải HIS (Hospital Information System) đầy đủ. MVP scope.
- **Không** phải app riêng cho bệnh nhân hoặc nhân viên. Chỉ Zalo OA. Nhưng vẫn phải có dashboard để theo dõi toàn bộ luồng vận hành cho chủ phòng khám theo dõi. Kế hoạch mới là làm thêm cả dashboard để giải đoạn 1, phòng khám sử dụng dasboard song song với việc nhập liệu thủ công vào notion của phòng khám để theo dõi độ hiệu quả.
- **Không** phải Voice-to-EMR ngay. Phase 2+ sau khi SOAP schema được chốt.
- **Không** phải Risk Scoring AI. Cấm cho đến khi có ≥50.000 thai kỳ có outcome.
- **Không** phải off-the-shelf CRM/HIS. Đã thử, không fit.
- **Không** phải multi-tenant white-label. Single clinic, multi-site.
- **Không** dùng n8n/Dify cho core agent logic.

## 3. Pain points cốt lõi (phòng khám đã xác nhận)

```
P-1  Nhập liệu trùng lặp 3 nơi (Sheet × 2 + Notion)        [B Session 10, Hà]
P-2  Duplicate patient: cùng người, nhiều SĐT              [B Session 4, Hoa]
P-3  Task giao qua Zalo/miệng, không tracking              [B Session 10, Hà]
P-4  CSKH báo KQ XN abnormal trước BS review               [B Session 19+24]
P-5  KQ XN về qua email, CSKH nhập tay vào Notion         [B Session 4, Hoa]
P-6  Phòng khám đã mất data khi đổi phần mềm trước         [B Session 10, Hà]
P-7  Quy trình lưu trong Google Doc tản mát, truyền miệng  [B Session 19, Hoa]
P-8  ~10K hồ sơ BN trong Notion + GSheet cần migrate       [B Session 4+10]
P-9  Mọi quy trình hiện cần ≥2 app                         [B Session 10, Hà]
P-10 Hoa "KHÔNG PHÁT SINH THÊM task" — điều kiện cứng      [B Session 19]
```

## 4. Tầm nhìn hệ thống production

```
Một bệnh nhân nhắn Zalo, Facebook,... các kênh sau này mở rộng → ClinicAI nhận diện danh tính tự động → phân loại intent → đặt lịch hoặc tư vấn → tạo task cho CSKH on-duty →
KQ XN về tự động phân loại GROUP_A/B/C → GROUP_C chặn cứng đến khi
BS xem → BS xem qua Zalo → CSKH được unlock notify BN → audit log
mọi bước. Trước mỗi ca khám 30 phút, BS nhận Pre-visit Brief 7 fields
qua Zalo. Hoa sửa rule SLA bằng cách edit file markdown trong wiki/,
hệ thống tự pickup. Mac Mini chạy Whisper transcript + Qwen worker rẻ + Marklt để chuyển file pdf sang markdown cho AI đọc nhanh.
VPS chạy 24/7 FastAPI + LangGraph workers + RabbitMQ+ API Anthropic sonnet,haiku. Supabase Cloud
là DB chính. Phòng khám không phải mở app mới.
```

## 5. Kiến trúc end-to-end (sơ đồ thật, không trừu tượng)

```
┌──────────────────────────┐         ┌──────────────────────────┐
│  MAC MINI M4 PRO 48GB    │         │  VPS PRODUCTION 24/7     │
│  (dev + AI worker)        │         │                          │
│  ─────────────────       │         │  - FastAPI services       │
│  - Code dev               │         │  - LangGraph workers     │
│  - PhoWhisper (audio)     │  VPN /  │  - RabbitMQ broker       │
│  - Qwen3-14B (worker)     │  HTTPS  │  - Webhook receivers     │
│  -  BGE-M3 (embed)       │◄────────►│  - Cron schedulers       │
│                           │         │  - Pancake adapter        │
│  Failover: nếu Mac down, │         │  - Zalo OA adapter        │
│  fallback Haiku API.      │         │  - Dashboard (Next.js)    │
└──────────────────────────┘         └────────────┬──────────────┘
                                                  │
       ┌──────────────────────────────────────────┼──────────────────────┐
       ▼                                          ▼                      ▼
┌──────────────────┐                  ┌──────────────────┐    ┌──────────────────┐
│ SUPABASE CLOUD   │                  │ ANTHROPIC API    │    │ EXTERNAL APIS    │
│                  │                  │                  │    │                  │
│ - PostgreSQL 16  │                  │ - Claude Sonnet  │    │ - Zalo OA        │
│ - pgvector       │                  │   (reasoning)    │    │ - Pancake        │
│ - Auth/RLS       │                  │ - Claude Haiku   │    │ - Diag (lab)     │
│ - Storage (local │                  │   (trivial)      │    │ - Medlatec (lab) │
│   for audio)     │                  │                  │    │ - KiotViet       │
│ - Realtime       │                  │                  │    │                  │
└──────────────────┘                  └──────────────────┘    └──────────────────┘
```

### 5.1 Layer-by-layer (8 tầng từ input đến action)

```
Tầng 0A — Channel Adapter (Pancake, Zalo OA, Hotline, Walk-in)
          Job: normalize input → InteractionEvent. KHÔNG ghi DB. KHÔNG business logic.
                                          ↓ (InteractionEvent)
Tầng 0B — Event Bus (RabbitMQ)
          Job: durable queue + fan-out. Exchange theo topic.
                                          ↓
Tầng 0C — Golden Record Engine (Layer 0C)
          Job: identity resolution (MPI) + dedup + ghi Domain DB.
          ĐÂY LÀ CỔNG DUY NHẤT ghi vào Patient/Appointment/Visit/etc.
                                          ↓
Tầng 1  — Domain DB (Supabase PostgreSQL)
          35 entities · 9 domains (theo v6 Schema). pgvector cho KB chunks.
          Trigger enforce_append_only() cho 6 bảng append-only.
                                          ↓
Tầng 2  — Domain Services (FastAPI)
          patient_service · scheduling_service · lab_service · task_service ·
          billing_service · communication_service. Business rules ở đây.
                                          ↓
Tầng 3  — Tool Layer
          Thin functions expose Layer 2 cho graphs. Deterministic.
          Ví dụ: create_appointment(), get_patient_summary(), classify_lab_result()
                                          ↓
Tầng 4  — LangGraph Orchestration
          Orchestrator Graph + 6 sub-graphs (Scheduling, Lab Triage, Task Manager,
          Communication, Pre-visit Brief, Voice-to-EMR Phase 2). State + checkpoint.
                                          ↓
Tầng 5  — AI Engine (model_gateway)
          Cost-aware routing: Qwen local → Haiku → Sonnet theo độ phức tạp.
          KHÔNG dùng AI cho safety gate decision.
                                          ↓
Tầng 6  — KB / Skills Layer
          Markdown source of truth → sync job → kb_page + kb_chunk + kb_policy_rule.
          3 retrieval strategies: JSONB structured · pgvector semantic · tsvector fulltext.
                                          ↓
Tầng 7  — Output Channels
          Zalo OA (BN) · Zalo OA Internal (staff) · Dashboard read-only.
          KHÔNG ghi DB từ đây — loop back qua event_log.
```

## 6. LangGraph layout — Orchestrator + 6 sub-graphs

| Sub-graph | Trigger | Job | Owner |
|-----------|---------|-----|-------|
| **Orchestrator** | Mọi InteractionEvent + scheduled tick | Route đến sub-graph đúng theo event type | Tuyền |
| **Scheduling** | Booking request, cancellation, walk-in | Tạo/sửa/huỷ appointment, slot-fill | Phase 1 |
| **Lab Triage** | LabResult event | Classify GROUP_A/B/C → gate GROUP_C → notify | Phase 2 |
| **Task Manager** | Bất kỳ event tạo task | Auto-assign theo WorkSession, SLA snapshot, escalation | Phase 2 |
| **Communication** | Zalo/Pancake inbound | Intent extraction + reply composition + routing | Phase 1 |
| **Pre-visit Brief** | Cron 30' trước WorkSession | Assemble 7-field brief, gửi BS qua Zalo | Phase 2 |
| **Voice-to-EMR** | Audio upload | Whisper transcript → SOAP fields → review gate | Phase 3 |

**Quy tắc:** Mỗi sub-graph có State riêng (TypedDict), nodes riêng, prompts riêng (lưu ở `wiki/agent-policy/prompts/`), tool subset riêng, checkpoint table riêng trong Postgres.

## 7. Vì sao chọn kiến trúc này (không chọn cái khác)

| Lựa chọn | Cái đã loại | Lý do |
|---|---|---|
| **LangGraph 1.0** | CrewAI, AutoGen, custom orchestrator | LangGraph đã chuẩn production 2026 (Uber/JPM/LinkedIn dùng). Checkpoint Postgres-backed. Sub-graph composable. CrewAI quá magical, hard to debug. |
| **FastAPI** | Django, Flask, Litestar | Python standard, async-native, Pydantic-friendly, hợp Supabase + LangGraph. |
| **Supabase Cloud** | Self-hosted Postgres, Firebase, Planetscale | Postgres + pgvector + Auth + Storage in-one. Đã verified với phòng khám (họ dùng Notion US-hosted, precedent OK). Self-host sau khi scale. |
| **RabbitMQ** | Kafka, Redis Streams, NATS | Đủ cho scale ClinicAI (~200 BN/tuần). Đơn giản hơn Kafka rất nhiều. Docker 1 lệnh. |
| **Anthropic Claude** | OpenAI, Gemini, Llama API | Sonnet tốt nhất cho reasoning tiếng Việt + medical context. Haiku rẻ. Có Claude Code đi kèm. |
| **PhoWhisper on-prem** | Whisper API, Deepgram | Pháp lý: audio không được rời phòng khám (NĐ13/2023). PhoWhisper fine-tune cho tiếng Việt. |
| **Qwen3-14B local** | Llama-3, DeepSeek local | Qwen3 tốt cho tiếng Việt + cost-saving. Fallback Haiku nếu Mac Mini down. |
| **BGE-M3** | | tốt cho tiếng việt |
| **Pancake adapter MVP** | Native Zalo SDK trực tiếp | Pancake đã có trong workflow phòng khám. Native Zalo OA = Phase 2. |
| **KB markdown source** | Notion API, headless CMS | Markdown trong git = version + diff + audit. Notion dependency nguy hiểm (vendor lock-in). |

## 8. So sánh với best practices thế giới (đến 2026-05-20)

### 8.1 Pattern adopt (áp dụng)

```
✓ LangGraph + PostgresSaver checkpoint           — production standard Q2 2026
✓ Event-driven architecture (EDA)                 — foundational layer cho agents
✓ Multi-agent harness cho dev team                — Anthropic 3-agent pattern (Mar 2026)
✓ Human-in-the-loop checkpoints                   — EU AI Act Art.14 deadline 08/2026
✓ Context engineering 3-tier                      — Anthropic Engineering 2025
✓ Policy-as-data (KB → DB sync)                   — mature enterprise pattern
✓ Tool boundary (deterministic vs reasoning)      — OpenAI Agents SDK + Anthropic
✓ Append-only event log + audit trail             — HL7 FHIR + TT13/2011 requirement
✓ Identity anchor pattern (immutable UUID PK)     — CRM/EHR best practice
✓ Master Patient Index (MPI)                      — healthcare standard
✓ Master data tables (no hardcoded ENUM)          — config-as-data
```

### 8.2 Pattern KHÔNG adopt MVP (defer hoặc skip)

```
⏭ Temporal durable workflow                       — overkill cho ClinicAI scale.
                                                    Reconsider khi có multi-day workflow.
⏭ OpenAI Agents SDK                               — đã chọn LangGraph + Claude
⏭ Full OpenTelemetry stack                        — Phase 2/3. Phase 1 đủ Supabase logs.
⏭ Microservices fan-out                            — 1 VPS không cần. Monolith first.
⏭ Reflective memory (agent self-learning)         — compliance trap trong y tế. Skip.
⏭ Hosted "Claude Managed Agents"                  — mất control, overkill cost.
⏭ Vector search cho everything                    — chỉ dùng cho clinical KB.
```

### 8.3 Pattern NGUY HIỂM nếu sai

```
✗ "AI quyết định safety gate"                     — CẤM. AI suggest, code + human enforce.
✗ Mega-graph (1 graph cho tất cả workflow)        — Unmaintainable > 10 nodes.
✗ Multi-tenant generalize sớm                     — Mỗi clinic constraints khác.
✗ Long-context "dump everything"                  — Cost 4x, quality giảm 84% benchmark.
✗ Multiple agents parallel write cùng DB row      — Race condition. Golden Record Engine = single writer.
✗ Reflective memory không gated                   — Audit nightmare trong y tế.
✗ Adapter ghi thẳng Domain DB                     — Bypass MPI + audit.
✗ Hardcode rule trong code thay vì KB             — Hoa không sửa được = handoff fail.
✗ Telegram/SMS/email fallback                     — Phá Zalo-only.
✗ Notion API as runtime KB                        — Vendor lock-in, không offline.
```

## 9. Final Architecture Decision (FAD) — Quyết định kiến trúc cuối cùng

```
FAD-1   Orchestration                LangGraph 1.0 + PostgresSaver checkpoint
FAD-2   Backend                      FastAPI 0.110+, Python 3.12, async-first
FAD-3   Database                     Supabase Cloud (PostgreSQL 16 + pgvector 0.7)
FAD-4   Event bus                    RabbitMQ 3.13 (Docker single instance MVP)
FAD-5   AI cloud                     Anthropic Claude Sonnet + Haiku
FAD-6   AI local                     Qwen3-14B + PhoWhisper-large-v3
FAD-7   Embeddings                   MiniLM-L12-v2 (384-d) Phase 1, BGE-M3 dự phòng
FAD-8   Patient comm                 Zalo OA only (BN), Zalo OA Internal (staff)
FAD-9   Multi-channel inbox          Pancake adapter MVP → native Zalo Phase 2
FAD-10  Lab integration              Diag + Medlatec (API where exists, email OCR fallback)
FAD-11  Billing                      KiotViet integrate (không thay thế MVP)
FAD-12  Voice                        PhoWhisper on-premise. Audio không rời clinic.
FAD-13  KB                           Markdown source → sync job → Postgres 3 retrieval strategies
FAD-14  Dashboard                    Next.js 15 (App Router) + Supabase Auth, read-only Phase 1
FAD-15  Deploy                       Docker Compose trên VPS, GitHub Actions CI/CD
FAD-16  Identity PK                  clinic_patient_id UUID + patient_code BN-YYYY-XXXXXX + CCCD nullable unique
FAD-17  Safety gates                 3 hard gates: GROUP_C lab, FINALIZED visit, is_training staff
FAD-18  Memory tiers                 Immediate (graph state) + Operational (WorkSession cache) + Long-term (Supabase + KB)
FAD-19  Schema canon                 v6 Schema (35 entities · 9 domains) — ClinicAI_v6_Schema_Memory_1.md
FAD-20  Multi-site                   ClinicLocation entity, location_id bắt buộc mọi entity vận hành
```

## 10. Tài liệu liên quan

Đọc tiếp theo thứ tự:
- `01_IMPLEMENTATION_ROADMAP_AND_TASKS.md` — phase build order + task template
- `02_CODING_RULES.md` — coding standards production
- `05_DATABASE_DESIGN_FINAL.md` — schema decisions chi tiết
- `06_HARD_DECISIONS_AND_STYLE.md` — locked decisions không vi phạm
- `08_END_TO_END_SYSTEM_DESIGN.md` — deploy + repo structure
- `11_REVIEW_AGENDA_FOR_HUMAN.md` — review từng phần với Quang

---

*00_SYSTEM_OVERVIEW_AND_FINAL_ARCHITECTURE.md · 2026-05-20 · Edit khi business scope hoặc tech stack thay đổi.*
