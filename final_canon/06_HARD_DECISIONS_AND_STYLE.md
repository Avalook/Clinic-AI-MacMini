# 06 — Hard Decisions & Style (Quyết định cứng + phong cách không vi phạm)

> File này **THẮNG TUYỆT ĐỐI** khi mâu thuẫn với file khác.
> Khi Claude Code/Codex/Antigravity/Qwen thấy task vi phạm file này → STOP, escalate.
> Cập nhật: 2026-05-20 · Status: **CANON-LOCK**

---

## 1. Locked decisions — Quyết định cứng (50 entries)

Format: **D###** · Decision · Rationale (1 dòng) · Source · Status (locked / tentative / needs review).

### Architecture core

```
D001  clinic_patient_id (UUID) là PK BẤT BIẾN duy nhất của Patient.
      Rationale: SĐT là tài sản nhà mạng — không kiểm soát được.
      Source: CLAUDE.md Loại A Session 4+31.
      Status: locked.

D002  national_id_number (CCCD) NULLABLE + partial UNIQUE; override SĐT khi present.
      Rationale: CCCD là identity strongest nhà nước; nullable vì gradual collection.
      Source: CLAUDE.md Loại A Session 31.
      Status: locked.

D003  patient_code BN-YYYY-XXXXXX là human identifier.
      Rationale: UUID không đọc qua điện thoại, không in thẻ được.
      Source: CLAUDE.md Loại A Session 13.
      Status: locked.

D004  Patient.phone giữ TRONG Patient table song song với PatientContactChannel.
      Rationale: phone = identity anchor verify; PatientContactChannel = routing.
      Source: CLAUDE.md Loại A Session 28.
      Status: locked.

D005  PatientContactChannel channel-agnostic (Zalo, Phone, FB, Email, ...).
      Rationale: hardcode "chỉ Zalo" tạo tech debt khi mở kênh mới.
      Source: CLAUDE.md Loại A Session 28.
      Status: locked.

D006  Adapter chỉ emit InteractionEvent. Golden Record Engine ghi Domain DB.
      Rationale: identity resolution global, single writer = single audit point.
      Source: CLAUDE.md Loại A Session 4.
      Status: locked.

D007  EventLog APPEND-ONLY. Không UPDATE/DELETE. Không trigger làm audit.
      Rationale: DB trigger as audit = silent + schema-coupled anti-pattern.
      Source: CLAUDE.md Loại A Session 4.
      Status: locked.

D008  6 append-only tables + DB trigger enforce_append_only().
      Rationale: defense-in-depth, application bug không mutate history được.
      Source: v6 Schema Principle 2.
      Status: locked.
      List: event_log, task_event, visit_amendment, drug_inventory_transaction,
            supply_inventory_transaction, FINALIZED visit.

D009  FINALIZED visit IMMUTABLE; chỉ tạo VisitAmendment.
      Rationale: TT13/2011/TT-BYT yêu cầu immutability sau khi đóng hồ sơ.
      Source: CLAUDE.md Loại A Session 13.
      Status: locked.

D010  Zalo OA = only patient channel. Zalo OA Internal = only staff channel.
      Rationale: app riêng thử và thất bại (Loại B Session 10).
      Source: CLAUDE.md Loại A Session 10.
      Status: locked.

D011  PhoWhisper on-premise; audio không rời clinic.
      Rationale: NĐ13/2023 + clinical confidentiality.
      Source: CLAUDE.md Loại A.
      Status: locked.

D012  KHÔNG AI chatbot tư vấn lâm sàng cho BN.
      Rationale: ranh giới pháp lý VN — clinic chịu trách nhiệm thay nếu AI sai.
      Source: CLAUDE.md Loại A.
      Status: locked.

D013  KHÔNG risk-scoring AI cho đến ≥50.000 thai kỳ + outcomes.
      Rationale: dưới N này, model unreliable; 1 lỗi mất tin tưởng BS vĩnh viễn.
      Source: CLAUDE.md Loại A.
      Status: locked.

D014  Tech stack: LangGraph 1.0 + FastAPI + Supabase Cloud + RabbitMQ +
      Anthropic Claude Sonnet/Haiku + Qwen3-14B local + PhoWhisper + MiniLM-L12-v2.
      Rationale: từng item đã decisive review trong 00_SYSTEM_OVERVIEW §7-8.
      Source: ConstraintMap §5 Session 29 + Quang prompt 2026-05-20.
      Status: locked.

D015  Cost-aware AI routing: trivial → Qwen local, simple → Haiku, complex → Sonnet.
      Target 60-70% cost reduction vs Sonnet-only.
      Rationale: small clinic can't pay enterprise bills.
      Source: CLAUDE.md Loại A.
      Status: locked.

D016  LangGraph là orchestration layer, KHÔNG phải toàn bộ system.
      Rationale: AI trong node là cost + non-determinism risk.
      Source: Quang prompt 2026-05-20.
      Status: locked.

D017  Orchestrator Graph + 6 sub-graphs (Scheduling, Lab Triage, Task Manager,
      Communication, Pre-visit Brief, Voice-to-EMR Phase 2).
      Rationale: mega-graph unmaintainable.
      Source: Quang prompt 2026-05-20.
      Status: locked.

D018  Memory split: short-term = LangGraph State + checkpoint; long-term = Supabase + KB.
      Rationale: graph state ephemeral by design.
      Source: Quang prompt 2026-05-20.
      Status: locked.

D019  Master data tables (ClinicLocation, ServiceType, BookingChannel) KHÔNG ENUM cứng.
      Rationale: clinics evolve catalog faster than dev cycles.
      Source: CLAUDE.md Loại A Session 29.
      Status: locked.

D020  Staff multi-role via staff_capability junction. Station per-session.
      Rationale: VN clinics need multi-role; capability ≠ station.
      Source: CLAUDE.md Loại A Session 29.
      Status: locked.

D021  Multi-site location_id BẮT BUỘC mọi operational entity.
      Rationale: KN + HN active; thêm location_id sau = backfill nhiều bảng.
      Source: CLAUDE.md Loại B Session 29 → enforce A.
      Status: locked.

D022  GROUP_C lab gate: CSKH KHÔNG được notify BN khi bs_reviewed_at IS NULL.
      Application layer enforce, không chỉ convention.
      Rationale: thực tế hiện tại CSKH báo abnormal trước BS review = clinical risk.
      Source: CLAUDE.md Loại B Session 19+24 → enforce A.
      Status: locked.

D023  is_training staff KHÔNG auto-assign task.
      Rationale: trainee không carry standalone responsibility.
      Source: CLAUDE.md Loại B Session 29.
      Status: locked.

D024  Lab notification batch model (không SLA countdown cứng).
      Rationale: clinic culture batch, không countdown alerts.
      Source: CLAUDE.md Loại B Session 24.
      Status: locked.

D025  Pre-visit Brief: 9 fields = 7 clinical core (BS Hùng) + 2 AI scaffolding.
      7 core (chờ BS Thành P2 sign-off tên chính xác): key_points, follow_up_items,
      pending_reviews, medications, allergies, pregnancy_context, risk_flags.
      2 scaffolding (AI-generated, không cần BS duyệt): headline, suggested_questions.
      Ultrasound + next-appointment hòa vào core fields qua LLM, không có slot riêng.
      Rationale: BS Hùng confirm 7 core Session 24; 2 scaffolding là UX đọc nhanh.
      Source: CLAUDE.md Loại B Session 24 + code verify P9.7c (9d9b3b0).
      Status: tentative (pending BS Thành Phase 2 sign-off tên 7 core).

D026  CSKH intake 5 fields khi BN lần đầu liên hệ.
      Rationale: BS Hùng baseline standard.
      Source: CLAUDE.md Loại B Session 24.
      Status: locked.

D027  Appointment vs Visit là 2 entity riêng.
      Rationale: walk-in (no appointment) + no-show (no visit).
      Source: CLAUDE.md Loại A.
      Status: locked.

D028  Drug ≠ Supply. 2 transaction tables riêng.
      Rationale: different triggers, FKs, billing exposure.
      Source: CLAUDE.md Loại A Session 28.
      Status: locked.

D029  KB markdown = source of truth. PostgreSQL = queryable index. Sync one-way.
      Rationale: markdown gives version control + diff + audit trail.
      Source: CLAUDE.md Loại A Session 8 + Session 33.
      Status: locked.

D030  KB 3 retrieval strategies: agent_policy → JSONB; clinical → pgvector; operations → tsvector.
      Rationale: agent policy phải deterministic; clinical conceptual; ops procedural.
      Source: ConstraintMap §5 Session 33.
      Status: locked.

D031  KB ownership role-based (CLINICAL_LEAD, CLINICAL_DOCTOR, OPS_MANAGER, DEVELOPER).
      Rationale: named-person ownership tạo orphan khi staff leave.
      Source: ConstraintMap §5 Session 33.
      Status: locked.

D032  Context 3-tier: Immediate (no cache), Operational (cache + shift TTL), Long-term (selective).
      Rationale: dump all = 4x cost + quality degrade 84% benchmark.
      Source: Context Engineering Research Session 18.
      Status: locked.

D033  Context Contract bắt buộc trước khi build agent mới.
      Rationale: agent without contract → generic decision instead of context-specific.
      Source: Context Engineering Research Session 18.
      Status: locked.

D034  BN trả ngay sau visit. Không deposit, không debt, không installment.
      Phương thức: CK + TM + Momo + VNPay + Mixed.
      Rationale: confirmed Session 24.
      Source: CLAUDE.md Loại B Session 24.
      Status: locked.

D035  Migration parallel-run + rollback plan. Không big-bang.
      Rationale: clinic đã mất data khi đổi phần mềm trước.
      Source: CLAUDE.md Loại B Session 10.
      Status: locked.

D036  Hoa hard constraint: KHÔNG PHÁT SINH THÊM task.
      Net staff effort ≤ 0 (ideally -1: feature subtracts step before adds).
      Rationale: deployment blocker.
      Source: CLAUDE.md Loại B Session 19.
      Status: locked.

D037  Mac Mini local AI = worker, KHÔNG critical path.
      Failover: Qwen down → Haiku → Sonnet.
      Rationale: 1 hardware = SPOF risk.
      Source: Quang prompt 2026-05-20.
      Status: locked.

D038  Git = shared memory cho tất cả AI agents. KHÔNG private memory.
      Rationale: silent drift, repeated work, conflict.
      Source: Quang prompt 2026-05-20.
      Status: locked.

D039  AI team roles: Chat=planner/reviewer, Code=executor, Codex=IDE quick-fix,
      Antigravity/Kiro=UI/browser, Qwen=cheap worker. Git/tests=arbitrator.
      Rationale: sweet spot per tool; forcing wastes tokens.
      Source: Quang prompt 2026-05-20.
      Status: locked.

D040  Session 33 KB design = Loại A (mặc dù source file marked "Draft").
      ConstraintMap đã promote.
      Source: ConstraintMap §5 Session 33.
      Status: needs review (verify 04_KB has Session 33 fully merged).

D041  ClinicalRecord.voice_note_reviewed BOOL gate.
      Voice transcript chưa review → draft, không phải clinical content final.
      Rationale: PhoWhisper good không perfect.
      Source: v6 Schema D3.2.
      Status: locked.

D042  Visit denormalizes location_id + service_type_id (frozen at visit time).
      Rationale: reporting performance + historical accuracy.
      Source: v6 Schema D3.1.
      Status: locked.

D043  service_type pre-allocate loinc_code + snomed_code columns (nullable).
      Phase 2 sẽ populate.
      Rationale: column add cheap, cross-system mapping expensive later.
      Source: v6 Schema D1.2.
      Status: locked.

D044  CSKH compensation 5 tags: CSKH_CALL, CSKH_CONFIRM, CSKH_NOTIFY, CSKH_ADMIN, (+1 historical).
      Per-tag unit price unknown (Q-08 OPEN).
      Source: CLAUDE.md Loại B Session 29.
      Status: locked (categories); tentative (prices).

D045  PatientNextOfKin entity riêng (1 BN : N người nhà).
      Rationale: OB-GYN context multi-family-contact norm.
      Source: v6 Schema D2.5.
      Status: locked.

D046  LabPartner entity (Diag, Medlatec). FK from LabOrder + LabResult.
      Rationale: ENUM "DIAG" tạo tech debt khi thêm partner.
      Source: v6 Schema D5.1.
      Status: locked.

D047  KB schema 3 tables: KBPage + KBChunk (pgvector) + KBPolicyRule (JSONB).
      Rationale: 1 table không index well cho 3 retrieval shapes.
      Source: v6 Schema D9.
      Status: locked.

D048  TaskEvent append-only history.
      Rationale: audit + escalation analytics + replay debug.
      Source: v6 Schema D6.2.
      Status: locked.

D049  Task policy_snapshot JSONB at creation.
      KB rule changes không retroactive cho task đã tạo.
      Rationale: prevent silent SLA breach.
      Source: v6 Schema D6.1.
      Status: locked.

D050  9 booking channels confirmed từ data (1.974 records Session 29).
      Zalo PK, Zalo Dr, FB Dr4women, FB 4women Clinic, FB 4women Academy,
      Hotline, TikTok BS Thành, CSKH gọi chủ động, BS giới thiệu.
      Source: CLAUDE.md Loại B Session 29.
      Status: locked.

D051  Python 3.12.x cứng. Không 3.11. Không 3.13.
      Rationale: avoid "works on my machine" — single source.
      Source: Quang prompt + 02_CODING_RULES §1.
      Status: locked.

D052  Patient self-booking via Zalo defer Phase 2 (sau Zalo OA token).
      Rationale: Phase 1 focus internal workflow.
      Source: PROGRESS.md.
      Status: locked.

D053  patient_summary = MATERIALIZED background job (resolve Q-19).
      Rationale: brief = 1 SELECT vs 5 SELECTs on-demand; 60s drift acceptable.
      Source: 05_DATABASE_DESIGN_FINAL §11 RECOMMEND.
      Status: needs review (Quang confirm).

D054  trace_id UUID propagate adapter → bus → graph → service → event_log.
      Rationale: end-to-end debug discipline.
      Source: best practice + 02_CODING_RULES §6.2.
      Status: locked.

D055  Failing test BEFORE bug fix. Negative test for every safety gate.
      Rationale: regression prevention.
      Source: 02_CODING_RULES §7.3.
      Status: locked.

D056  No production deploy autonomously by AI. Quang manual deploy only.
      Rationale: compliance accountability.
      Source: 04_MULTI_AI_WORKING_MODEL §13.
      Status: locked.

D057  Eval suite mandatory Phase 13: 50 golden Zalo messages + 20 lab + 5 brief.
      Run CI mỗi commit; fail eval → block merge.
      Rationale: prevent silent quality drift.
      Source: 01_IMPLEMENTATION_ROADMAP P13.
      Status: locked.

D058  Crypto-erase pattern for NĐ13/2023 right-to-forget (Phase 1.5).
      Encrypt PII columns; drop key = forget; audit row immutable.
      Rationale: append-only conflicts right-to-forget; crypto-erase resolves.
      Source: 00_SYSTEM_OVERVIEW §10 Compliance.
      Status: tentative (Phase 1.5 design pending).

D059  Pancake adapter MVP; native Zalo OA SDK Phase 2.
      Rationale: Pancake đã trong workflow, native là roadmap.
      Source: CLAUDE.md Loại A Session 4.
      Status: locked.

D060  KiotViet integration (read invoices). Không thay thế MVP.
      Rationale: KiotViet handle POS + payroll calc — out of MVP scope.
      Source: CLAUDE.md Loại B Session 10.
      Status: locked.
```

