# 07 — Context & Memory Rules (Quy tắc context và memory)

> Quy tắc bộ nhớ chung và riêng cho từng khu vực hệ thống — runtime memory + dev session memory.
> Cập nhật: 2026-05-20 · Status: **CANON**

---

## 1. Context tiers — 3 tầng (runtime memory cho graphs/agents)

```
┌──────────────────────────────────────────────────────────────────────┐
│  TIER 1: IMMEDIATE  (per-task, never cache)                          │
│  ───────────────────────────────                                     │
│  - Event vừa trigger (Zalo message, lab result arrival, cron tick)   │
│  - Tool call results trong lượt hiện tại                              │
│  - Decision trace của graph step                                      │
│  - LLM response gần nhất                                              │
│                                                                       │
│  Live in:  LangGraph State (per-run)                                  │
│  TTL:      Run lifetime (~seconds to minutes)                         │
│  Cache:    NEVER. Always fresh.                                       │
│  Persist:  Có (LangGraph checkpoint) cho replay/pause-resume.         │
└──────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌──────────────────────────────────────────────────────────────────────┐
│  TIER 2: OPERATIONAL  (per-shift cache, TTL = shift end)             │
│  ──────────────────────────────────────────                          │
│  - WorkSession: ai on-duty, station map                              │
│  - Active staff capability map                                        │
│  - Current is_training flags                                          │
│  - Open task queue per WorkSession                                    │
│                                                                       │
│  Live in:  In-memory cache (e.g., Redis hoặc in-process LRU)         │
│            HOẶC Postgres view (refresh on shift start)                │
│  TTL:      Until shift end → invalidate.                              │
│  Cache:    YES. Refresh on shift events:                              │
│            shift_start, shift_end, staff_swap, station_change.        │
│  Persist:  Source truth ở work_session + work_session_staff tables.   │
└──────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌──────────────────────────────────────────────────────────────────────┐
│  TIER 3: LONG-TERM  (persistent, selective query)                    │
│  ─────────────────────────────────────                               │
│  - Patient profile + medical history + pregnancy                     │
│  - Visit history + ClinicalRecord                                     │
│  - Lab history                                                        │
│  - Event log (full audit, 7+ years retention)                         │
│  - KB pages + chunks + policy rules                                   │
│  - patient_summary (materialized snapshot)                            │
│                                                                       │
│  Live in:  Supabase tables + pgvector + KB markdown source           │
│  TTL:      Persistent (no expire).                                    │
│  Cache:    Per-query selective; NO blanket cache.                     │
│  Persist:  100%.                                                      │
│                                                                       │
│  RULE: SELECTIVE RETRIEVAL. Không dump toàn bộ patient history vào   │
│        prompt. Query đúng fields cần.                                 │
└──────────────────────────────────────────────────────────────────────┘

KHÔNG bao giờ:
- Cache Immediate context (luôn fresh).
- Dump Long-term toàn bộ vào context window.
- Persist Operational ngoài cache + source truth (no third copy).
- Cross-tier leak (immediate cache leak vào next request).
```

## 2. Memory ở đâu (physical mapping)

```
LangGraph State              → memory in-process per run
LangGraph Checkpoint         → Postgres table (langgraph_checkpoints schema)
Supabase/Postgres            → Domain DB (35 tables, v6 schema)
KB markdown                  → wiki/ (git source of truth)
KB indexed                   → kb_page + kb_chunk + kb_policy_rule (Postgres)
KB vectors                   → kb_chunk.embedding (pgvector HNSW)
EventLog                     → event_log table (append-only, 7+ year retention)
PatientSummary               → patient_summary table (materialized, background-updated)
WorkSession cache            → in-process LRU (per-VPS instance) — invalidate at shift end
TraceContext                 → propagated as parameter (in code), persisted to event_log.trace_id

NOT memory:
- /tmp                       → ephemeral, lose on restart, no source truth
- Python module globals      → no, lose on restart, not persisted
- Agent "private notes"      → cấm (Loại A D038)
- Chat scrollback alone      → not durable; report file is durable
```

## 3. Context Contract — bắt buộc cho mỗi sub-graph/agent

