# 09 — Claude & Agent Instructions (Hướng dẫn cho Claude / Agent)

> File instruction cuối cùng + copy-paste-ready CLAUDE.md cho root repo.
> Cập nhật: 2026-05-20 · Status: **CANON**

---

## 1. System behavior cho Claude (Chat hoặc Code)

Khi một Claude session bắt đầu:

```
1. Đọc CLAUDE.md (root) — copy-paste section §9 file này.
2. Thực hiện Startup Ritual.
3. Báo cáo ngắn (3-5 dòng): hiểu gì về project hiện tại?
4. Đợi yêu cầu từ user (Quang hoặc upstream Claude Chat).
5. Confirm K1 assumption nếu yêu cầu underspecified.
6. Thực thi nhiệm vụ theo phase đúng (xem 01_IMPLEMENTATION_ROADMAP).
7. Báo cáo theo .ai/REPORT_TEMPLATE.md.
8. Cập nhật canon doc nếu DoD yêu cầu.
```

## 2. Cách start một session

```
SESSION OPENING (Claude Chat):
"Tôi đã đọc CLAUDE.md, context/CONSTRAINTS.md (§C1-C15),
context/CURRENT_ARCHITECTURE_STATE.md, và glance qua context/OPEN_QUESTIONS.md.

Hiểu nhanh hiện trạng:
- Phase đang ở: <P0 / P1 / P2...>
- Tasks mới nhất completed: <T-XXX>
- Blockers open: <Q-V01, Q-V08>
- Loại A decisions mới nhất: <Dxx>

Quang muốn làm gì session này?"

SESSION OPENING (Claude Code):
"Đã đọc:
- CLAUDE.md
- final_canon/06_HARD_DECISIONS_AND_STYLE.md
- context/CONSTRAINTS.md
- task file .ai/tasks/T-YYYYMMDD-NN.md
- listed context files in task

Hiểu task: <1-2 câu paraphrase>
Assumption confirm (K1):
  1. <X>
  2. <Y>
  3. <Z>

OK proceed?"
```

## 3. Files to read FIRST per session type

### Session type: planning / architecture review

```
Read order:
1. CLAUDE.md
2. final_canon/00_SYSTEM_OVERVIEW_AND_FINAL_ARCHITECTURE.md
3. final_canon/06_HARD_DECISIONS_AND_STYLE.md (decisions D001-D060)
4. context/CURRENT_ARCHITECTURE_STATE.md
5. context/OPEN_QUESTIONS.md
6. (relevant domain file from final_canon/0X)
```

### Session type: implementation / coding

```
Read order:
1. CLAUDE.md
2. .ai/tasks/T-YYYYMMDD-NN.md (the task)
3. final_canon/02_CODING_RULES.md (relevant sections)
4. final_canon/06_HARD_DECISIONS_AND_STYLE.md §1 (D### referenced in task)
5. context/CONSTRAINTS.md (§C## referenced in task)
6. (context files listed in task)
7. (ClinicAI_v6_Schema_Memory_1.md §D## if schema involved)
```

### Session type: bug fix

```
Read order:
1. CLAUDE.md
2. Bug report + stack trace
3. final_canon/06_HARD_DECISIONS_AND_STYLE.md §1 (relevant D###)
4. relevant code area (current state)
5. relevant test file
6. Write FAILING test reproducing bug (K-bug-1)
7. Then proceed with fix
```

### Session type: review / code review

```
Read order:
1. CLAUDE.md
2. The PR diff
3. .ai/REVIEW_CHECKLIST.md (run through)
4. final_canon/02_CODING_RULES.md (sections relevant to diff)
5. final_canon/06_HARD_DECISIONS_AND_STYLE.md (D### relevant to diff)
6. (relevant test additions in diff)
```

## 4. How to select context

### Rule of selective context (D032)

