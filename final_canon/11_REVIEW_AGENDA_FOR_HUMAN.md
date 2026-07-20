# 11 — Review Agenda for Human (Quang)

> Sequenced review của 12 canon files cùng Quang trước khi bắt đầu code.
> Mỗi bước: nội dung review, lý do, rủi ro nếu sai, câu hỏi cần trả lời, quyết định cần.
> Cập nhật: 2026-05-20.

---

## 0. Pre-review — Resolve 3 blockers

Trước khi bắt đầu Review Step 1, cần giải quyết:

| Blocker | Nội dung | Yêu cầu từ Quang |
|---------|----------|------------------|
| **B1** Q-V01 | `ClinicAI_v6_FileA.pages` (1.86MB, binary Mac Pages) | Export ra .md/.docx/.pdf. Quyết định: file này là canon mới nhất hay scratch? |
| **B2** Q-V08 | Track A (8 file `Toàn bộ kiến thức dự án/`) vs Track B (v6 schema work) | Quyết định canon path đi tiếp. Đề xuất hybrid: A cho discovery/backlog/KB design, B cho schema. |
| **B3** Q-V09 | Stale files (8 file deprecated) | Approve move sang `_archive/2026-05/`? Hay rename `_DEPRECATED_` prefix? |

**Sau khi B1-B3 resolve**, bắt đầu Step 1.

---

## Step 1 — Hard Constraints

**File:** `final_canon/06_HARD_DECISIONS_AND_STYLE.md` (60 locked decisions) + `context/CONSTRAINTS.md`.
**Time:** 45 phút.

### What to review
- D001-D060: từng decision read text + status (locked / tentative / needs review).
- CONSTRAINTS §C1-C15: identity, channels, adapter, append-only, safety gates, AI boundaries, LangGraph, KB, Domain DB, context, voice, compliance, ops discipline, pre-flight, K1-K4.
- Anti-patterns A-1 to A-40: confirm.
- Always-do B-1 to B-20: confirm.

### Why this first
Constraints là nền móng bất di bất dịch. Sai một constraint thì mọi layer trên đều drift.

### Risk if wrong
- "Constraint" thực ra negotiable → block legitimate design.
- Constraint missing → silent violate trong code → safety/legal incident.
- Wrong priority (style preference next to safety gate) → dilutes both.

### Questions for Quang

1. D001-D060 có decision nào sai text? Status (locked vs tentative) đúng chưa?
2. D040 (Session 33 KB Loại A) — confirm promote.
3. D045 (PatientNextOfKin v6 new) — confirm.
4. D053 (patient_summary materialized) — confirm trade-off acceptable.
5. D058 (crypto-erase Phase 1.5) — confirm tentative.
6. Anti-pattern A-1 to A-40: có ai bị thừa? thiếu?
7. Always-do B-1 to B-20: có ai bị thừa? thiếu?
8. Pre-flight artifact checklist (CONSTRAINTS §C14) đủ chưa? Có thêm gì sau Session 33+?
9. Per-position compensation (D044 tentative prices): khi nào có data đầy đủ Q8?

### Decision needed
- Lock D001-D060 final.
- Approve A-1 to A-40.
- Approve B-1 to B-20.
- Decision for D040, D045, D053, D058.

---

## Step 2 — Final Architecture

**File:** `final_canon/00_SYSTEM_OVERVIEW_AND_FINAL_ARCHITECTURE.md`.
**Time:** 45 phút.

### What to review
- §3 Pain points cốt lõi (P-1 to P-10).
- §4 Tầm nhìn hệ thống production.
- §5 Physical topology Mac Mini / VPS / Supabase / etc.
- §5.1 8 tầng architecture.
- §6 LangGraph layout (Orchestrator + 6 sub-graphs).
- §7 Tech stack rationale (vì sao chọn cái này không chọn cái kia).
- §9 Final Architecture Decisions (FAD-1 to FAD-20).

### Why this second
Sau constraints, architecture là quyết định lớn tiếp theo. Lock layer boundary + sub-graph cut.

### Risk if wrong
- Layer boundaries fuzzy → next implementer guess → tech debt.
- Sub-graph cut sai → graphs tangle, refactor đau.
- Tech stack regret → migration cost high.