## 2. Anti-patterns — KHÔNG bao giờ làm

```
A-1  AI quyết safety gate (GROUP_C, FINALIZED, is_training, voice_review).
A-2  Mega-graph (1 LangGraph cho mọi workflow).
A-3  Multi-tenant generalize sớm (single-tenant Dr4women).
A-4  Microservices fan-out cho 1-VPS deployment.
A-5  Reflective memory (agent self-learning) trong y tế.
A-6  Long-context "dump everything" thay vì selective retrieval.
A-7  Multiple AI agents parallel write cùng DB row.
A-8  Hardcode business rule trong code thay vì KB.
A-9  Adapter ghi thẳng Domain DB.
A-10 Phone là PK/FK của Patient.
A-11 ENUM hardcode cho ServiceType/BookingChannel/LabPartner.
A-12 UPDATE FINALIZED visit row.
A-13 DELETE từ append-only table.
A-14 Audio cloud STT (PhoWhisper local only).
A-15 Telegram/SMS/email fallback (Zalo only).
A-16 Notion API as runtime KB (markdown source).
A-17 Sửa schema production qua Supabase Dashboard.
A-18 Commit secret vào git.
A-19 print() trong production code.
A-20 except Exception quá rộng.
A-21 dict[str, Any] trong API response.
A-22 Tool gọi Tool khác.
A-23 Graph node gọi DB trực tiếp.
A-24 Service contain prompt inline.
A-25 Migration không có DOWN script.
A-26 PR --no-verify skip pre-commit.
A-27 Codex/Antigravity tạo task mới (chỉ Claude Chat).
A-28 Qwen autonomous commit/PR.
A-29 Refactor adjacent code khi fix bug (K3).
A-30 Skip CONSTRAINTS check khi tạo artifact.
A-31 Skip Context Contract khi build agent mới.
A-32 Build Task routing trước WorkSession entity.
A-33 Build graph trước khi tools đầy đủ.
A-34 Sync DB call trong async handler.
A-35 time.sleep() trong test.
A-36 log PII vào application logs.
A-37 Force NOT NULL trên column đã có data.
A-38 Use SQL string interpolation (injection risk).
A-39 Bypass RLS với service-role key thay user.
A-40 Branch không có corresponding task ID.
```