```
NEVER:
- Read entire codebase.
- Dump >5 large markdown files into context.

ALWAYS:
- Read only listed in task.
- Sample large file by section (§ markers).
- Skim README/CHANGELOG, deep-read CONSTRAINTS/DECISIONS.
- Verify file existence before quoting reference.

ALLOWANCE:
- 5-8 files max per task context.
- ≤30K tokens of context per session for stable performance.
- If task needs more → split task.
```

### File-by-file context budget

```
CLAUDE.md                                  always full
context/CONSTRAINTS.md                     always full
final_canon/06_HARD_DECISIONS               sections referenced
final_canon/02_CODING_RULES.md             sections referenced
final_canon/05_DATABASE_DESIGN_FINAL.md    sections referenced
ClinicAI_v6_Schema_Memory_1.md             §D## relevant only
context/CURRENT_ARCHITECTURE_STATE.md      §1-2 + ORANGE list
context/OPEN_QUESTIONS.md                  only Q### mentioned in task
.ai/tasks/T-XXX.md                         full
wiki/agent-policy/contracts/<name>.md      full if agent involved
src/clinicai/<module>/                     only files in task scope
```

## 5. How to create a task (Claude Chat only)

```
1. Read Quang's request.
2. Check OPEN_QUESTIONS — does this depend on unresolved blocker?
   - If yes: ask Quang first.
3. Check CONSTRAINTS — does request violate any rule?
   - If yes: surface conflict, propose alternative.
4. Check DECISIONS — does request reverse a locked decision?
   - If yes: propose ADR draft, escalate Quang.
5. Decompose into tasks ≤XL (split if >2 days).
6. For each task:
   a. Open .ai/TASK_TEMPLATE.md.
   b. Fill all sections.
   c. Save to .ai/tasks/T-YYYYMMDD-NN.md.
   d. Assign to right owner (per 03_TASK_DELEGATION §11 matrix).
7. Report back to Quang: task IDs + assignees + estimated.
```

## 6. How to implement (Claude Code / Codex / Antigravity)

```
1. Read task file fully.
2. Read context files listed (selective).
3. Reply with K1 assumption confirmation (or pushback).
4. WAIT for confirmation before code.
5. Plan: write a 3-5 bullet implementation sketch (not full code yet).
6. Implement:
   a. Migration first (if applicable) — apply local + rollback test.
   b. Test scaffolding (failing tests).
   c. Implementation.
   d. Tests passing.
   e. Pre-commit hooks pass.
7. Self-review against REVIEW_CHECKLIST.md.
8. Write .ai/reports/T-YYYYMMDD-NN.md.
9. Open PR or commit per task convention.
10. Notify reviewer (Claude Chat or Quang).
```

## 7. How to report

```
Format: .ai/reports/T-YYYYMMDD-NN.md
Content sections (mandatory, see 03_TASK_DELEGATION §4):
- Outcome
- What was done
- Files read
- Files edited
- Tests
- Acceptance criteria status
- Diagnosis / design notes
- Assumptions confirmed / pushback
- Noted but not fixed
- Canon doc updates
- Open questions surfaced
- Risks
- Next steps suggested
- Commit / PR

Length: Concise. Bullets > paragraphs. No fluff.
```

## 8. How to fix bug

```
1. STOP. Write failing test reproducing bug FIRST.
2. Diagnose root cause (not just where it crashes — WHY).
3. If cause touches CONSTRAINTS / DECISIONS → escalate before fix.
4. Fix ONLY root cause.
5. Confirm failing test now passes.
6. Confirm other tests still pass.
7. Report includes:
   - Repro test
   - Diagnosis (1-3 sentences)
   - Fix location
   - Anything noted-but-not-fixed.

NEVER:
- Patch symptom without understanding cause.
- Comment out failing test "to make it pass."
- Lower test strictness.
- Refactor unrelated code in same commit.
```

## 9. CLAUDE.md (copy-paste-ready cho root repo)

Đây là nội dung dành cho file `CLAUDE.md` ở root repo. Copy nguyên văn:

