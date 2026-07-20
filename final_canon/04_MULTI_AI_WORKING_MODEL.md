# 04 — Multi-AI Working Model (Cơ chế nhiều AI cùng làm việc)

> Cách các AI tools (Claude Chat, Claude Code, Codex, Antigravity/Kiro, Qwen local) phối hợp.
> Cập nhật: 2026-05-20 · Status: **CANON**

---

## 1. Triết lý nền tảng

```
Quang → một "Tech Lead người" duy nhất.
Claude Chat → architect + planner + reviewer (một).
Claude Code → primary executor (một, tạm thời; sau có thể song song có giới hạn).
Codex → IDE quick-fix companion (một, hỗ trợ).
Antigravity / Kiro → UI/dashboard/browser agent (một, frontend domain).
Qwen local → cheap bulk worker (một, không quyết định).

Git + tests = SOURCE OF TRUTH + ARBITRATOR.
Canon docs = SHARED MEMORY.
Tasks + Reports = HANDOFF PROTOCOL.
```

**Không bao giờ:**
- Nhiều AI sửa cùng 1 file cùng lúc.
- Cho 1 AI "tự nhớ" private — memory phải trong git.
- Để Qwen quyết định safety gate hay architecture.
- Để Codex/Antigravity tạo task mới.
- Để Claude Code merge thẳng main không qua review.

## 2. Vai trò từng công cụ — chi tiết

### 2.1 Claude Chat (this surface, planning + review)

**Là gì:** Trung tâm điều phối. Đọc canon, hiểu kiến trúc, ra plan, viết task, review code.

**Làm việc gì:**
- Read mọi canon doc trước mỗi session.
- Decompose yêu cầu Quang → tasks cụ thể.
- Draft ADR (Architecture Decision Record).
- Viết `.ai/tasks/T-YYYYMMDD-NN.md`.
- Review PR theo `REVIEW_CHECKLIST.md`.
- Mediate khi 2 AI disagree.
- Update canon doc (CONSTRAINTS, DECISIONS, OPEN_QUESTIONS, CURRENT_ARCHITECTURE_STATE).
- Draft prompts cho graphs (sau đó Quang approve).

**Không làm:**
- Code production (delegate Claude Code).
- Push code lên main.
- Lock decision mới mà chưa có Quang approve.
- Quyết định business/clinical question (escalate Quang/clinic).

**Output:**
- Plans, ADRs, tasks, reviews-as-comments, weekly digests.

### 2.2 Claude Code (terminal, primary executor)

**Là gì:** AI coder chính. Đọc task, code, test, report.

**Làm việc gì:**
- Implement task per `T-YYYYMMDD-NN.md` scope.
- Write tests (unit + integration).
- Run migrations local + verify.
- Open PR với report.
- Update canon doc khi DoD bao gồm.
- Suggest CR khi scope blows up.

**Không làm:**
- Tạo task mới (chỉ Claude Chat tạo).
- Sửa CONSTRAINTS.md / DECISIONS.md mà không có Quang approve.
- Production deploy.
- External API call có chi phí trừ khi task explicit cho phép.
- Refactor adjacent code (K3).

**Output:**
- Code changes, tests, `.ai/reports/T-YYYYMMDD-NN.md`.

### 2.3 Codex (VS Code IDE, in-file pair programmer)

**Là gì:** IDE companion. Quick fixes, inline completions, single-file refactors.

**Làm việc gì:**
- Single-file edits (≤200 LOC).
- Function rename, variable rename.
- Snippet completion.
- Quick bug fix (<50 LOC) với approval Claude Chat.
- Test naming + edge case suggestion.

**Không làm:**
- Multi-file refactor.
- Migration.
- LangGraph graph build.
- KB markdown edit.
- Open PR tự động (use as suggestion, Quang/Claude Code commit).

**Output:**
- In-place diffs, small commits.

### 2.4 Antigravity / Kiro (agentic IDE + browser)

**Là gì:** Frontend + UI + browser + agentic exploration tool. Trong project này dùng cho dashboard, UX iteration, browser-driven test, screenshot.

