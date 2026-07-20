# 03 — Task Delegation Rules (Quy tắc giao task cho AI agents)

> Quy tắc giao task chính xác cho Claude Code, Codex, Antigravity/Kiro, Qwen local.
> Cập nhật: 2026-05-20 · Status: **CANON**

---

## 1. Task packet format (chuẩn giao task)

Mỗi task lưu ở `.ai/tasks/T-YYYYMMDD-NN.md`:

```markdown
# T-YYYYMMDD-NN — <imperative title in English>

## Metadata
- **Assigned to:** Claude Code | Codex | Antigravity | Kiro | Qwen
- **Priority:** P0 (blocker) | P1 (important) | P2 (nice-to-have) | P3 (backlog)
- **Phase:** P<N> (theo 01_IMPLEMENTATION_ROADMAP)
- **Created by:** Claude Chat | Quang
- **Created at:** YYYY-MM-DD HH:MM
- **Estimated:** S (<2h) | M (2-6h) | L (6h-2d) | XL (split this!)
- **Depends on:** T-..., T-... (other task IDs)

## Goal (1-2 câu)
<Outcome description, không phải step list>

## Why (linking)
<Link to DECISIONS D###, CONSTRAINTS §C##, OPEN_QUESTIONS Q-... hoặc CURRENT_ARCHITECTURE_STATE>

## Scope

### In-scope (mọi file được phép sửa)
- src/clinicai/services/patient_service.py
- src/clinicai/tools/patient/find_by_phone.py
- src/tests/services/test_patient_service.py
- src/migrations/20260521_002_patient.sql

### Out-of-scope (KHÔNG động vào)
- src/clinicai/adapters/* (separate task)
- wiki/* (no KB edit in this task)
- Bất kỳ file ngoài in-scope list ở trên

## Context to read FIRST (ngược thứ tự ưu tiên)
1. CLAUDE.md
2. final_canon/06_HARD_DECISIONS_AND_STYLE.md (entire file)
3. final_canon/02_CODING_RULES.md §3 (LangGraph) §7 (Testing)
4. final_canon/05_DATABASE_DESIGN_FINAL.md §3 (Patient identity)
5. final_canon/07_CONTEXT_AND_MEMORY_RULES.md §3 (Context contract)
6. ClinicAI_v6_Schema_Memory_1.md §D2 (Patient domain)

## Acceptance criteria (measurable)
- [ ] Migration `20260521_002` apply + rollback clean.
- [ ] Test `test_patient_service__create_with_existing_phone__creates_with_warning` pass.
- [ ] Test `test_mpi__cccd_match_overrides_phone__returns_existing` pass.
- [ ] No file outside in-scope list modified (verified via `git diff --name-only`).
- [ ] Pre-commit hooks pass.
- [ ] CI green.
- [ ] Report filed at `.ai/reports/T-20260601-01.md`.

## Constraints to respect
- §C1 Identity rules (clinic_patient_id PK, CCCD partial unique).
- §C3 Adapter boundary (don't write to DB from adapter).
- §C15 K1-K4 Karpathy.

## Decisions referenced
- D001 clinic_patient_id is the only PK
- D002 national_id_number nullable + partial unique
- D004 Patient.phone stays as identity anchor
- D005 PatientContactChannel channel-agnostic

## Assumptions to confirm BEFORE coding (K1)
Implementer MUST reply with confirmation or pushback before writing code:

1. patient_code format = "BN-YYYY-XXXXXX" where YYYY = current year, XXXXXX = 6-digit sequential.
2. MPI confidence threshold for auto-merge = 0.95; below → Human Review Queue.
3. CCCD match (when both have CCCD) overrides phone match.

## Open questions that might block
- Q-26 (clinic abbreviations) — not blocking for this task.
- Q-29 (5K vs 10K record discrepancy) — not blocking.

## Definition of Done
- [ ] All AC pass.
- [ ] All existing tests still pass (`pytest --no-cov`).
- [ ] No drive-by changes (verify K3).
- [ ] `.ai/REPORT_TEMPLATE.md` filed.
- [ ] If decision changed: DECISIONS.md updated.
- [ ] If open question surfaced: OPEN_QUESTIONS.md updated.
- [ ] If state changed (ORANGE → GREEN): CURRENT_ARCHITECTURE_STATE.md updated.
- [ ] Reviewer (Claude Chat) signed off.
- [ ] Merged to main OR PR open with green CI.

## Notes from author
<Bất cứ gì implementer cần biết mà không phải "what to do">
```

## 2. Acceptance criteria — chuẩn measurable

