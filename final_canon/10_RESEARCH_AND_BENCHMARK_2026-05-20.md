# 10 — Research & Benchmark (2026-05-20)

> Tóm tắt best practices industry Q2 2026 và so sánh với ClinicAI.
> Cập nhật: 2026-05-20 · Status: **CANON** · Re-read trước mỗi Phase mới.

---

## 1. Best practices Q2 2026 — overview

### 1.1 LangGraph 1.0 (released October 2025)

- Production-grade checkpointing với `AsyncPostgresSaver` (mature path).
- Sub-graph composability stable.
- Used at production scale: Uber, JP Morgan, BlackRock, Cisco, LinkedIn, Klarna.
- 90 triệu monthly downloads.

**Áp dụng ClinicAI:** ADOPT (Loại A D014, D016, D017). PostgresSaver checkpoint trên Supabase. Sub-graph layout per domain.

### 1.2 LangGraph + Temporal hybrid pattern

- LangGraph: micro-level reasoning (graph step, cyclical agent logic).
- Temporal: macro-level durable workflow (hours-to-days, survive infrastructure events).
- OpenAI Codex uses Temporal cho "agent wait days for human approval."
- Pattern: Temporal workflow activity spawns LangGraph for reasoning subtask.

**Áp dụng ClinicAI:** SKIP MVP, RECONSIDER Phase 3. Workflows ClinicAI ngắn (seconds-minutes). Longest = "doctor review GROUP_C wait" — hours, không days. RabbitMQ + LangGraph checkpoint đủ. Temporal complexity overkill.

### 1.3 Event-driven architecture (EDA)

- "Foundational design paradigm" cho agents Q2 2026.
- 70-90% latency reduction vs polling.
- Mainstream: Kafka, RabbitMQ, NATS.
- 40% enterprise software dự kiến có AI agents cuối 2026.

**Áp dụng ClinicAI:** ADOPT (Loại A D006, P3 in 01_ROADMAP). RabbitMQ Phase 1. Kafka Phase 3+ nếu cần.

### 1.4 Anthropic agent harness (March 2026)

- Two-agent harness: initializer (setup feature list + git state + progress file) + coder (incremental session-by-session).
- Three-agent harness: planner + generation + evaluation.
- Address "context rot" — model degrade as window fills.
- Pattern: structured handoff artifacts (feature list, progress file) thay vì raw context dump.

**Áp dụng ClinicAI:**
- For dev team: ADOPT. Canon docs (`context/`, `final_canon/`) là handoff artifacts. Claude Chat = planner, Claude Code = coder, Claude Chat = verifier.
- For clinic runtime: SKIP. Orchestrator graph IS the planner. Adding meta-planner = over-engineering.

### 1.5 Healthcare AI safety patterns

- EU AI Act Article 14 (deadline Aug 2026): high-risk AI systems mandate human oversight interface.
- Healthcare = high-risk by default.
- HITL (Human-in-the-Loop) = compliance baseline, not optional.
- Multi-agent roles: planner + tool specialist + verifier.
- PHI-safe data flows, consent + provenance tracking, deterministic validation.

**Áp dụng ClinicAI:**
- ADOPT (Loại A D022 GROUP_C gate + D009 FINALIZED visit gate + D023 is_training gate).
- Human Review Queue cho MPI ambiguity = HITL pattern.
- Compliance: TT13/2011 + NĐ13/2023 alignment (Vietnam equivalent). Crypto-erase pattern Phase 1.5 (D058).
- Not directly under EU AI Act, but Vietnam regulators following trend.

### 1.6 Context engineering (Anthropic 2025-2026)

- 3-tier memory architecture (immediate / operational / long-term).
- Selective retrieval reduces 84% tokens in 100-turn workflows.
- Context Contract pattern: agents have explicit data contracts before build.
- Avoid context rot via reset + handoff artifacts.

**Áp dụng ClinicAI:** ADOPT (Loại A D032, D033). 3-tier memory in runtime. Context Contract bắt buộc trước mỗi sub-graph build.

### 1.7 Policy-as-data (mature enterprise pattern)