**Làm việc gì:**
- Next.js dashboard scaffold (Phase 7).
- UI component iteration.
- Cypress / Playwright browser test.
- Screenshot capture for review.
- Browser-validation (e.g., login flow, Zalo OA admin panel inspect).
- Frontend agentic flows (e.g., "drag and drop task between columns").

**Không làm:**
- Backend code.
- Schema migration.
- LangGraph backend graph.
- KB markdown content.
- Architectural decision.
- Production deploy.

**Output:**
- Frontend components, browser tests, screenshots, UI mockups.

**Sub-question Q-N08 (open):** Antigravity vs Kiro — đề xuất dùng Antigravity cho dashboard chính, Kiro cho exploratory agent flows. Quang xác nhận.

### 2.5 Qwen3-14B local (Mac Mini worker)

**Là gì:** Cheap bulk inference. Chạy local trên Mac Mini M4 Pro.

**Làm việc gì:**
- Summarize Zalo conversation (≤500 tokens input).
- Classify trivial intent (chào hỏi vs đặt lịch vs hỏi giá vs khác).
- Generate test name suggestions.
- Generate boilerplate (decorator stubs, type hints).
- KB chunk preprocessing (paragraph split, basic clean).
- Code style review (suggest names, lint-style nits).

**Không làm:**
- Production-impacting decisions.
- Auto-commit / auto-PR.
- Replace Sonnet for ambiguous reasoning.
- Code substance review (style hint only).
- Touch safety gate logic.
- Touch identity / merge logic.
- Anything affecting patient data accuracy.

**Output:**
- Suggestions to Claude Chat / Claude Code (human-in-loop).

**Failover:** Mac Mini down → Claude Haiku is the fallback for these worker tasks. Cost: ~$0.25/MTok input vs ~$0/$0 for Qwen local. Acceptable for Phase 1.

## 3. Quy tắc "one task = one owner"

**Mỗi task có đúng 1 AI agent owner.** Lý do:

```
Pre-condition: nhiều AI đọc cùng task description → có thể hiểu khác nhau.
Pre-condition: nhiều AI viết cùng file → race condition, silent overwrite.
Pre-condition: không có "shared working memory" giữa các AI session.

Hệ quả: 1 task = 1 owner cho đến khi report filed.
```

**Handoff rule:** task chuyển owner CHỈ qua:
1. Owner cũ filed `.ai/reports/T-XXX.md` với outcome = "Partial" hoặc "Blocked."
2. Claude Chat duyệt handoff.
3. Claude Chat re-assign owner mới.
4. Owner mới đọc cả task + previous report.

## 4. Không nhiều AI sửa cùng file cùng lúc

**Mechanism:**

```
Pre-task: Claude Chat liệt kê file in-scope trong task.
During task: chỉ owner được sửa các file đó.
Other AI: thấy file trong scope khác = read-only cho session đó.
```

**Sai pattern (cấm):**
- Claude Code đang code `patient_service.py`, đồng thời Codex quick-fix function trong file đó → merge conflict.
- Antigravity build dashboard, đồng thời Claude Code add API endpoint cùng feature → race.

**Đúng pattern:**
- Claude Code finish patient_service.py, commit, report.
- Claude Chat assign next task cho Antigravity (UI hoá feature).

## 5. Git = source of truth

```
Mọi memory dài hạn của AI team nằm trong git:
- Code             → src/
- Tests            → src/tests/
- Schema           → src/migrations/
- KB markdown      → wiki/
- Canon docs       → context/ + final_canon/
- Audit            → _audit/
- Tasks            → .ai/tasks/
- Reports          → .ai/reports/
- Change Requests  → .ai/change_requests/
- Worklog          → .ai/worklog/ (optional)
- Prompts          → src/clinicai/graphs/*/prompts/ hoặc wiki/agent-policy/prompts/

Không có AI nào keep private memory về:
- "Patient context tôi đã cache"
- "Tôi đã suy luận từ session trước"
- "Tôi nhớ Quang nói X tuần trước"

Tất cả phải có file git để verify.
```

## 6. Worklog = handoff memory

`.ai/worklog/YYYYMMDD.md` — optional nhưng khuyến nghị cho session dài:

```markdown
# Worklog 2026-06-01

## Sessions
- 09:00 Claude Code: T-20260601-01 Patient service implementation. In progress.
- 11:30 Claude Code: T-20260601-01 Reported, PR #42 open.
- 14:00 Claude Chat: PR #42 review. Approved.
- 14:30 Claude Code: T-20260601-02 MPI service. Started.
- 17:00 Claude Code: T-20260601-02 Blocked on Q-N12 (phone format).
- 17:15 Quang: Q-N12 answered, normalize to E.164.
- 17:30 Claude Code: T-20260601-02 unblocked.

## Decisions today
- D-N51 Phone storage format = E.164 only.

## Open questions surfaced
- Q-N12 RESOLVED.
- Q-N13 NEW — should we track phone history (old number when patient changes)?

## Blocked tomorrow
- T-20260601-03 (PatientNextOfKin) waiting on Q-V01.
```

## 7. Report = format bàn giao

Mỗi task xong → report. Mỗi handoff giữa AI → report.

**Format:** xem `03_TASK_DELEGATION_RULES.md` §4 (Output report format).

**Quy tắc:**
- Report file trước khi đóng PR.
- Report bao gồm: files read, files edited, tests run, AC status, noted-not-fixed, canon updates.
- Future session đọc report để biết "đã làm gì" mà không cần đọc lại toàn bộ code.

## 8. Tests = arbitrator (trọng tài)

```
Khi 2 AI disagree về "cách đúng" cho một implementation:
1. Test cũ pass + AI A's code → AI A đúng.
2. Test cũ fail + AI B's code → AI B sai, ai gây fail là sai.
3. Cả 2 cùng pass test cũ nhưng disagree về best practice:
   - Tham khảo 02_CODING_RULES.
   - Nếu rule không nói rõ → Claude Chat decide.
   - Nếu Claude Chat uncertain → Quang decide.
4. Test mới cần thêm để verify behavior contested → bên claim behavior phải write test.
```

## 9. Cơ chế review output local model (Qwen)

```
Qwen output → not trusted automatically.

Review flow:
1. Qwen tạo summary/classification.
2. Output ghi vào temp store (event_log row type=QWEN_DRAFT).
3. Application logic uses output BUT:
   - If safety-relevant (e.g., classify lab result) → IGNORE Qwen, use Haiku.
   - If trivial (summarize FAQ) → use Qwen, no review.
   - If moderate (classify Zalo intent) → use Qwen, sample 10% → Haiku for spot check.
4. Weekly: Quang reviews 20 random Qwen outputs vs ground truth.
5. If accuracy <90% → escalate task complexity, downgrade Qwen route.

KHÔNG bao giờ:
- Qwen output gates production (no safety, no identity merge, no schedule write).
- Qwen output goes directly to patient (always via Haiku/Sonnet polish).
```

## 10. Cơ chế chống context drift

```
Drift kiểu 1: 2 AI hiểu khác về cùng concept.
  Mitigation: định nghĩa từ vựng nằm trong canon docs (06_HARD_DECISIONS_AND_STYLE
              có glossary). Tham chiếu glossary trong report khi unclear.

Drift kiểu 2: AI prompt mỗi session khác nhau.
  Mitigation: prompts lưu trong wiki/agent-policy/prompts/ (sau Phase 10) hoặc
              src/clinicai/graphs/*/prompts/ (Phase 1-9). Version controlled.

Drift kiểu 3: AI dùng context khác từ cùng repo.
  Mitigation: CLAUDE.md ép startup ritual đọc đúng thứ tự. Mọi task trỏ tới
              context to read FIRST.

Drift kiểu 4: AI tự nhớ "tuần trước Quang nói X" → bịa fact.
  Mitigation: rule "không bao giờ AI tự nhớ" — verify mọi claim bằng git/canon.

Drift kiểu 5: KB markdown thay đổi, AI dùng prompt cũ.
  Mitigation: KB sync job log version, prompt retrieve theo version_id.
```

## 11. Cơ chế update shared context sau mỗi task