```
✓ "Test X passes" — concrete, machine-verifiable
✓ "Migration apply + rollback clean" — concrete
✓ "Endpoint POST /api/v1/patient returns 201 with patient_code in response"
✓ "Event log row emitted with type=PATIENT_CREATED"

✗ "Code is clean" — not measurable
✗ "Works correctly" — not measurable
✗ "Tests cover the cases" — too vague (which cases?)
✗ "Performance is acceptable" — define threshold
```

## 3. Files được phép sửa vs KHÔNG được động

### 3.1 Mặc định: deny-by-default

Implementer **chỉ được** sửa file trong **In-scope list**. Mọi file khác = không động.

### 3.2 Khi tìm thấy bug ngoài scope

```
Implementer flow:
1. Tìm thấy bug ngoài scope task hiện tại.
2. KHÔNG fix.
3. Ghi vào report section "Noted but not fixed":
   - Path
   - Brief description
   - Suggested separate task ID
4. Continue current task.
```

### 3.3 Khi cần file ngoài scope để hoàn thành task

```
Implementer flow:
1. STOP code.
2. Reply lên Claude Chat:
   "T-YYYYMMDD-NN cần sửa thêm file X vì lý do Y.
    Approve mở scope hay tạo task mới?"
3. ĐỢI Claude Chat reply.
```

## 4. Output report format

Mỗi task xong → report tại `.ai/reports/T-YYYYMMDD-NN.md`:

```markdown
# REPORT — T-YYYYMMDD-NN

## Outcome
Complete | Partial | Blocked | Abandoned

## What was done (3-7 bullets, verbs first)
- Added migration `20260521_002_patient.sql`.
- Implemented `patient_service.create_patient()` with MPI dedup.
- Added 8 unit tests + 2 integration tests.
- Wired `patient_code` generator function.

## Files read (mọi canon doc đã consult)
- CLAUDE.md
- final_canon/02_CODING_RULES.md
- final_canon/05_DATABASE_DESIGN_FINAL.md §3
- ClinicAI_v6_Schema_Memory_1.md §D2

## Files edited
```
A  src/migrations/20260521_002_patient.sql
A  src/migrations/20260521_002_patient.down.sql
A  src/clinicai/services/patient_service.py
A  src/clinicai/tools/patient/create.py
A  src/tests/services/test_patient_service.py
M  src/clinicai/types.py
```

## Tests
- New: 8 unit + 2 integration.
- Command: `pytest src/tests/services/test_patient_service.py -v`
- Result: **10 passed, 0 failed, 0 skipped**
- Full suite: `pytest` → **73 passed, 0 failed** (was 65, +8 new).

## Acceptance criteria status
- [x] Migration apply + rollback clean.
- [x] Test `test_patient_service__create_with_existing_phone__creates_with_warning` pass.
- [x] Test `test_mpi__cccd_match_overrides_phone__returns_existing` pass.
- [x] No file outside in-scope list modified.
- [x] Pre-commit hooks pass.
- [x] CI green.
- [x] Report filed.

## Diagnosis / design notes (non-trivial)
- Chose `gen_random_uuid()` over `uuid_generate_v4()` (deprecated in PG 16).
- patient_code generator uses advisory lock to avoid race condition on sequential number.

## Assumptions confirmed / pushback (K1)
Confirmed all 3 assumptions from task. No pushback.

## Noted but not fixed (K3)
- `src/clinicai/services/_common/db.py` has a TODO about connection pool sizing. Out of scope. Suggest T-NEXT-XX.

## Canon doc updates
- [ ] CONSTRAINTS.md — no
- [ ] DECISIONS.md — no
- [x] CURRENT_ARCHITECTURE_STATE.md — moved Phase 3 patient_service to GREEN
- [ ] OPEN_QUESTIONS.md — no

## Open questions surfaced
- Q-N12 — Should `Patient.phone` accept multiple formats (+84, 0...) and normalize, or reject non-E.164? Currently I normalize → store E.164. Confirm intent.

## Risks / things to watch
- patient_code generator uses Postgres advisory lock. On extreme concurrency (1000+ inserts/sec), could bottleneck. Not a concern at clinic scale (~30 patients/day).

## Next steps suggested
1. T-NEXT-01 — Wire MPI service into Golden Record Engine.
2. T-NEXT-02 — Add Human Review Queue UI in dashboard.

## Commit / PR
- Branch: feature/patient-domain
- Commits: 7c4a9e2..b1d3f51
- PR: #42
- Merge readiness: ready
```

## 5. Patch / report workflow