## 3. Always do (Quy tắc bắt buộc)

```
B-1  Type hints đầy đủ Python.
B-2  Pydantic schema cho mọi API I/O.
B-3  Migration có DOWN script.
B-4  Negative test cho mọi safety gate.
B-5  trace_id propagation end-to-end.
B-6  event_log row cho mọi mutation.
B-7  Pre-commit hooks pass.
B-8  CI green trước merge.
B-9  Report sau mỗi task.
B-10 Context Contract trước khi build agent mới.
B-11 K1 K2 K3 K4 (Karpathy).
B-12 Update canon doc khi state thay đổi.
B-13 Master data build TRƯỚC mọi domain entity.
B-14 WorkSession build TRƯỚC Task Manager.
B-15 SOAP schema có cấu trúc TRƯỚC Voice-to-EMR.
B-16 Snapshot SLA policy at task creation.
B-17 Sub-graph có State riêng + checkpoint riêng.
B-18 Tool deterministic; AI ambiguous only.
B-19 KB markdown source; DB index.
B-20 Sequential commit (no merge bomb).
```

## 4. Pre-flight checklist — TRƯỚC khi code

```
Trước khi viết dòng code nào, AI agent phải confirm:

[ ] Đã đọc CLAUDE.md.
[ ] Đã đọc task `.ai/tasks/T-YYYYMMDD-NN.md`.
[ ] Đã đọc context files được list trong task.
[ ] Đã đọc DECISIONS.md cho D### relevant.
[ ] Đã đọc CONSTRAINTS.md §C## relevant.
[ ] Đã confirm assumption (K1) với Claude Chat / Quang.
[ ] Đã hiểu scope in-scope vs out-of-scope.
[ ] Đã hiểu Acceptance Criteria measurable.
[ ] Đã biết test sẽ viết là gì.
[ ] Đã biết safety gate test (nếu có).
```