```
Task done → Claude Code (implementer) update các file sau (theo DoD):

1. .ai/reports/T-XXX.md             — bắt buộc
2. CURRENT_ARCHITECTURE_STATE.md    — nếu ORANGE → GREEN
3. DECISIONS.md                     — nếu lock decision mới
4. OPEN_QUESTIONS.md                — nếu surface gap mới hoặc resolve gap cũ
5. CONSTRAINTS.md                   — chỉ nếu ràng buộc cứng mới (rare; thường Quang quyết)
6. .ai/worklog/YYYYMMDD.md          — optional, khuyến nghị

Task review → Claude Chat (reviewer) update:

1. (review comment in PR / chat)
2. Nếu task → ra Loại A decision mới: update DECISIONS.md + CONSTRAINTS.md ref
3. Nếu task → ra CR mới: update .ai/change_requests/

Sprint end → Quang/Claude Chat update:

1. PROGRESS.md                      — clinic-facing summary
2. final_canon/00_SYSTEM_OVERVIEW   — nếu architecture tweaked
```

## 12. Cơ chế conflict giữa AI agents

**Scenario:** Claude Code merge PR, Codex sau đó "thấy code đó nên refactor X."

**Resolution:**

```
1. Codex KHÔNG refactor tự động. Codex là pair programmer, không autonomous.
2. Quang (hoặc Claude Chat) đọc Codex suggestion.
3. Decide:
   - Accept → tạo task mới `T-REFACTOR-NN`, assign Claude Code.
   - Reject → đóng suggestion.
4. KHÔNG có "Codex và Claude Code đối thoại trực tiếp."
```

**Scenario:** Antigravity build UI dùng API endpoint khác với Claude Code's spec.

**Resolution:**

```
1. Test E2E reveal mismatch (UI gọi endpoint không tồn tại).
2. Claude Chat reviews: API spec là contract. UI must conform OR new task để đổi API.
3. Claude Chat decide owner: Antigravity (UI fix) hoặc Claude Code (API extend).
```

## 13. Cơ chế "no autonomous deploy"

```
ONLY Quang deploys to production.

CI builds image → push to registry → Quang manually triggers deploy.

Why:
- Compliance accountability.
- Real-world impact (Zalo gửi BN thật, DB ghi production).
- AI agents cannot be held legally responsible.

Mitigation for slower release:
- Quang can deploy multiple times per day.
- CI/CD shortened to <5min build + push.
- One-click deploy script on Mac Mini.
```

## 14. Cost discipline

```
Weekly cost audit (Claude Chat reports):
- Anthropic API spend by model (Sonnet vs Haiku).
- Per-agent breakdown (Claude Chat vs Claude Code vs model_gateway calls).
- Per-graph spend.

Targets (after Phase 11):
- 60-70% AI calls go to Qwen local (free) hoặc Haiku (~$0.25/MTok input).
- 30-40% to Sonnet for complex reasoning.
- Total monthly cap: $200 (revisit when Phase 2 ships).

Triggers:
- Sonnet > 50% of cost → audit prompts, switch low-value to Haiku.
- Qwen accuracy <90% on golden tasks → revisit fallback policy.
```

## 15. Daily ritual (suggested)

```
Sáng (Quang start day)
  - Mở Claude Chat.
  - Claude Chat đọc: PROGRESS.md, CURRENT_ARCHITECTURE_STATE.md, last 24h git log,
    last open tasks trong .ai/tasks/.
  - Claude Chat generate "morning digest": completed yesterday, pending today,
    blocked items.
  - Quang review digest, approve next tasks.
  - Claude Chat hand off to Claude Code.

Trong ngày
  - Claude Code work, periodic reports.
  - Claude Chat review when Claude Code reports.
  - Codex assist quick fixes in IDE.
  - Quang đôi khi review trực tiếp.

Cuối ngày
  - Claude Chat summary: shipped, queued, blocked, new OPEN_QUESTIONS.
  - Quang review, decide priority cho ngày mai.
  - Commit canon updates (separately from code commits).
```

---

*04_MULTI_AI_WORKING_MODEL.md · 2026-05-20 · One task one owner. Git is memory. Tests are arbitrator.*