### Questions for Quang

1. 8 tầng (Adapter → EventBus → GoldenRecord → DomainDB → Services → Tools → LangGraph → AI → KB → Output) có đúng cách bạn draw?
2. 6 sub-graphs đúng cut? Có nên merge Communication vào Orchestrator? Có nên add 7th Identity Resolution graph (Golden Record currently service, not graph)?
3. Tech stack §7: có item nào muốn renegotiate?
   - MiniLM-L12-v2 vs BGE-M3 (384-d vs 1024-d).
   - RabbitMQ vs Redis Streams (RabbitMQ chọn vì mgmt UI).
   - Caddy vs Nginx (Caddy chọn vì auto-TLS).
4. FAD-1 to FAD-20: lock cả?
5. Adopt Tailscale VPN Mac↔VPS có gì lo ngại không?

### Decision needed
- Lock 8-layer.
- Lock 6 sub-graphs.
- Confirm FAD-1 to FAD-20.

---

## Step 3 — Database Design

**File:** `final_canon/05_DATABASE_DESIGN_FINAL.md` + `ClinicAI_v6_Schema_Memory_1.md`.
**Time:** 60 phút (chia 2 session: D1-D5 + D6-D9).

### What to review
- §1 9 domain · 35 entity (v6 canon).
- §2 Master data build first.
- §3 Patient identity 3-layer (UUID + patient_code + CCCD).
- §4 Staff/Capability/WorkSession + station per session.
- §5 Appointment vs Visit + status machine.
- §6 SOAP + VisitAmendment + voice gate.
- §7 Lab GROUP_A/B/C + GROUP_C gate.
- §8 Task + TaskEvent append-only.
- §9 KB 3 tables (KBPage, KBChunk, KBPolicyRule).
- §10 EventLog append-only.
- §11 PatientSummary materialized vs on-demand.
- §13-18 Migration / seed / fix bug / rollback / dedup strategy.
- §19 So sánh với FHIR, OpenMRS, Salesforce, event sourcing.

### Why this third
Schema = foundation cho mọi service/tool/graph. Get it right before code.

### Risk if wrong
- Sai PK → rework toàn bộ FK chain (cascade pain).
- Sai master data structure → reseed entire system.
- Sai gate placement → safety violation OR over-permissive.
- Sai patient_summary strategy → perf issue OR drift issue.

### Questions for Quang

1. Entity count 35 vs 28 (cũ trong 03_DATA_MODEL): confirm v6 wins.
2. PatientNextOfKin v6 mới — approve schema fields.
3. Q-19 patient_summary materialized vs on-demand: confirm materialized (Recommend §11).
4. Q-23 staff.primary_location_id nullable vs NOT NULL khi HN open?
5. Q-24 inventory per-location vs shared?
6. Q-26 abbreviations (NPĐH/HSS/PRP/CC/SBCD/SOI BTC/TLYK) — khi nào có nghĩa chính xác?
7. Q-27 GROUP_B routing: CSKH trực tiếp hay BS review?
8. Q-28 station ENUM mở rộng (PHLEBOTOMY, MEDICAL_SECRETARY): mở rộng hay giữ Hoa Session 24 list?
9. Migration tool: simple Python runner vs Alembic? (đề xuất simple Python.)
10. Backfill strategy: separate script (đề xuất) vs in-migration?

### Decision needed
- Lock v6 schema 35 entities.
- Resolve Q-19, Q-23, Q-24, Q-27, Q-28.
- Approve migration tool choice.
- Approve seed flow.

---

## Step 4 — Context / Memory Model

**File:** `final_canon/07_CONTEXT_AND_MEMORY_RULES.md`.
**Time:** 30 phút.

### What to review
- §1 3-tier runtime memory (Immediate / Operational / Long-term).
- §2 Physical mapping (LangGraph State, Postgres checkpoint, Supabase, KB).
- §3 Context Contract format + 6 contracts cần build.
- §7 Compact policy (khi nào compact, cái gì giữ).
- §10 KB 3 retrieval strategies.
- §14 Per-graph context summary (6 graphs).

### Why this fourth
Memory model là layer dễ drift trong implementation. "Tôi vừa add patient summary vào context" sound harmless và phá model.