## 5. Pre-flight checklist — TRƯỚC khi tạo artifact (HTML/PPTX/diagram/docx/pdf)

(Repeat từ CONSTRAINTS §C14, vì pre-flight này quan trọng nhất.)

```
[ ] Output channels: KHÔNG Telegram. → Zalo OA.
[ ] Staff interface: KHÔNG "App/Tablet/Web for staff." → Zalo OA Internal.
[ ] Patient interface: KHÔNG "Own app for patients." → Zalo OA.
[ ] Billing: chỉ GAP, không detail schema (chờ Q8/Q9).
[ ] Primary key: KHÔNG phone. → clinic_patient_id.
[ ] Patient identifier in UI: KHÔNG UUID. → patient_code (BN-YYYY-XXXXXX).
[ ] Adapter: KHÔNG direct arrow Adapter → Domain DB. → Event Bus + Layer 0C.
[ ] Invoice: KHÔNG Supply on line items. → Drug only.
[ ] Visit edit: KHÔNG UPDATE FINALIZED. → VisitAmendment flow.
[ ] Location: KHÔNG single-site assumption. → location_id (KN + HN).
[ ] Service/Channel: KHÔNG hardcoded ENUM. → master data table reference.
[ ] Abbreviations (NPĐH/HSS/PRP/CC/SBCD/SOI BTC/TLYK): KHÔNG đoán nghĩa.
[ ] KB owner: KHÔNG named person. → role.
[ ] KB policy rule: KHÔNG direct DB edit. → markdown + sync.
```