**Loại A D033:** Không build agent mới khi chưa có Context Contract.

**Format:**

```markdown
# Context Contract — <agent_name>

## Owns
What this agent does. 1-2 sentences.

## Trigger
What event/cron/scheduler starts this agent.

## Input context (immediate)
Fields the trigger event must supply:
- event.type
- event.payload.X
- event.payload.Y
- trace_id

## Operational context needed
Data fetched at run start from WorkSession cache:
- current_shift_staff: list[Staff]
- on_duty_doctor_ids: list[UUID]
- station_map: dict[station, staff_id]

## Long-term context needed (selective)
Specific queries fetched per task type:

For task_type = LAB_REVIEW:
- patient_id → patient_summary.last_visit_summary
- visit_id → clinical_record.soap_assessment
- lab_result_id → lab_result.result_data + classification

For task_type = SLOT_FILL:
- waitlist (Top 5 patients with status='WAITING')
- next_available_slot → query work_session within next 7 days

## KB context needed
Pages and policy keys this agent reads:
- kb_policy_rule WHERE policy_key IN ('LAB_REVIEW.sla', 'LAB_REVIEW.routing')
- kb_chunk semantic search if clinical question (with embedding)

## Tools used
Layer 3 tool functions invoked:
- tools.patient.get_summary(patient_id)
- tools.task.assign(task_id, staff_id)
- tools.kb.read_policy(policy_key)
- tools.event_log.append(event_type, payload, trace_id)

## State schema (LangGraph)
TypedDict / Pydantic model definition.

## Refresh policy
- Immediate fields: never cache.
- Operational fields: cache validity 4 hours OR until shift_end.
- Long-term fields: NO cache; query each time.
- KB policy: cache snapshot at task creation (D049 policy_snapshot).

## Invalidation rules
- Operational cache: invalidate on WORK_SESSION_END event.
- KB cache: invalidate on KB_SYNC_COMPLETE event.

## Output
- Side-effects (DB writes, Zalo sends).
- Event_log row emitted.
- Task state updated.
```

**Lưu tại:** `wiki/agent-policy/contracts/<agent_name>.md`.

**Per-agent contract (Phase 1-2 required):**

```
✓ Orchestrator      — generic routing contract.
✓ Communication     — Zalo intent extraction + reply.
✓ Scheduling        — appointment lifecycle.
✓ Lab Triage        — GROUP_C gate enforcement.
✓ Task Manager      — auto-assign + SLA + escalation.
✓ Pre-visit Brief   — 7-field assembly.
○ Voice-to-EMR      — Phase 3, defer.
```

## 4. Context shared giữa các AI tools (dev memory)

```
CLAUDE CHAT          reads:  CLAUDE.md, context/*, final_canon/*, ~/Documents/ClinicAI/*
                     writes: context/*, final_canon/* (updates), .ai/tasks/*

CLAUDE CODE          reads:  CLAUDE.md, task file, listed context files in task
                     writes: src/*, src/tests/*, src/migrations/*, .ai/reports/*
                             Limited context updates (per DoD).

CODEX                reads:  current file + 02_CODING_RULES, CLAUDE.md (intro)
                     writes: in-file edits only

ANTIGRAVITY / KIRO   reads:  CLAUDE.md, dashboard spec, related backend API spec
                     writes: src/dashboard/* only

QWEN local           reads:  task-specific snippet only (≤500 tokens)
                     writes: NOTHING TO GIT (output → temp store, reviewed by Claude Chat)
```

**Shared substrate = git repo + canon docs + KB markdown. Period.**

## 5. Global context files (always-on, every session)

Files Claude Chat / Claude Code MUST read at start of every session:

```
1. CLAUDE.md                                  (root instruction)
2. final_canon/06_HARD_DECISIONS_AND_STYLE.md (locked decisions check)
3. context/CONSTRAINTS.md                     (hard rules)
4. context/CURRENT_ARCHITECTURE_STATE.md      (built vs planned)
```

Skim only (deep-read if task touches that domain):
```
5. final_canon/00_SYSTEM_OVERVIEW.md
6. final_canon/02_CODING_RULES.md
7. context/OPEN_QUESTIONS.md
```