```markdown
# CLAUDE.md — ClinicAI Repo Instructions

> File này được Claude Code / Cowork đọc đầu mỗi session.
> Đọc theo đúng thứ tự §1 dưới đây. Không bỏ bước.

---

## §1 STARTUP RITUAL

1. Đọc file này (CLAUDE.md) toàn bộ.
2. Đọc `context/CONSTRAINTS.md` đầy đủ.
3. Đọc `final_canon/06_HARD_DECISIONS_AND_STYLE.md` §1 (D001-D060).
4. Đọc `context/CURRENT_ARCHITECTURE_STATE.md` §1-3.
5. Glance `context/OPEN_QUESTIONS.md` — note Q-V01 và blockers khác.
6. NẾU task file có sẵn: đọc `.ai/tasks/<task-id>.md`.
7. NẾU task list context files: đọc đúng sections.

Sau §1, báo cáo ngắn 3-5 dòng + đợi user.

## §2 METHOD

Apply Karpathy principles:
- K1 — State assumptions trước khi đề xuất.
- K2 — Simplest first.
- K3 — Touch only what was asked.
- K4 — Success criteria measurable.

Phase order:
1. Hiểu vấn đề.
2. Benchmark / nguyên tắc.
3. Business decision (từ phòng khám).
4. Technical design.
5. Implementation.

Bỏ bước nào là sai.

## §3 BUG FIX PROTOCOL

1. Reproduce qua failing test.
2. Diagnose root cause.
3. Confirm trước nếu touch CONSTRAINTS/DECISIONS.
4. Fix only root cause (K3).
5. Test pass.
6. Report.

NEVER patch symptom, never lower test strictness.

## §4 FEATURE PROTOCOL

1. Check scope.
2. K4 acceptance criteria.
3. Decompose smallest slice.
4. K1 confirm assumptions.
5. Design before code.
6. Implement + test.
7. Update canon doc nếu DoD bao gồm.
8. Report.

## §5 CODING RULES — TÓM TẮT

Full ở `final_canon/02_CODING_RULES.md`. Highlight:
- Python 3.12 cứng.
- async-first.
- Pydantic schema for I/O.
- LangGraph node KHÔNG ghi DB → qua tool.
- AI call qua model_gateway only.
- Prompt trong file riêng (`<graph>/prompts/`).
- Test mọi safety gate (negative test).
- Migration có DOWN script.
- trace_id end-to-end.
- event_log row cho mọi mutation.

## §6 KHÔNG VƯỢT SCOPE

K3 strict. Nếu thấy bug khác hoặc cải thiện adjacent code:
- Ghi vào report "Noted but not fixed."
- KHÔNG sửa.

Nếu task scope không đủ:
- STOP code.
- Reply ask Claude Chat refine task.

## §7 LUÔN REPORT

Mỗi task → `.ai/reports/T-YYYYMMDD-NN.md`.
Format: xem `final_canon/03_TASK_DELEGATION_RULES.md` §4.

Nội dung tối thiểu:
- Files read
- Files edited
- Tests run + results
- AC status
- Noted-not-fixed
- Open questions surfaced
- Canon doc updates

Không report = next session blind.

## §8 SAFETY GATES (LOẠI A)

KHÔNG bypass:
- GROUP_C lab gate (CSKH không notify khi bs_reviewed_at NULL).
- FINALIZED visit immutable.
- is_training staff không auto-assign.
- voice_note_reviewed gate trên ClinicalRecord.

Tất cả 4 gates enforce ở application layer; 2/4 enforce thêm ở DB trigger.

## §9 NEVER

- Adapter ghi Domain DB.
- Phone là PK.
- ENUM hardcode cho ServiceType/BookingChannel/LabPartner.
- AI quyết safety gate.
- Audio cloud.
- Telegram/SMS/email cho BN/staff.
- print() trong production.
- except Exception quá rộng.
- dict[str, Any] trong API response.
- Skip pre-commit hooks.
- Production deploy autonomously.

## §10 CONFLICTS

Khi 2 file mâu thuẫn:
1. `06_HARD_DECISIONS_AND_STYLE.md` thắng.
2. Hard safety gate thắng convention.
3. Newer version thắng older.
4. Code (test pass) thắng narrative.
5. Khi không chắc → escalate Quang.

## §11 LOCAL MODELS (Qwen / Whisper)

- Worker only, không quyết định.
- Production fallback: API (Haiku/Sonnet).
- Output review trước khi dùng:
  - Safety-relevant → IGNORE Qwen, dùng Haiku/Sonnet.
  - Trivial → use directly.
  - Moderate → sample 10% review.

## §12 NGƯỜI

- Quang (Sáng Ý / Avalook / DEE DEE) — boss + architect.
- Hà — co-founder, deployment decision.
- Hoa — ops manager. "KHÔNG PHÁT SINH THÊM task."
- BS Thành — clinical lead.
- BS Hùng — clinical contributor (SOAP, Pre-visit Brief).
- Hà bé — CSKH primary.
- Hương — nurse ultrasound.
- Minh — training.

Clinic = Dr4women, sản phụ khoa, Hà Nội. 2 sites: KN (active) + HN (mở sau).

## §13 KHI HOÀI NGHI

- Task ambiguous → ask.
- Conflict với DECISIONS → STOP, surface.
- Safety gate touched → STOP, double-check.
- Tests fail unrelated → STOP, escalate.
- Need clinic input → add to OPEN_QUESTIONS, assign owner, không proceed.
- Don't know canon? → check `context/FILE_MAP.md` hoặc `_audit/VERSION_MAP.md`.

## §14 TÀI LIỆU CHÍNH

Đọc theo nhu cầu:
- `final_canon/00_SYSTEM_OVERVIEW...` — kiến trúc tổng.
- `final_canon/01_IMPLEMENTATION_ROADMAP...` — phase + task.
- `final_canon/02_CODING_RULES...` — code rules.
- `final_canon/03_TASK_DELEGATION_RULES...` — task format.
- `final_canon/04_MULTI_AI_WORKING_MODEL...` — AI team.
- `final_canon/05_DATABASE_DESIGN_FINAL...` — schema reasoning.
- `final_canon/06_HARD_DECISIONS_AND_STYLE...` — không vi phạm.
- `final_canon/07_CONTEXT_AND_MEMORY_RULES...` — context/memory.
- `final_canon/08_END_TO_END_SYSTEM_DESIGN...` — deploy + repo.
- `final_canon/09_CLAUDE_AND_AGENT_INSTRUCTIONS...` — file này nguồn.
- `final_canon/10_RESEARCH_AND_BENCHMARK_2026-05-20...` — industry benchmark.
- `final_canon/11_REVIEW_AGENDA_FOR_HUMAN...` — review checklist.

Source schema canon: `ClinicAI_v6_Schema_Memory_1.md`.

---

*Owner: Quang · Last updated: 2026-05-20*
```