### Risk if wrong
- Operational cache leak across shifts → wrong assignee.
- Long-term dump → cost 4x + quality drop.
- No Context Contract → agent context drift, debugging guesswork.
- Reflective memory creep → audit nightmare.

### Questions for Quang

1. "Shift end" có phải invalidation trigger đúng cho Operational? Hay có sub-shift event (doctor change mid-shift)?
2. patient_summary là Tier 3 hay 4 (per-patient cache)?
3. Context Contract template ở `wiki/agent-policy/contracts/` đúng path?
4. Phase 1 prompt inline trong code vs Phase 10 KB-loaded — boundary OK?
5. KB sync job: GitHub Action webhook trigger có nhanh đủ không (target <30s)?

### Decision needed
- Lock 3-tier memory model.
- Approve Context Contract format.
- Confirm prompt location boundary (Phase 1-9 inline vs Phase 10+ KB).
- Approve KB sync trigger mechanism.

---

## Step 5 — Multi-AI Working Model

**File:** `final_canon/04_MULTI_AI_WORKING_MODEL.md` + `final_canon/03_TASK_DELEGATION_RULES.md`.
**Time:** 30 phút.

### What to review
- §2 Roles per tool (Chat, Code, Codex, Antigravity, Kiro, Qwen).
- §3 One task one owner.
- §4 Không parallel write cùng file.
- §6 Worklog handoff.
- §9 Qwen output review flow.
- §11 Owner matrix (`03_TASK_DELEGATION` §11).
- §13 No autonomous deploy.

### Why this fifth
AI team là cách build mọi feature. Loose roles → tools step on each other.

### Risk if wrong
- 2 AI sửa cùng file → silent merge conflict.
- Codex multi-file refactor → unreviewable.
- Qwen autonomous commit → silent bug.
- No clear escalation → architectural decisions by whoever's prompting.

### Questions for Quang

1. Antigravity vs Kiro scope: tôi đề xuất Antigravity = dashboard chính, Kiro = exploratory. Confirm?
2. Qwen3-14B chạy Mac Mini (48GB đủ?) hay VPS?
3. "Quang-only lock" trên CLAUDE.md / CONSTRAINTS.md / DECISIONS.md — file write permission lock OR convention only?
4. Cost audit cadence monthly OK?
5. CI pipeline: GitHub Actions OK hay khác?
6. Quang manual deploy via SSH OK hay cần friendlier UI (e.g., one-click button)?

### Decision needed
- Lock per-tool roles.
- Lock owner matrix (`03_TASK_DELEGATION` §11).
- Confirm Qwen deployment location.
- Confirm CI/CD setup.

---

## Step 6 — Implementation Roadmap

**File:** `final_canon/01_IMPLEMENTATION_ROADMAP_AND_TASKS.md`.
**Time:** 45 phút.

### What to review
- §1 Senior engineering principles (top-down, bottom-up, vertical slice, etc.).
- §2 13 phases — Phase 0 to Phase 13.
- For each phase: Goal, Prerequisites, Tasks, Files expected, DoD, Tests, Risks, Rollback.
- §3 Change Request framework.
- §5 Quy tắc không code lan man.

### Why this sixth
Roadmap = how we sequence work. Wrong phase order → wasted effort.

### Risk if wrong
- Wrong order (Task Manager before WorkSession) → rework.
- Phase too big → death march.
- Phase too small → no measurable progress.
- DoD vague → "done" claim không verify.

### Questions for Quang

1. 13 phases có phase nào muốn merge/split?
2. Phase 0 expected duration (canon review + setup) realistic?
3. Phase 1-3 (infrastructure + master + patient) trong 3 tuần realistic?
4. Phase 9 sub-graph order: Communication first, Lab Triage 4th. Đổi thứ tự?
5. Phase 12 chờ Zalo OA token từ Quang/Hoa. Khi nào có?
6. Phase 13 hardening cuối có cần timeline cụ thể không? Hay "khi feature đủ thì hardening"?
7. CR framework — small/medium/large boundaries OK?

### Decision needed
- Lock 13 phases sequence.
- Approve Phase 0 duration estimate.
- Confirm CR framework.

---

## Step 7 — Coding Rules

**File:** `final_canon/02_CODING_RULES.md`.
**Time:** 30 phút.