## 6. Task-specific context files

Per-task task file (`T-YYYYMMDD-NN.md`) lists "Context to read FIRST" section. Example:

```
For task involving Patient domain:
- final_canon/05_DATABASE_DESIGN_FINAL.md §3-5 (Patient identity, MPI, Staff)
- ClinicAI_v6_Schema_Memory_1.md §D2 (Patient domain schema)
- wiki/agent-policy/contracts/patient_intake.md (if agent involved)

For task involving Lab Triage:
- final_canon/05_DATABASE_DESIGN_FINAL.md §7 (Lab GROUP_C gate)
- final_canon/06_HARD_DECISIONS_AND_STYLE.md D022 (gate enforcement)
- wiki/clinical/lab/group_classification.md (if exists)
- wiki/agent-policy/contracts/lab_triage.md
```

**Rule:** Task lists context. Implementer reads listed only — không read everything.

## 7. Context compact — khi nào, cái gì, giữ lại

```
KHI NÀO COMPACT (dev session, không runtime):
- Sau mỗi sprint (1-2 tuần).
- Khi PROGRESS.md > 1 page.
- Khi DECISIONS.md > 100 entries (chia thành sub-files).
- Khi OPEN_QUESTIONS.md > 50 entries.
- Khi CURRENT_ARCHITECTURE_STATE.md "GREEN" list > 30 items.

COMPACT CÁI GÌ:
- DECISIONS.md: archive D-### đã marked deprecated/superseded.
- OPEN_QUESTIONS.md: move resolved to DECISIONS.md, archive deferrable >6 months.
- CURRENT_ARCHITECTURE_STATE.md: "DONE" list older than last 2 sprints → archive.
- worklog/: archive worklog older than 30 days to .ai/worklog/_archive/.

GIỮ LẠI (KHÔNG compact):
- CONSTRAINTS.md            (always full).
- 06_HARD_DECISIONS_AND_STYLE.md (always full, this file).
- ARCHITECTURE_SUMMARY.md   (concise, no compact needed).
- DECISIONS.md core         (D001-D060 hôm nay luôn giữ).

UPDATE FORMAT khi compact:
- CHANGELOG.md (root) ghi "2026-XX-XX: compacted DECISIONS, archived D-XXX..D-YYY."
- _archive/YYYY-MM/ chứa version cũ.
- Git history vẫn còn — không xoá nội dung, chỉ archive ngoài hot path.
```

## 8. Đọc lại context trước khi code

```
Mỗi task file phải có "Context to read FIRST" section.

Trước khi viết dòng code:
1. Đọc CLAUDE.md (intro + startup ritual).
2. Đọc task file đầy đủ.
3. Đọc context files được list trong task (chỉ list này, không hơn).
4. Đọc DECISIONS D### được reference (deep-read, not skim).
5. Đọc CONSTRAINTS §C## được reference.
6. Confirm K1 assumptions với Claude Chat.

SAU đó mới code.

NẾU implementer không thấy context cần thiết → STOP, ask Claude Chat refine task.
```

## 9. Cơ chế không dump toàn bộ repo vào LLM

```
SAI: "Cho Claude Code đọc cả repo rồi tự tìm hiểu."
ĐÚNG: Task file curate đúng context files.

RULES:
- Task scope ≤5 file (trừ migration multi-file).
- Context list ≤8 file (combination of canon + KB + code).
- Mỗi context file đọc đúng sections, không full file.

Ví dụ tốt:
"Context to read:
- final_canon/02_CODING_RULES.md §3 (LangGraph style) §7 (Testing)
- final_canon/05_DATABASE_DESIGN_FINAL.md §11 (PatientSummary)
- ClinicAI_v6_Schema_Memory_1.md §D2.3 (PatientMedicalProfile)
"

Ví dụ XẤU:
"Context: read entire ~/Documents/ClinicAI/ folder."
```

## 10. KB / LLM wiki — chi tiết

### 10.1 Single source of truth