## 10. How to handle conflicts

```
Conflict type 1: User request conflicts with locked DECISION.
Action:
1. Don't comply silently.
2. Reply: "Yêu cầu này conflict với D### [tên decision]. Source: [file].
          Để thực hiện, cần ADR đổi D###. Quang xác nhận?"
3. Wait Quang decision.
4. If Quang override: draft ADR, update DECISIONS, then implement.
5. If Quang stand by D###: implement alternative aligned with D###.

Conflict type 2: Two CONSTRAINTS contradict each other (hiếm).
Action:
1. STOP. Escalate Claude Chat / Quang.
2. Document conflict in _audit/.
3. Resolve via ADR.

Conflict type 3: Code says X, doc says Y.
Action:
1. Test wins. If test enforces X, code is right.
2. If test missing: ask Quang which is correct.
3. Update either code or doc to align. Update event_log.

Conflict type 4: 2 AI agents disagree on approach.
Action:
1. Claude Chat mediates per 04_MULTI_AI_WORKING_MODEL §8.
2. Tests are tiebreaker.
3. If still tied: Quang decides.
```

## 11. How to work with local models (Qwen / Whisper)

```
Calling Qwen for trivial classification:

response = await model_gateway.chat(
    system=CLASSIFY_INTENT_PROMPT,
    user=zalo_message,
    complexity="trivial",   # routes to Qwen local first
)

Gateway behavior:
- complexity="trivial":  Qwen local → fallback Haiku
- complexity="simple":   Haiku → fallback Sonnet
- complexity="medium":   Haiku
- complexity="complex":  Sonnet
- complexity="reasoning": Sonnet

Failover:
- Qwen timeout 5s → log warning, retry with Haiku.
- Haiku error 5xx → retry once → Sonnet fallback.
- Sonnet 5xx → raise IntegrationError, fall to human queue.
```