## 6. Pre-flight checklist — TRƯỚC khi schema change

```
[ ] Có task ID associated (T-YYYYMMDD-NN).
[ ] Migration file format đúng (YYYYMMDD_NNN_<desc>.sql + .down.sql).
[ ] DOWN script test rollback clean local.
[ ] Idempotent (IF NOT EXISTS / IF EXISTS).
[ ] Trong BEGIN/COMMIT transaction.
[ ] Comment table + complex column.
[ ] Test applied locally + verify schema state.
[ ] Breaking change? → 30-day backward compat plan.
[ ] Backfill script (if needed) separate, not in migration.
[ ] Quang approval cho production apply.
```

## 7. Decision record format (cho ADR mới)

```markdown
# ADR-YYYYMMDD-NN — <title>

## Status
Proposed | Accepted | Superseded by ADR-XXX | Deprecated

## Context
<What problem are we solving? Why now? What's at stake?>

## Decision
<What we will do. Crisp.>

## Rationale
<Why this and not alternatives.>

## Alternatives considered
- Option A: <pro/con>
- Option B: <pro/con>
- Option C: <pro/con>

## Consequences
### Positive
- ...
### Negative
- ...
### Neutral / trade-off
- ...

## Compliance / safety implications
<Affects any safety gate? Compliance? PHI handling?>

## Affected files / decisions
- D###, D### (DECISIONS.md to update)
- §C## (CONSTRAINTS.md to update)
- src/clinicai/... (code areas affected)

## Source
- Conversation date + participants
- Survey / interview reference
- Industry source if benchmark

## Owner
<Person responsible to keep this current>

## Change process
This ADR changes only via:
1. New ADR superseding.
2. Quang explicit override (recorded in DECISIONS.md).

NOT via silent code edit or chat consensus.
```