```
KB source        = wiki/ markdown trong git.
KB index         = Postgres tables (kb_page, kb_chunk, kb_policy_rule).
KB sync          = one-way: markdown → DB.

Khi diverge:
- markdown WINS absolutely.
- DB re-sync from markdown.
- KHÔNG sửa kb_policy_rule trực tiếp trong DB (D029).
```

### 10.2 KB category retrieval strategies

```
category = 'agent_policy'    → JSONB structured lookup (deterministic)
                                 SELECT rule_data FROM kb_policy_rule
                                 WHERE policy_key = 'LAB_REVIEW.sla.warn'

category = 'clinical'        → pgvector semantic search (MiniLM-L12-v2 384-d)
                                 SELECT * FROM kb_chunk
                                 ORDER BY embedding <=> $query_embedding LIMIT 5

category = 'operations'      → tsvector full-text (Vietnamese tokenizer if available,
                                 else default 'simple')
                                 SELECT * FROM kb_page
                                 WHERE tsvector_content @@ to_tsquery($query)

category = 'faq_internal'    → tsvector or pgvector hybrid (TBD Phase 2)
```

### 10.3 KB governance metadata

```
Mỗi kb_page có:
- owner_role          CLINICAL_LEAD | CLINICAL_DOCTOR | OPS_MANAGER | DEVELOPER
- status              DRAFT | REVIEW | ACTIVE | DEPRECATED
- last_reviewed_at    when last sanity-checked
- review_cycle_days   event-driven, không scheduled (Loại B Session 24)

Dashboard panel "stale KB" list pages where:
- status = ACTIVE AND
- last_reviewed_at < NOW() - INTERVAL '90 days'

→ surfaces to owner_role for review.
```

### 10.4 Markdown front-matter format

```yaml
---
page_key: agent-policy/sla
title: SLA Policy for Task Types
category: agent_policy
owner_role: OPS_MANAGER
status: ACTIVE
last_reviewed_at: 2026-05-20
retrieval_strategy: structured_jsonb
---

# SLA Policy

## LAB_REVIEW
- policy_key: LAB_REVIEW.sla.warn
  rule_data:
    warn_minutes: 90
    breach_minutes: 240
    escalation_chain: [doctor, ops_manager]
- policy_key: LAB_REVIEW.routing
  rule_data:
    primary: doctor_zalo
    fallback_after_minutes: 60
    fallback: ops_manager_zalo

## SLOT_FILL
... etc
```

**Sync job:** parse front-matter → upsert kb_page; parse `policy_key:` blocks → upsert kb_policy_rule; chunk body → kb_chunk + embed.

## 11. Cơ chế chống stale document

```
PROBLEM: doc lỡ stale, AI dùng info cũ → lỗi.

MITIGATION 1 — Sync discipline:
- Mỗi PR ảnh hưởng canon → update canon trong cùng commit (atomic).
- DoD bao gồm "canon updated" checkbox.

MITIGATION 2 — Last-updated visible:
- Mọi canon file có footer: "Last updated: 2026-XX-XX · By: <session-id>"
- Reviewer check: file modified vs git log mismatch → flag.

MITIGATION 3 — Cross-reference verify:
- AI agent khi đọc canon thấy reference [[name]] → verify file exists.
- Stale [[name]] → log warning, không proceed.

MITIGATION 4 — Eval suite catches drift:
- Eval suite (Phase 13) chạy CI mỗi commit.
- Output diverge from canon expectation → fail.

MITIGATION 5 — Quang review weekly:
- Quang glance qua CURRENT_ARCHITECTURE_STATE.md weekly.
- Anything ORANGE lâu hơn 2 tuần → "is this still planned?"
```

## 12. Cơ chế archive version cũ