## 12. How to prepare task for Codex/Antigravity/Kiro/Qwen

```
FOR CODEX (small in-file fix):
- Give Codex: file path + line range + specific change requested.
- Codex output: in-place suggestion.
- Claude Code or Quang commits.

FOR ANTIGRAVITY (dashboard/UI):
- Give Antigravity: dashboard mockup (text description) + API spec backend serves.
- Antigravity output: Next.js components + browser test.
- Claude Chat reviews UX coherence.

FOR KIRO (agentic exploration):
- Give Kiro: high-level goal (e.g., "explore which Zalo OA admin settings affect rate limit").
- Kiro output: investigation report.
- Claude Chat synthesizes into ADR or KB page.

FOR QWEN (bulk worker):
- Give Qwen: input text (≤500 tokens) + classification prompt.
- Qwen output: structured response.
- Claude Chat OR application logic reviews:
  - Safety-relevant → IGNORE Qwen, retry with Haiku.
  - Trivial → use Qwen output directly.
  - Moderate → sample 10% spot-check.
```

## 13. Refuse unsafe / over-scope changes

```
Refuse + explain when user asks Claude to:

✗ Bypass safety gate → "Không thể bypass GROUP_C gate. Đây là Loại A D022 + clinical risk.
                       Nếu cần test, dùng test data với gate disabled in test config, không production."

✗ Skip migrations → "Migration là rule cứng. KHÔNG sửa schema production qua Dashboard.
                     Cần tạo migration file theo format."

✗ Hardcode rule trong code → "Rule này phải vào KB markdown. Lý do: Hoa cần sửa được mà
                              không cần developer. Đây là D029."

✗ Log PII → "Không log PII vào application logs. Dùng event_log table thay."

✗ Send audio cloud → "Audio không rời clinic. NĐ13/2023 + Loại A D011."

✗ Build risk scoring AI → "Cấm cho đến N=50K outcomes. Loại A D013."

Format response:
1. Lý do tại sao không thể.
2. Reference rule (Loại A D###, §C##, hoặc file).
3. Đề xuất alternative.
```

## 14. How to update docs

```
DURING task:
- Update canon doc trong cùng commit với code change.
- Update theo DoD checkbox trong task.

AFTER task:
- File `.ai/reports/T-XXX.md` ghi "Canon doc updates":
  [ ] CONSTRAINTS.md
  [ ] DECISIONS.md
  [ ] CURRENT_ARCHITECTURE_STATE.md
  [ ] OPEN_QUESTIONS.md
  [ ] CHANGELOG.md (root)

PERIODIC:
- Sprint end → Quang/Claude Chat update PROGRESS.md.
- Quarter → compact DECISIONS/OPEN_QUESTIONS (xem 07_CONTEXT_AND_MEMORY §7).

NEVER:
- "Code đi, doc sửa sau."
- "Doc small, không quan trọng."
- Update doc trong commit deploy production (must be separate).
```

---

*09_CLAUDE_AND_AGENT_INSTRUCTIONS.md · 2026-05-20 · Copy-paste CLAUDE.md content trong §9.*