```
Quang (chat)
  └→ Claude Chat
        ├─ Read task description, CONSTRAINTS, DECISIONS
        ├─ Decompose if needed
        ├─ Write .ai/tasks/T-YYYYMMDD-NN.md
        └─ Assign to Claude Code (default)
              │
              ├─ Read task + canon docs listed
              ├─ Reply with K1 assumption confirmation (or pushback)
              │   └→ Claude Chat resolves before coding starts
              ├─ Implement per scope
              ├─ Run tests
              ├─ Write .ai/reports/T-YYYYMMDD-NN.md
              └─ Open PR / commit
                    │
                    └→ Claude Chat reviews:
                          ├─ Run REVIEW_CHECKLIST.md
                          ├─ Approve → merge
                          ├─ Request changes → back to Claude Code (same agent)
                          └─ Block (cite rule) → escalate Quang
```

## 6. Khi nào AI được hỏi lại

```
Implementer ASK Claude Chat (or Quang) khi:
✓ Assumption không có trong task → confirm trước khi code.
✓ Task in-scope file nhưng cần migration mới chưa có trong task → ask.
✓ Test fail vì lý do không liên quan task (existing bug hoặc env issue) → ask.
✓ Performance / security concern phát hiện trong scope → ask.
✓ Scope task không đủ để đạt AC → ask.
✓ Conflict với CONSTRAINTS / DECISIONS → STOP, ask.

Implementer KHÔNG ASK (tự handle):
✓ Naming detail trong scope (function name, variable name) — theo §11 02_CODING_RULES.
✓ Bao nhiêu test → ≥80% coverage cho code mới + safety gate negative test.
✓ Có dùng async hay sync — async-first per §2.2 02_CODING_RULES.
✓ Format code — pre-commit black + ruff handle.
```

## 7. Khi nào phải DỪNG

Implementer **STOP** immediately khi:

```
1. Tìm thấy mâu thuẫn với CONSTRAINTS hoặc Loại A DECISIONS.
2. Cần xoá data từ append-only table.
3. Cần UPDATE FINALIZED visit row.
4. Cần thay đổi safety gate behavior (GROUP_C, FINALIZED, is_training, voice_review).
5. Cần thêm dependency mới chưa có trong pyproject.toml.
6. Cần thêm external API mới chưa có trong adapters/.
7. Cần thay đổi schema production qua Dashboard (cấm).
8. Test cũ bị fail vì code mới và không hiểu tại sao.
9. Cần access secret/credential ngoài .env.example template.
10. Cần chạy script gây tác động ngoài (gửi Zalo thật, gọi API trả phí lớn).

KHÔNG TỰ XỬ LÝ — escalate Claude Chat hoặc Quang.
```

## 8. Khi nào phải tạo FAILING TEST trước

```
✓ Bug fix:           failing test reproduce bug → fix → test pass.
✓ Safety gate add:   negative test trước (gate must block) → implement gate.
✓ New invariant:     test invariant → implement.
✓ Regression report: test rebuild scenario → fix.

✗ Greenfield feature: implement + test cùng lúc OK.
✗ Refactor không đổi behavior: existing test phải vẫn pass.
```

## 9. Khi nào phải đề xuất MIGRATION

```
NEW migration cần khi:
- Thêm/sửa/xoá table.
- Thêm/sửa/xoá column.
- Thêm/sửa/xoá index.
- Thêm/sửa/xoá constraint (CHECK, FK, UNIQUE).
- Thêm/sửa/xoá function, trigger, view, type.

KHÔNG cần migration cho:
- INSERT/UPDATE seed data thông thường (dùng API, không SQL trực tiếp).
- Cấu hình app behavior (dùng KB, không schema).

Mọi migration phải có DOWN script (§8.2 02_CODING_RULES).
```

## 10. Khi nào phải ESCALATE lên Quang (chứ không phải Claude Chat)

Claude Chat thay vì Quang OK cho:
- Architectural decision trong khuôn khổ đã locked.
- Task decomposition.
- Code review.
- Debugging.

**ESCALATE QUANG** (Claude Chat KHÔNG quyết được) khi:
- Đổi locked decision (Loại A).
- Đổi tech stack.
- Đổi safety gate behavior.
- Đổi communication channel (thêm/bỏ).
- Spend rules (cost ceiling, API budget).
- Hiring/firing AI agent từ team.
- Đổi clinical workflow (cần BS Thành/BS Hùng).
- Đổi compliance scope (NĐ13, TT13, FHIR).
- Conflict giữa 2 stakeholder (Hà vs Hoa vs BS).
- Production incident severity >= P1.

## 11. Owner matrix theo task type