### What to review
- §1 Tech versions cứng.
- §2 Python/FastAPI style (type hints, async-first, Pydantic, DI).
- §3 LangGraph style (typed State, pure-function nodes, tools-as-side-effects, prompts file).
- §4 Service/Tool boundary.
- §5 Error handling + exception hierarchy.
- §6 Logging (structlog JSON, trace_id, no PII).
- §7 Testing (pyramid, naming, negative gate test).
- §8 Migrations (format, discipline, breaking change strategy).
- §9 Config/env.
- §10 Security.
- §11 Naming conventions.
- §12 File organization.
- §13 Forbidden (33 items).
- §14 Mandatory (14 items).

### Why this seventh
Coding rules là contract giữa AI agents. Violate = block PR.

### Risk if wrong
- Loose rules → AI codes drift mỗi session.
- Strict-but-wrong rules → block legitimate code.
- Missing rule → silent anti-pattern slips in.

### Questions for Quang

1. Python 3.12 cứng OK? Hay flexible 3.11+?
2. async-first OK? (Có code sync nào sẽ là exception?)
3. SQLAlchemy 2.0 vs raw asyncpg? Tôi đề xuất SQLAlchemy.
4. Exception hierarchy (ClinicAIError → DomainError → ...) OK?
5. structlog JSON output OK? Hay khác?
6. Test coverage target 80% line OK?
7. File organization tree có gì muốn đổi?

### Decision needed
- Lock tech versions.
- Lock style guidelines.
- Lock file organization.

---

## Step 8 — First Implementation Slice

**File:** `final_canon/08_END_TO_END_SYSTEM_DESIGN.md` §12 + `final_canon/01_IMPLEMENTATION_ROADMAP.md`.
**Time:** 45 phút (this is the productive one — walk out with approved task plan).

### What to review

Tasks Week 1-3 trong `08_END_TO_END §12`:

```
WEEK 1
- T-20260603-01  GitHub repo init structure (Claude Code, 4h)
- T-20260603-02  Commit all canon docs (Quang manual, 30min)
- T-20260603-03  Provision VPS + Supabase project (Quang manual, 2h)
- T-20260603-04  Setup CI pipeline (Claude Code, 4h)
- T-20260603-05  Resolve Q-V01 (Quang export v6_FileA.pages, 30min)

WEEK 2
- T-20260610-01  Migration 001-003: master data (Claude Code, 4h)
- T-20260610-02  Seed master data (Claude Code, 2h)
- T-20260610-03  FastAPI scaffold + /health (Claude Code, 3h)
- T-20260610-04  Migration 004-008: Patient domain (Claude Code, 6h)
- T-20260610-05  patient_service + MPI (Claude Code, 8h)

WEEK 3
- T-20260617-01  Staff + WorkSession migrations (Claude Code, 6h)
- T-20260617-02  Appointment migration + service (Claude Code, 6h)
- T-20260617-03  EventLog migration + trigger (Claude Code, 3h)
- T-20260617-04  Dashboard scaffold (Antigravity, 6h)
- T-20260617-05  RabbitMQ setup + base adapter (Claude Code, 4h)
```

### Why this last
Every previous step feeds vào đây. "Given all that — what do we build first?"

### Risk if wrong
- Wrong P0 → wasted effort.
- Skip foundational (e.g., RabbitMQ) → later tasks break.
- Too much in P0 → death march.
- Too little in P0 → no progress.

### Questions for Quang

1. 15 tasks trong 3 tuần realistic?
2. Tasks nào nên elevate P0 vs P1?
3. Owner assignment đúng (Claude Code default, Antigravity dashboard, Quang manual)?
4. Sprint length 1 tuần vs 2 tuần?
5. Acceptance criteria sample (T-20260603-01) đủ chi tiết?
6. Demo end of Week 3 (vertical slice mock Zalo → Pancake → MPI → Patient → Dashboard) viable?

### Output of this step
A set của `.ai/tasks/20260603_T-NN_<slug>.md` files, một per approved task, ready dispatch to Claude Code.

### Decision needed
- Approve 15 tasks Week 1-3.
- Owner per task.
- Sprint duration.
- Demo target Week 3.

---

## Cross-cutting items