- Business rules editable by non-devs.
- Storage: JSON/YAML/markdown trong git → DB sync.
- 3 retrieval strategies based on rule shape: structured / semantic / full-text.

**Áp dụng ClinicAI:** ADOPT (Loại A D029, D030, D031). Markdown source, KBPolicyRule JSONB, KBChunk pgvector, KBPage tsvector.

### 1.8 Tool boundary (deterministic vs reasoning)

- AI for reasoning; tools for deterministic action.
- Typed, testable, mockable tools.
- Anthropic harness + OpenAI Agents SDK both lock this boundary.

**Áp dụng ClinicAI:** ADOPT (Loại A D016). Layer 3 (tools) deterministic. Layer 5 (AI) reasoning. Tools never call LLM.

### 1.9 Multi-agent coding workflow

- Anthropic Claude Code multi-agent orchestration (April 2026).
- Lead agent decomposes + sub-agents work parallel on shared FS.
- Multiple Claude sessions in parallel (worktrees / web sessions).

**Áp dụng ClinicAI:**
- For dev team: PARTIAL ADOPT. Claude Chat (lead) + Claude Code/Codex/Antigravity (sub-agents). But careful: not "all parallel write," sequential ownership per task (04_MULTI_AI_WORKING_MODEL §3).
- For clinic runtime: NO. Multiple LangGraph workers consuming RabbitMQ events OK; multiple parallel writers to same DB row = race condition.

### 1.10 Supabase / Postgres production (2026)

- Pgvector mature (HNSW index defaults).
- Realtime + Auth + Storage + Edge Functions in single platform.
- Pro plan PITR 7-day standard.
- Multi-tenant via RLS for SaaS; single-tenant fine cho ClinicAI.

**Áp dụng ClinicAI:** ADOPT (Loại A D014). Cloud Phase 1; self-host nếu scale demand.

## 2. Patterns adopt fully

```
PATTERN                                  WHERE ADOPTED
─────                                    ─────────────
LangGraph 1.0 + PostgresSaver            D014, P8 in 01_ROADMAP
Event-driven (RabbitMQ)                  D014, P5
Append-only audit log                    D007, D008, 6 tables
Identity anchor (UUID PK)                D001, D002, D003
Master Patient Index                     §3.2 in 05_DATABASE_DESIGN
Human-in-the-loop checkpoint             D022, D023, D041, Human Review Queue
3-tier memory                             D032, §1 in 07_CONTEXT_MEMORY
Context Contract                          D033, §3 in 07_CONTEXT_MEMORY
Policy-as-data (KB markdown→DB)          D029, D030, D031, P10
Tool boundary                             D016, §10 in 00_SYSTEM_OVERVIEW
Master data tables (no ENUM)              D019, D045, D046
Multi-site location_id                    D021
Cost-aware AI routing                     D015, P11
Pgvector semantic search                  D030, KBChunk
Selective context retrieval               D032, §10 in 09_CLAUDE_AGENT
```

## 3. Patterns adopt partial

```
PATTERN                                  STATUS                NOTES
─────                                    ──────                ─────
Multi-agent harness (Anthropic)          Dev team ADOPT        Claude Chat + Code + Codex
                                         Runtime SKIP          Orchestrator IS the planner
Healthcare planner-specialist-verifier   Lab Triage YES        Other graphs simpler
                                         Pre-visit Brief YES   Doctor is verifier
Observability stack                       Phase 1 minimal       Supabase logs + RabbitMQ UI
                                         Phase 2 Loki/Grafana
CI/CD eval suites                         Phase 1 manual        Safety gate tests mandatory
                                         Phase 13 automated    Golden 50+20+5 tasks
Replay testing                            Phase 1 fixture        Capture real Pancake/Zalo
                                         Phase 2 simulator     Skip simulator agent
Agent memory                              Short+Long ADOPT      D032
                                         Reflective SKIP       Compliance trap in y tế
Multi-agent coding (parallel sessions)   Dev SEQUENTIAL OK     One task one owner (04_MULTI_AI)
                                         Runtime SKIP          Race condition risk
```