```
TASK TYPE                           DEFAULT OWNER          ALLOWED FALLBACK
─────                               ─────────────          ────────────────
Migration                            Claude Code            Quang manual
Service implementation               Claude Code            Codex (small)
Tool implementation                  Claude Code            Codex
LangGraph sub-graph                  Claude Code            (Claude Code only — complex)
Adapter                              Claude Code            (Claude Code only)
Test addition                        Claude Code OR Codex   Either
Single-file refactor (<100 LOC)      Codex                  Claude Code
Bug fix < 50 LOC                     Codex                  Claude Code
Bug fix > 50 LOC                     Claude Code            (Claude Code only)
Bug fix multi-file                   Claude Code            (Claude Code only)
Dashboard page                       Antigravity            Claude Code (backend integration)
Dashboard component                  Antigravity            Codex
Browser-driven validation            Antigravity            (Antigravity only)
KB markdown edit                     Quang                  Claude Chat (drafts)
KB sync logic                        Claude Code            (Claude Code only)
Prompt drafting                      Claude Chat → Qwen review → Quang approve
Eval suite addition                  Claude Code            Codex (data prep)
Summarization (bulk, non-prod)       Qwen worker            Claude Haiku fallback
Classification (trivial, non-prod)   Qwen worker            Claude Haiku fallback
Code review (small diff <100 LOC)    Qwen (style only) + Claude Chat (substance)
Code review (medium diff)            Claude Chat            Quang final
Code review (large diff >500 LOC)    Quang                  Claude Chat draft
Production deploy                    Quang (manual)         (Quang only)
ADR drafting                         Claude Chat            Quang approve
CR (Change Request) drafting         Claude Chat            Quang approve
Production incident response         Quang                  Claude Chat support
```

## 12. Per-agent capability limits

### Claude Code (primary executor)

```
CAN:
- Multi-file changes within task scope.
- Run tests, run migrations locally.
- Open PR.
- Read mọi canon doc.
- Edit code, edit tests, edit KB markdown (with explicit task).
- Suggest CR if scope blows up.

CANNOT (without escalation):
- Push to main directly.
- Sửa CONSTRAINTS.md / DECISIONS.md.
- Production deploy.
- External API call with cost (chỉ với explicit cost budget trong task).
- Tạo task mới (chỉ Claude Chat tạo task).
```

### Codex (in VS Code IDE)

```
CAN:
- Single-file edits.
- Quick fixes, renames, simple refactors.
- Test additions for existing code.

CANNOT:
- Multi-file refactor without Claude Chat sign-off.
- Schema migrations.
- LangGraph sub-graph build.
- KB markdown edits.
- Open PR autonomously (use as suggestion only).
```

### Antigravity / Kiro (agentic IDE + browser)

```
CAN:
- Dashboard page scaffold.
- UI iteration.
- Browser validation (e.g., Zalo OA admin checks).
- Screenshot for review.
- Frontend test scaffolding (Cypress).

CANNOT:
- Backend code.
- Schema migrations.
- Architectural decisions.
- Production deploy.
```

### Qwen3-14B local (worker)

```
CAN:
- Summarize Zalo conversation snippets (≤500 tokens).
- Classify intent (trivial categories).
- Generate test name suggestions.
- Generate boilerplate (decorator stubs, type hints).
- Pre-process KB chunks (paragraph extraction, basic clean).

CANNOT:
- Production-impacting decision.
- PR/commit autonomously.
- Replace Haiku/Sonnet for ambiguous reasoning.
- Code review for substance (style only, supervised by Claude Chat).
- Touch safety gate logic.
- Touch identity / merge logic.
```

## 13. Anti-patterns to avoid

```
✗ "Hey Codex, also refactor this nearby function while you're there."
  Solution: separate task.

✗ Multiple AI agents pull-request hôm cùng file cùng lúc.
  Solution: one task = one owner. Sequential, not parallel.

✗ Qwen "đã review code và approve" → merge.
  Solution: Qwen review = style hint only. Substance reviewer = Claude Chat or Quang.

✗ Claude Code "thấy migration cũ bug, tự fix."
  Solution: report as "noted but not fixed," create separate migration task.

✗ Antigravity "build dashboard then add new API endpoint mid-task."
  Solution: scope creep. Stop, escalate.

✗ Task không có acceptance criteria measurable.
  Solution: Claude Chat reject task, ask Quang to refine.

✗ "Implementer đã chạy được, không cần test."
  Solution: tests mandatory. PR blocked otherwise.

✗ "Pre-commit fail, dùng --no-verify để push."
  Solution: FIX the failures, không skip.

✗ "Code OK nhưng quên update DECISIONS.md."
  Solution: review checklist sẽ catch — DoD bao gồm canon doc update.
```

---

*03_TASK_DELEGATION_RULES.md · 2026-05-20 · Task template + owner matrix + escalation rules.*