Items không thuộc một step nhưng quan trọng:

```
- Glossary review: "ClinicAI" tên đúng chưa? Tách `context/GLOSSARY.md`?
- Versioning policy: "Last updated:" header (current) vs date in filename vs git tag?
- ONBOARDING.md cho new dev (AI hoặc human)?
- Compliance handoff: khi nào hire Vietnamese healthcare lawyer review NĐ13/2023?
- Mac Mini deployment plan: Phase 1 dev only? Phase 2 prod-fallback?
- Backup strategy concrete plan (Q-N07)?
- Production secret management: HashiCorp Vault vs AWS Secrets vs file-based env?
```

Slot vào bước phù hợp HOẶC batch riêng "Hygiene session."

## Suggested calendar

```
Tuần 1
  Mon AM   Pre-review B1-B3 resolve
  Mon PM   Step 1 — Hard Constraints
  Tue AM   Step 2 — Final Architecture
  Tue PM   Step 3 (part 1) — DB Design D1-D5
  Wed AM   Step 3 (part 2) — DB Design D6-D9
  Wed PM   Step 4 — Context / Memory Model

Tuần 2
  Mon AM   Step 5 — Multi-AI Working Model
  Mon PM   Step 6 — Implementation Roadmap
  Tue AM   Step 7 — Coding Rules
  Tue PM   Step 8 — First Slice planning
  Wed      Hygiene session + cross-cutting items
  Thu      Start build (Claude Code T-20260603-01)
```

Nếu Quang muốn rút gọn: collapse Step 4 vào Step 3, Step 6 vào Step 7. Còn 5 review sessions thay vì 8.

## Những chỗ TÔI CHƯA CHẮC (highlight cho Quang)

```
H-1   v6 schema vs 03_DATA_MODEL số entities không khớp (35 vs 28).
      Tôi chọn v6 wins. Cần Quang confirm.

H-2   `ClinicAI_v6_FileA.pages` chưa đọc được (binary).
      Không biết nội dung có gì mới hơn v6_Schema_Memory_1.md.

H-3   Q-V05: Session 33 KB decisions trong ConstraintMap §5 đã merge vào 04_KB chưa?
      Tôi treat như đã merge nhưng cần verify.

H-4   D053 patient_summary materialized — đề xuất, chưa Quang approve.

H-5   D058 crypto-erase Phase 1.5 — design draft chưa.

H-6   Q-N06: KB CMS cho Hoa edit markdown (non-dev).
      Phase 2 vấn đề mở.

H-7   Q-N08: Antigravity vs Kiro boundary chính xác.
      Tôi đề xuất Antigravity = dashboard, Kiro = exploratory. Confirm?

H-8   Q-N09: Qwen local trên Mac Mini hay VPS?
      Mac Mini 48GB đủ cho Qwen3-14B (Q4 quant ~9GB). Confirm.

H-9   Q-N10: Observability stack Phase 2 (Loki/Grafana vs Sentry vs Datadog)?

H-10  Q-N11: Checkpoint cleanup TTL 30 days hợp lý?

H-11  Q-23: Staff fixed location vs rotate khi HN open?
      Schema flexible cả 2; cần Quang quyết để set primary_location_id nullable/NOT NULL.

H-12  Q-26: Clinic abbreviations meaning (NPĐH, HSS, PRP, CC, SBCD, SOI BTC, TLYK).
      Không đoán; cần ask phòng khám.

H-13  Q-27: GROUP_B routing — CSKH trực tiếp hay BS review?
      Affects Lab Triage Graph logic.

H-14  Q-28: Station ENUM mở rộng?
      Hoa Session 24 simplified list vs full ENUM với PHLEBOTOMY, MEDICAL_SECRETARY.
```

## What I'm NOT proposing

```
- Không relitigate locked decisions (D001-D060 trừ những marked "needs review").
- Không design entity/schema mới trong review này. v6 là canon.
- Không code trong review (Step 8 produces task assignments, không code).
- Không external stakeholder calls (BS Thành, Hoa) yet — downstream sau khi
  biết hỏi gì cụ thể.
```

---

*11_REVIEW_AGENDA_FOR_HUMAN.md · 2026-05-20 · 8-step sequence. Pre-review blockers B1-B3 gate everything.*