## 8. Decisions cần Quang review

```
NEEDS-REVIEW từ canon work hôm nay:

D025 Pre-visit Brief 7 fields  — chờ BS Thành Phase 2 sign-off.
D040 Session 33 KB Loại A      — verify 04_KB merged.
D053 patient_summary materialized — confirm trade-off.
D058 Crypto-erase pattern Phase 1.5 — design draft pending.

OPEN BLOCKERS:
Q-V01  ClinicAI_v6_FileA.pages content — Quang export cần thiết.
Q-V08  Track A (00-07) vs Track B (v6) precedence — confirm canon path.
Q-V09  Archive policy cho stale files — approve _archive/2026-05/.

BUSINESS QUESTIONS chờ phòng khám:
Q-08   Per-position compensation formula.
Q-09   Package services.
Q-17   Context Contract LAB_REVIEW fields.
Q-19   patient_summary strategy (recommend materialized — confirm).
Q-20   Doctor free-window cho batch lab reminder.
Q-23   Staff fixed location vs rotate khi HN open.
Q-26   Clinic abbreviation meanings.
Q-27   GROUP_B routing (CSKH trực tiếp hay BS review?).
Q-28   Station ENUM mở rộng.
```

## 9. Quy tắc precedence final

```
HARDEST → SOFTEST:

1. Hard safety gate (D009, D022, D023, D041) — application + DB enforce.
2. Identity rules (D001-D005) — schema level.
3. Adapter / Golden Record / Event Log rules (D006-D008) — architectural.
4. Locked decisions (D001-D060) — file 06_HARD_DECISIONS_AND_STYLE.md.
5. Hard constraints (CONSTRAINTS.md §C##).
6. Coding rules (02_CODING_RULES.md).
7. Tentative decisions — re-evaluate when new info.
8. Recommendations (RECOMMEND-1..10) — sensible default, can adjust.
9. Open questions — surface, don't guess.

If conflict between layer N và N+1, N wins.
If conflict within same layer, escalate Quang.
```

---

*06_HARD_DECISIONS_AND_STYLE.md · 2026-05-20 · 60 locked decisions + 40 anti-patterns + 20 always-do + 6 pre-flight checklists. WINS WHEN CONFLICT.*