```
ARCHIVE PATH: _archive/YYYY-MM/<original-path>

Khi archive:
1. Move file vào _archive/YYYY-MM/.
2. Update CHANGELOG.md (root):
   "2026-05-20: archived ClinicAI_SystemOverview.md (superseded by final_canon/00_SYSTEM_OVERVIEW)."
3. Search-and-replace mọi reference → new path (hoặc remove if dead).
4. Commit archive trong commit riêng (không bundle code).

DON'T DELETE — keep for git history + provenance.

ARCHIVE TRIGGERS:
- File superseded by canon.
- File marked STALE-DEPRECATED in INVENTORY.md.
- File >6 months and not referenced.

ARCHIVE DO NOT:
- _audit/* (audit trail, keep).
- _archive/* (already archived).
- src/migrations/*.sql (history).
- src/migrations/*.down.sql (history).
- event_log data (DB).
```

## 13. Cơ chế refresh context khi PM (Quang) đổi hướng

```
SMALL change (1 task, không phá decision):
- Edit task description.
- AI agent re-confirm assumptions.
- Proceed.

MEDIUM change (1 phase, không phá architecture):
- Tạo .ai/change_requests/CR-YYYYMMDD-NN.md.
- Claude Chat impact analysis.
- Update affected tasks.
- Maybe update CURRENT_ARCHITECTURE_STATE.md.
- Proceed after impact ack.

LARGE change (phá architecture, đổi tech stack, đổi safety gate):
- STOP all code.
- Schedule review session.
- Tạo ADR mới (xem 06_HARD_DECISIONS §7 format).
- Update DECISIONS.md, CONSTRAINTS.md.
- Update final_canon/00_SYSTEM_OVERVIEW if needed.
- Update PROGRESS.md.
- Restart Phase plan from affected point.

NEVER:
- Im lặng đổi behavior cũ.
- Skip impact analysis "vì nhỏ thôi."
- Update doc sau khi đã code.
```

## 14. Per-graph context summary

```
ORCHESTRATOR GRAPH
  Immediate: event, trace_id, route decision
  Operational: which sub-graphs are healthy (circuit breaker)
  Long-term: minimal — just dispatch
  KB: minimal — routing rules cached at startup

COMMUNICATION GRAPH
  Immediate: Zalo message text, sender_zalo_id, trace_id
  Operational: current CSKH on-duty list
  Long-term: patient_summary (if sender matches existing patient), recent 5 events
  KB: communication intent classifier prompts + reply templates

SCHEDULING GRAPH
  Immediate: booking request fields (service, preferred date, channel)
  Operational: WorkSession map next 7 days, slot availability
  Long-term: patient.last_visit, prior appointment behavior (no-show rate)
  KB: scheduling policy (priority slots, walk-in handling)

LAB TRIAGE GRAPH
  Immediate: lab_result, classification
  Operational: which doctor is on-duty (for routing notification)
  Long-term: visit context (visit_id linkage), patient pregnancy/conditions
  KB: lab classification rules per test code

TASK MANAGER GRAPH
  Immediate: task creation event, task_type
  Operational: on-duty staff + capability + station + is_training flags
  Long-term: prior task history of involved patient (rare, low priority)
  KB: routing rules, SLA per task_type, escalation chain

PRE-VISIT BRIEF GRAPH
  Immediate: appointment_id, attending_doctor_id, scheduled cron tick
  Operational: doctor's preferred brief format (from staff preference cache)
  Long-term: patient_summary (FULL — this is the source for 7 fields)
  KB: brief template prompt
```

## 15. Anti-drift toolkit (kỹ thuật chống drift giữa AI sessions)

```
1. ALWAYS reference [[D###]] / [[§C##]] / [[Q-N##]] cross-links trong report.
   Not "decision about identity" → use [[D001]].

2. NEVER fabricate file path. Always verify with Read/ls.

3. NEVER quote chat history of previous session. Quote canon file instead.

4. NEVER assume "Quang said X last week." Quote git commit, canon entry, or ask.

5. ALWAYS check timestamp:
   - File modified date matches git log? (No → maybe out-of-band edit.)
   - Decision created in Session N — what was N? Check session log timeline.

6. ALWAYS run /healthcheck on canon docs at session start (auto where possible):
   - Verify CLAUDE.md exists.
   - Verify 12 canon files exist.
   - Verify wiki/ structure.
```

---

*07_CONTEXT_AND_MEMORY_RULES.md · 2026-05-20 · 3-tier runtime + dev session memory + KB governance + anti-drift toolkit.*