## 4. Patterns NOT adopt / defer

```
PATTERN                                  REASON
─────                                    ──────
Temporal durable workflow                 Overkill ClinicAI scale (seconds-minutes).
                                          Reconsider Phase 3 if multi-day flows emerge.

Full OpenTelemetry stack                  Phase 3+. Phase 1 = Supabase + RabbitMQ admin.

Microservices fan-out                     1 VPS Phase 1. Monolith fine.
                                          Split per-domain Phase 3+ if scale.

Reflective memory (agent self-learning)  Compliance trap. Auditors ask "when did logic
                                          change?" Reflective updates diffuse.

Hosted Claude Managed Agents              Lost control. Self-hosted LangGraph cheaper
                                          + more control cho compliance constraints.

Vector search for everything              Cost + noise. Use 3-strategy KB (D030).

Long-context "dump everything"            4x cost + 84% quality degrade.
                                          Selective retrieval (D032).

Multi-tenant generalize                   Single-tenant Dr4women. Premature optimization.

Custom CMS for KB                         Markdown first. Quang/Hoa edit qua GitHub web
                                          edit + auto-PR. CMS Phase 2 nếu friction.

Mobile-native apps                        Banned BN + staff. Zalo OA only (D010).

Real-time hotline audio                   Phase 3+. Legal NĐ13/2023 + Audio handling complex.
```

## 5. Patterns DANGEROUS if applied wrong

```
PATTERN                                  WHY DANGEROUS                            MITIGATION
─────                                    ──────────────                            ──────────
"AI decides safety gate"                 Patient harm if AI wrong on classification AI suggests, code + human enforce.
                                                                                   D022, D023, D041.

Mega-graph (1 LangGraph)                  Unmaintainable >10 nodes.                Sub-graph per domain (D017).
                                          State debugging nightmare.

Multi-tenant premature                   Each clinic constraints differ.          Single-tenant. Refactor only when
                                                                                   2nd clinic real, not speculative.

Adapter writes Domain DB                  Bypass MPI + audit + Golden Record.      D006. Adapter emits event only.

ENUM hardcode catalog                    Tech debt mỗi khi clinic thêm service.   Master data tables (D019, D046).

Long-context dump                         Cost 4x + quality degrade.               Selective retrieval (D032).

Reflective memory ungated                Audit nightmare in y tế.                  Skip until clear governance.

Multiple writers same DB row             Race condition silent overwrite.         Golden Record = single writer.

Hardcode rule in code                    Hoa không sửa được = handoff fail.        Policy-as-data (D029).

Microservices premature                  1 VPS = ops headache.                     Monolith first; split khi scale.

Telegram fallback                         Violates Zalo-only constraint.            Constraint enforce at code level.

Notion API runtime                        Vendor lock-in, không offline.            Markdown source (D029).

Self-fork LangGraph                       Upstream evolves fast.                    Use public API only; wrap, không fork.

CCCD as FK                                CCCD nullable.                            UUID PK only (D001, D002).

DELETE FINALIZED visit                   Legal violation TT13/2011.                Append-only + trigger.

Audio cloud STT                          Legal NĐ13/2023.                          PhoWhisper local only (D011).

Risk scoring AI premature                Wrong prediction destroys BS trust.       Wait ≥50K outcomes (D013).

Free-form clinical chatbot                Legal red line VN.                        Cấm (D012). AI helps staff, không BN.
```

## 6. Cost / complexity trade-offs

| Pattern | Adoption cost | Ops complexity | Recommendation |
|---------|---------------|----------------|----------------|
| LangGraph + PostgresSaver | Low | Low | Adopt MVP |
| RabbitMQ event bus | Low (Docker 1 lệnh) | Medium (broker hygiene) | Adopt MVP |
| Pgvector embeddings | Low (Supabase built-in) | Low | Adopt MVP |
| 3-tier memory | Architectural (no infra) | Low | Adopt MVP |
| HITL queue + gates | Architectural | Medium (UI to build) | Adopt MVP |
| Eval suite (gates + golden) | Low | Low (CI runs) | Adopt MVP |
| Replay fixtures | Low (capture) | Low | Adopt MVP |
| Temporal | High (separate runtime) | High (worker fleet) | Skip MVP, Phase 3 reconsider |
| Langfuse / Helicone | Medium | Medium | Phase 2 |
| OpenTelemetry full | High | High | Phase 3 |
| KB CMS non-devs | Medium | Low | Phase 2 nếu friction |
| Reflective memory | Medium | High (governance) | Skip until use case clear |
| Multi-region | High | High | Skip (single VPS scale enough Phase 1-2) |
| Self-host Supabase | High (init) | High (ops) | Phase 3 nếu scale + compliance demand |

## 7. ClinicAI alignment scorecard

```
PATTERN (14 mainstream)                 STATUS
─────                                    ──────
P1  LangGraph 1.0 + PostgresSaver       ✅ ADOPT MVP
P2  Temporal + LangGraph hybrid          ⏭ DEFER Phase 3
P3  Event-driven (EDA)                   ✅ ADOPT MVP
P4  Multi-agent harness (dev side)       ✅ ADOPT
P5  Human-in-the-loop checkpoints        ✅ ADOPT (3 gates + Review Queue)
P6  Context engineering 3-tier           ✅ ADOPT
P7  Policy-as-data                       ✅ ADOPT
P8  Tool boundary                        ✅ ADOPT
P9  Observability                        ⏳ PARTIAL (Phase 2)
P10 CI/CD eval suites                    ⏳ PARTIAL (Phase 1 manual + Phase 13 automated)
P11 Replay testing                       ⏳ PARTIAL (fixture Phase 1)
P12 Agent memory (short/long)            ✅ ADOPT short+long; SKIP reflective
P13 Multi-agent coding (dev)             ✅ ADOPT sequential; SKIP runtime parallel writers
P14 Healthcare planner-specialist-verifier ✅ PARTIAL (Lab Triage native)

Score: 9 full adopt, 4 partial/defer, 1 skip intentional.
Aligned with mainstream agentic + healthcare AI thinking 2026.
```

## 8. Rủi ro over-engineering

```
RISK-1 Build full FHIR R4 compliance Phase 1
       → Premature. ServiceType.loinc_code + snomed_code pre-allocated đủ.
       → Phase 2 fill data per code as clinical workflows mature.

RISK-2 Microservices từ đầu
       → 1 VPS không cần. Monolithic FastAPI + workers OK Phase 1.
       → Split Phase 3+ if scale demands.

RISK-3 Sub-graph quá fine-grained
       → 6 sub-graphs là đúng cut. Đừng split thêm "intent extraction graph"
         "reply composer graph" — đó là nodes trong Communication.

RISK-4 KB phân loại quá sâu
       → 3 categories (agent_policy, clinical, operations) đủ.
       → Phase 2 thêm faq_internal nếu real demand. Không trước.

RISK-5 Eval suite quá to
       → 50+20+5 golden tasks đủ Phase 1.
       → Mở rộng theo real bug patterns, không speculative.

RISK-6 Custom embedding model
       → MiniLM-L12-v2 fine-tune Vietnamese? Skip Phase 1.
       → Use default model, evaluate trên golden tasks first.
       → Fine-tune only if accuracy <85%.

RISK-7 Production Antigravity early
       → Dashboard read-only Phase 1 đủ. Agentic dashboard Phase 2+.

RISK-8 Crypto-erase Phase 1
       → Phase 1.5 OK. NĐ13/2023 không yêu cầu instant compliance.
       → Document plan trong canon doc enough Phase 1.

RISK-9 Auto-deploy
       → Manual deploy là intentional (D056).
       → Auto-deploy = compliance risk + AI agent accountability gap.

RISK-10 Logging everything
        → Structured logs là OK. Nhưng index/store full = expensive.
        → Sample DEBUG logs, retain INFO+ full.
```

## 9. Quyết định cuối cùng — Industry alignment

```
DECISION-INDUSTRY-1   Tech stack giữ nguyên (D014).
                      LangGraph + FastAPI + Supabase + RabbitMQ + Claude + Qwen
                      là đúng line industry 2026.

DECISION-INDUSTRY-2   Defer Temporal đến khi có concrete use case.
                      Trigger reconsider: doctor review wait >24h became norm.

DECISION-INDUSTRY-3   Healthcare safety patterns đã built in.
                      3 gates (D022, D023, D041) là planner-specialist-verifier hợp lý.

DECISION-INDUSTRY-4   Context engineering pattern adopted.
                      3-tier + Context Contract + selective retrieval là current best practice.

DECISION-INDUSTRY-5   Policy-as-data design đúng.
                      Markdown source + 3 retrieval strategies + role-based ownership.

DECISION-INDUSTRY-6   Avoid premature optimization.
                      No Temporal, no microservices, no multi-tenant, no reflective memory.

DECISION-INDUSTRY-7   AI coding team là sequential ownership.
                      Multi-agent coding parallel = race condition trap. One task one owner.

DECISION-INDUSTRY-8   Observability stack scale gradually.
                      Phase 1: Supabase + RabbitMQ admin + structlog JSON.
                      Phase 2: Loki/Grafana.
                      Phase 3: OpenTelemetry full.

DECISION-INDUSTRY-9   Compliance roadmap aligned.
                      TT13/2011 ✓ schema satisfies.
                      NĐ13/2023 Phase 1.5 crypto-erase plan.
                      FHIR R4 Phase 2 LOINC/SNOMED mapping.

DECISION-INDUSTRY-10  Eval suite mandatory Phase 13.
                      Industry standard 2026. Block merge khi fail.
```

## 10. Patterns to monitor (re-evaluate end Phase 2)

```
1. Temporal adoption trong healthcare specifically.
   Trigger: clinical AI vendors converge on Temporal → reconsider.

2. EU AI Act enforcement (Aug 2026).
   Vietnam regulators watch EU trends. If mandatory AI disclosure to patients arrives,
   consent + audit design strengthen.

3. Claude Managed Agents evolution.
   If Anthropic hosted alternative cheap + compliant → trade-off self-host cost.
   Today: self-host LangGraph cheaper + more control.

4. Multi-modal models cho medical (X-ray, ultrasound image classification).
   Phase 3+ if BS need image triage from AI.

5. Local model improvements (Qwen4, Llama-4 ...).
   Quarterly review: routes from Haiku → local nếu local quality match.
```

## 11. Nguồn tham khảo (URLs)

```
LangGraph
- https://www.alphabold.com/langgraph-agents-in-production/
- https://www.spheron.network/blog/langgraph-vs-langchain/
- https://sparkco.ai/blog/mastering-langgraph-checkpointing-best-practices-for-2025

Temporal vs LangGraph
- https://agentmarketcap.ai/blog/2026/04/08/langgraph-vs-temporal-long-running-agent-workflows-2026
- https://cordum.io/blog/temporal-vs-langgraph
- https://nirmitee.io/blog/langgraph-crewai-temporal-custom-orchestration-healthcare-agents-2026/

Anthropic harness
- https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents
- https://www.infoq.com/news/2026/04/anthropic-three-agent-harness-ai/
- https://resources.anthropic.com/2026-agentic-coding-trends-report
- https://www.anthropic.com/product/claude-code

Healthcare AI
- https://tateeda.com/blog/agentic-ai-in-healthcare-trends-and-types
- https://atlan.com/know/ai-agent/ai-agent-in-healthcare/
- https://aws.amazon.com/blogs/machine-learning/human-in-the-loop-constructs-for-agentic-workflows-in-healthcare-and-life-sciences/

Event-driven
- https://atlan.com/know/event-driven-architecture-for-ai-agents/
- https://agenticaileadership.com/architecture-and-system-design/event-driven-architecture-in-agentic-ai-system-design/
```

---

*10_RESEARCH_AND_BENCHMARK_2026-05-20.md · 2026-05-20 · Re-read trước Phase 2 design lock. Field evolves fast.*
