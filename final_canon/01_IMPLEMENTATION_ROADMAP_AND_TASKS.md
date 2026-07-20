# 01 — Implementation Roadmap & Tasks (Lộ trình triển khai)

> Build order chi tiết, từng phase, từng task, đủ để Claude Code/Codex/Antigravity nhận và chạy.
> Cập nhật: 2026-05-20 · Status: **CANON**

---

## 1. Nguyên tắc làm việc kiểu senior engineer

```
1. TOP-DOWN để hiểu kiến trúc:
   - Đọc 00_SYSTEM_OVERVIEW + 05_DATABASE_DESIGN_FINAL + 08_END_TO_END
     trước khi viết dòng code nào.

2. BOTTOM-UP để build module chắc:
   - Schema migration trước → service trước → tool trước → graph sau.
   - Không build graph khi service chưa có tool.

3. VERTICAL SLICE để chứng minh chạy thật:
   - Sau mỗi phase, phải có 1 luồng end-to-end demo được.
   - Không build 5 service rồi mới wire UI.

4. TEST TRƯỚC/SAU:
   - Bug fix: failing test trước, fix sau.
   - Safety gate: negative test bắt buộc.
   - Feature: integration test trước khi merge.

5. SMALL COMMITS:
   - 1 commit = 1 logical change.
   - Migration tách commit khỏi code change.
   - Canon doc update tách commit khỏi code.

6. ROLLBACK ĐƯỢC:
   - Mỗi migration có DOWN script.
   - Mỗi feature có flag để tắt nhanh.
   - Mỗi deploy có 1 commit hash để revert về.

7. ONE TASK = ONE OWNER:
   - Task assigned cho đúng 1 AI agent.
   - Khi handoff, viết .ai/REPORT_TEMPLATE.md.

8. CANON DOC SỐNG SONG SONG CODE:
   - Code thay đổi gì ảnh hưởng decision → update DECISIONS.md.
   - Constraint mới phát sinh → update CONSTRAINTS.md.
   - Không bao giờ "code đi rồi sửa doc sau."
```

## 2. Phase build order (13 phases)

### Phase 0 — Canon docs + Repo operating system

**Goal:** Bộ canon docs trong `final_canon/` được Tuyền approve. Repo structure khoá. CLAUDE.md hoạt động.

**Prerequisites:** Không.

**Tasks:**
- T-P0-01 Review 12 canon files với Tuyền theo `11_REVIEW_AGENDA`.
- T-P0-02 Resolve 3 blockers: Q-V01 (v6_FileA.pages), Q-V08 (track A vs B), Q-V09 (archive policy).
- T-P0-03 Khởi tạo git repo `clinicai/`, push canon docs.
- T-P0-04 Setup `.ai/tasks/`, `.ai/reports/`, `.ai/worklog/` folders.
- T-P0-05 Cấu hình CLAUDE.md ở root → Claude Code đọc đúng startup ritual.

**Files expected:**
```
clinicai/
├── CLAUDE.md
├── context/ (8 files)
├── final_canon/ (12 files)
├── .ai/ (templates + tasks/ + reports/ + worklog/)
├── _audit/ (3 files)
└── .gitignore
```

**Definition of Done (DoD):**
- Tất cả canon files committed lên git.
- Tuyền xác nhận đã review.
- Claude Code session mới đọc CLAUDE.md → tự load context đúng thứ tự.

**Tests:** Không có code → không có test. Kiểm tra bằng cách: mở session mới, hỏi "where is decisions list" → AI trả về `context/DECISIONS.md` đúng path.

**Risks:** Tuyền đổi cấu trúc folder sau khi đã code → phải refactor path nhiều file. Mitigation: lock structure ở Phase 0.

**Rollback:** Git checkout commit trước.

---

### Phase 1 — Bootstrap infrastructure

**Goal:** Local dev environment + VPS provisioning + Supabase project ready.

**Prerequisites:** Phase 0 done.

**Tasks:**
- T-P1-01 Setup Mac Mini dev: Python 3.12, Docker, Poetry, VS Code + Cursor + Claude Code CLI.
- T-P1-02 Provision VPS (ví dụ Vultr/DigitalOcean Singapore, 4 vCPU / 8GB RAM).
- T-P1-03 Tạo Supabase project (region Singapore), enable pgvector extension.
- T-P1-04 Setup GitHub repo + GitHub Actions CI workflow.
- T-P1-05 Setup `.env.example`, environment management theo `02_CODING_RULES`.
- T-P1-06 Docker Compose cho local dev: postgres (mirror Supabase schema), rabbitmq.

**Files expected:**
```
src/
├── pyproject.toml
├── docker-compose.yml
├── .env.example
├── .github/workflows/ci.yml
└── README.md
```

**DoD:**
- `poetry install` trên Mac Mini chạy ok.
- `docker compose up` local cho ra postgres + rabbitmq healthy.
- GitHub Actions CI chạy được pytest (chưa có test, chỉ verify pipeline).
- Supabase dashboard mở được, pgvector visible.

**Tests:** `pytest --collect-only` (chỉ verify pytest setup).

**Risks:** VPS region cách xa Supabase → latency. Mitigation: chọn cùng region (Singapore).

**Rollback:** Destroy VPS instance, recreate.

---

### Phase 2 — Supabase + Migrations + Master Data

**Goal:** 3 master data tables (ClinicLocation, ServiceType, BookingChannel) live trên Supabase với seed data thật từ phòng khám.

**Prerequisites:** Phase 1 done.

**Tasks:**
- T-P2-01 Migration `20260521_001_create_clinic_location.sql` + DOWN script.
- T-P2-02 Migration `20260521_002_create_service_type.sql` (với `aliases TEXT[]`, `loinc_code`, `snomed_code` pre-allocate).
- T-P2-03 Migration `20260521_003_create_booking_channel.sql`.
- T-P2-04 Seed: 2 locations (KN, HN), 15 service types (từ Notion data), 9 booking channels (từ session log Q4).
- T-P2-05 Setup migration runner: `python -m clinicai.migrations apply` / `rollback`.
- T-P2-06 Trigger `set_updated_at()` cho mọi table có `updated_at`.
- T-P2-07 Test: insert + select + alias fuzzy match.

**Files expected:**
```
src/migrations/
├── 20260521_001_create_clinic_location.sql
├── 20260521_002_create_service_type.sql
├── 20260521_003_create_booking_channel.sql
└── seed/
    ├── 001_clinic_locations.sql
    ├── 002_service_types.sql
    └── 003_booking_channels.sql
src/clinicai/migrations/runner.py
src/tests/migrations/test_master_data.py
```

**DoD:**
- Apply migration lên Supabase prod + local.
- Rollback chạy clean.
- Seed data đúng số rows (2 + 15 + 9).
- Test fuzzy match: input "siêu âm 4D thai" → match "ULTRASOUND_4D".

**Tests:**
- `test_apply_idempotent` — apply 2 lần không lỗi.
- `test_rollback` — DOWN script khôi phục state.
- `test_alias_match` — `service_type.aliases` matching đúng.

**Risks:** Seed data sai → khó sửa khi đã có FK reference. Mitigation: seed ở Phase 2, validate ngay trước Phase 3.

**Rollback:** Run DOWN scripts theo thứ tự ngược.

---

### Phase 3 — Patient / Contact / MPI

**Goal:** Patient + PatientContactChannel + PatientMedicalProfile + PatientNextOfKin + Pregnancy live. Master Patient Index (dedup logic) hoạt động.

**Prerequisites:** Phase 2 done.

**Tasks:**
- T-P3-01 5 migration cho 5 bảng D2 (Patient, PatientContactChannel, PatientMedicalProfile, Pregnancy, PatientNextOfKin).
- T-P3-02 Partial unique index `patient_national_id_idx` (WHERE national_id_number IS NOT NULL).
- T-P3-03 Function `generate_patient_code()` (format BN-YYYY-XXXXXX, sequential).
- T-P3-04 Service `patient_service.py`: create_patient, search_by_phone, search_by_name_dob, search_by_cccd.
- T-P3-05 MPI logic: identity resolution score (phone match + name fuzzy + DOB + CCCD).
- T-P3-06 Human Review Queue table + service.
- T-P3-07 Test set 50 fake patients + 10 dedup edge cases.

**Files expected:**
```
src/migrations/20260522_*.sql (5 files)
src/clinicai/services/patient_service.py
src/clinicai/services/mpi_service.py
src/clinicai/services/human_review_queue.py
src/tests/services/test_patient_service.py
src/tests/services/test_mpi.py
```

**DoD:**
- Tạo 1 Patient → patient_code = "BN-2026-000001".
- Same phone + same DOB + similar name → MPI return `MATCH` confidence ≥0.9.
- Different phone + same CCCD → MPI return `MATCH` confidence 1.0 (CCCD wins).
- Ambiguous (phone 1 same, DOB different) → push to Human Review Queue.

**Tests:**
- 10 unit test MPI score.
- 5 integration test (create + dedup + queue).
- Negative test: cannot insert duplicate CCCD.

**Risks:** MPI score tuning sai → false merge. Mitigation: prefer false-positive (push to queue) over false-merge.

**Rollback:** DOWN 5 migrations theo thứ tự ngược.

---

### Phase 4 — Staff / WorkSession / Appointment

**Goal:** Staff + WorkSession + WorkSessionStaff + Appointment live. CSKH có thể tạo appointment.

**Prerequisites:** Phase 2, 3 done.

**Tasks:**
- T-P4-01 4 migration: Staff, WorkSession, WorkSessionStaff, Appointment (defer StaffCapability sang Phase 9).
- T-P4-02 UNIQUE constraint (location_id, session_date, session_type) trên WorkSession.
- T-P4-03 Service `staff_service.py` + `scheduling_service.py`.
- T-P4-04 Seed: 29 staff (Thành, Nam, Hùng, Hằng, Thiệp, Quyết, Linh, Đào? + KTV + CSKH + LT...).
- T-P4-05 Tool: `create_appointment()`, `cancel_appointment()`, `confirm_appointment()`.
- T-P4-06 `is_training` field hoạt động (gate exclude khỏi auto-assign).
- T-P4-07 Test: tạo WorkSession, gắn staff với station, tạo appointment.

**Files expected:**
```
src/migrations/20260523_*.sql (4 files)
src/migrations/seed/004_staff.sql
src/clinicai/services/staff_service.py
src/clinicai/services/scheduling_service.py
src/clinicai/tools/scheduling/*.py
src/tests/services/test_scheduling.py
```

**DoD:**
- Insert 29 staff seeded.
- Tạo WorkSession buổi tối thứ 2 + 5 staff với station khác nhau.
- Tạo Appointment đúng location_id, đúng queue_number format ("2A", "ƯT1").
- Q-25 (BS Đào): chấp nhận `is_active=FALSE` nếu chưa confirm.

**Tests:**
- `test_worksession_unique` (cannot create duplicate).
- `test_walkin_appointment_nullable` (appointment_id nullable trong visit).
- `test_is_training_excluded` (training staff không xuất hiện trong assignee pool).

**Risks:** Station ENUM khác Q-28 still open. Mitigation: dùng station list từ Hoa Session 24 + lưu vào master data table (config-as-data).

**Rollback:** DOWN 4 migrations.

---

### Phase 5 — EventLog + Queue + Worker skeleton

**Goal:** RabbitMQ queue chạy, EventLog append-only enforced, worker process consume từ queue.

**Prerequisites:** Phase 4 done.

**Tasks:**
- T-P5-01 Migration EventLog table + trigger `enforce_append_only()`.
- T-P5-02 Docker Compose RabbitMQ trên VPS.
- T-P5-03 Adapter base class: `BaseAdapter` với method `normalize() -> InteractionEvent` + `emit()`.
- T-P5-04 Worker process: consume từ topic `interaction.*` → call Golden Record Engine.
- T-P5-05 Golden Record Engine skeleton: identity resolution → write Patient → emit event_log row.
- T-P5-06 trace_id propagation từ adapter → queue → worker → DB.
- T-P5-07 Integration test: mock InteractionEvent → worker process → EventLog ghi đúng.

**Files expected:**
```
src/migrations/20260524_*.sql
src/clinicai/event_bus/
├── adapters/base.py
├── consumer.py
└── publisher.py
src/clinicai/golden_record/engine.py
src/tests/integration/test_event_flow.py
```

**DoD:**
- RabbitMQ admin UI accessible.
- Publish event "interaction.test" → consumer log "received."
- Trigger enforce_append_only(): UPDATE event_log → DB error.
- trace_id present in event_log payload.

**Tests:**
- `test_event_log_immutable` (UPDATE fails).
- `test_event_log_appendable` (INSERT works).
- `test_trace_id_propagation`.

**Risks:** RabbitMQ single instance = SPOF. Acceptable MVP. Cluster Phase 3.

**Rollback:** Disable consumer, queue messages buffer trong RabbitMQ.

---

### Phase 6 — Services / Tools full coverage

**Goal:** Mọi domain service Layer 2 + Tool Layer 3 cho Phase 1 entities sẵn sàng cho LangGraph.

**Prerequisites:** Phase 3, 4, 5 done.

**Tasks:**
- T-P6-01 Audit: list mọi tool cần cho 6 sub-graphs (theo `00_SYSTEM_OVERVIEW` §6).
- T-P6-02 Implement tools: `get_patient_summary`, `find_oncall_staff`, `send_zalo_message_stub`, `classify_lab_result_stub`, `read_kb_policy`, `create_task`, etc.
- T-P6-03 Tools nhận `TraceContext`, return typed Pydantic models.
- T-P6-04 Unit test mỗi tool (mock Supabase + RabbitMQ).
- T-P6-05 OpenAPI doc cho FastAPI endpoints expose tool layer.

**Files expected:**
```
src/clinicai/tools/
├── patient/get_summary.py
├── scheduling/find_oncall.py
├── communication/send_zalo.py (stub Phase 6, real Phase 12)
├── lab/classify.py (stub)
├── kb/read_policy.py
└── task/create.py
src/clinicai/api/v1/router.py
src/tests/tools/*.py
```

**DoD:**
- Mỗi tool có docstring + Pydantic input/output schema.
- 100% tool có unit test pass.
- OpenAPI `/docs` render đầy đủ.

**Tests:** Unit test cho từng tool (≥3 case mỗi tool: happy, edge, error).

**Risks:** Tool boundary fuzzy → tool gọi tool. Mitigation: tool gọi service, không gọi tool khác.

**Rollback:** Git revert.

---

### Phase 7 — Dashboard shell (read-only)

**Goal:** Next.js dashboard chạy được, hiển thị WorkSession + Patient list + Task backlog real-time.

**Prerequisites:** Phase 3, 4 done.

**Tasks:**
- T-P7-01 Next.js 15 (App Router) + Supabase Auth + Tailwind.
- T-P7-02 3 pages: `/work-sessions`, `/patients`, `/tasks`.
- T-P7-03 Supabase Realtime subscription cho tasks pending.
- T-P7-04 Auth flow: chỉ staff (Supabase users) login được.
- T-P7-05 Deploy dashboard lên VPS (Caddy reverse proxy + Docker).

**Files expected:**
```
src/dashboard/
├── app/(dashboard)/work-sessions/page.tsx
├── app/(dashboard)/patients/page.tsx
├── app/(dashboard)/tasks/page.tsx
├── lib/supabase.ts
└── Dockerfile
```

**DoD:**
- Truy cập `https://dash.clinicai.local/work-sessions` show list.
- Tạo Task qua API → Dashboard tự update qua Realtime.

**Tests:** Cypress smoke test cho 3 page load.

**Risks:** Supabase Realtime row-count limit. Mitigation: filter theo location_id + status.

**Rollback:** Take down dashboard Docker container; backend vẫn chạy.

---

### Phase 8 — LangGraph Orchestrator skeleton

**Goal:** Orchestrator Graph nhận InteractionEvent → route đến sub-graph stub.

**Prerequisites:** Phase 5, 6 done.

**Tasks:**
- T-P8-01 Install LangGraph 1.0+, PostgresSaver.
- T-P8-02 Migration `langgraph_checkpoint` schema (LangGraph tự generate, run sync command).
- T-P8-03 Orchestrator graph: 1 entry node + 1 router node + 6 dispatch nodes (stub) + 1 exit node.
- T-P8-04 State schema: `OrchestratorState (event, patient_ctx, work_session_ctx, trace_id, route)`.
- T-P8-05 Wire RabbitMQ consumer → invoke graph.
- T-P8-06 Test: publish event → graph dispatch đúng sub-graph stub → exit ghi event_log.

**Files expected:**
```
src/clinicai/graphs/
├── orchestrator/state.py
├── orchestrator/nodes.py
├── orchestrator/graph.py
└── orchestrator/router.py
src/tests/graphs/test_orchestrator.py
```

**DoD:**
- Publish event type="zalo.message" → Orchestrator route đến Communication stub.
- Publish event type="lab.result" → route Lab Triage stub.
- Checkpoint table có row sau mỗi run.

**Tests:** 6 test, mỗi event type 1 case.

**Risks:** Checkpoint table phình. Mitigation: TTL policy Phase 13.

**Rollback:** Disable consumer.

---

### Phase 9 — Sub-graphs theo thứ tự

**Build theo thứ tự ưu tiên:**

```
9.1 Communication Graph     (intent extract + reply) — first because Zalo cần luôn
9.2 Scheduling Graph        (appointment lifecycle)  — second because volume lớn
9.3 Task Manager Graph      (auto-assign + SLA)      — third because gate cho Lab
9.4 Lab Triage Graph        (GROUP_C gate)           — fourth because safety critical
9.5 Pre-visit Brief Graph   (30' pre-shift)          — fifth because nice-to-have
9.6 StaffCapability         (multi-role backup)      — sixth, defer Phase 9 cuối
9.7 Voice-to-EMR Graph      (Phase 2/3)              — defer
```

**Mỗi graph có format task riêng theo template trong `03_TASK_DELEGATION_RULES`.**

**Common DoD cho mỗi graph:**
- State schema typed.
- Context Contract written ở `wiki/agent-policy/contracts/<graph>.md` TRƯỚC khi code.
- Tools đầy đủ từ Phase 6.
- Prompts ở `src/clinicai/graphs/<name>/prompts/` (Phase 9) hoặc `wiki/agent-policy/prompts/` (Phase 10 sau khi KB sync).
- Checkpoint cleanup test.
- Integration test happy path + 1 safety negative test.

---

### Phase 10 — KB Sync + Policy-as-Data

**Goal:** Hoa edit file markdown `wiki/agent-policy/sla.md` → sync job tự pickup → `kb_policy_rule` table cập nhật → graphs đọc rule mới ở runtime.

**Prerequisites:** Phase 9.3 (Task Manager) done.

**Tasks:**
- T-P10-01 Migration `kb_page`, `kb_chunk`, `kb_policy_rule`.
- T-P10-02 Sync job: scan `wiki/`, parse front-matter + body, upsert vào DB.
- T-P10-03 3 retrieval strategies:
  - `agent_policy` → JSONB query bằng `policy_key`.
  - `clinical` → pgvector cosine với MiniLM embeddings.
  - `operations` → tsvector full-text.
- T-P10-04 Role-based ownership: `owner_role` ENUM + `kb_role_assignment`.
- T-P10-05 GitHub Action: trên `wiki/**` change → trigger sync job qua webhook.
- T-P10-06 Test: edit markdown → push → DB row cập nhật trong 30s.

**Files expected:**
```
src/migrations/20260601_*.sql
src/clinicai/kb/sync.py
src/clinicai/kb/retriever.py
wiki/
├── agent-policy/
│   ├── sla.md
│   ├── routing.md
│   └── escalation.md
├── clinical/
└── operations/
```

**DoD:**
- Edit `wiki/agent-policy/sla.md` line "LAB_REVIEW: warn=90min" → "60min" → push → after sync, query `SELECT rule_data FROM kb_policy_rule WHERE policy_key='LAB_REVIEW.sla.warn'` returns 60.
- Task Manager Graph dùng SLA mới cho task tạo sau sync.

**Tests:**
- `test_sync_idempotent`.
- `test_markdown_wins_on_diverge`.
- `test_role_assignment_constraint` (mỗi role ≥1 active staff).

**Risks:** Sync job lag → graphs dùng rule cũ. Mitigation: Task snapshot `policy_snapshot` (frozen at creation).

**Rollback:** Restore wiki/ từ git commit trước + force re-sync.

---

### Phase 11 — AI Model Gateway

**Goal:** Mọi LLM call đi qua `model_gateway` với routing: Qwen local → Haiku → Sonnet theo độ phức tạp.

**Prerequisites:** Phase 9.1 done.

**Tasks:**
- T-P11-01 `model_gateway.py`: interface `chat(messages, complexity) -> Response`.
- T-P11-02 Routing logic: `complexity in ['trivial', 'simple']` → Qwen local; `['medium']` → Haiku; `['complex', 'reasoning']` → Sonnet.
- T-P11-03 Fallback: Qwen unavailable → Haiku; Haiku timeout → Sonnet.
- T-P11-04 Cost tracking: log mỗi call vào `event_log` với cost estimate.
- T-P11-05 Per-graph default complexity (Pre-visit Brief = Sonnet, Communication intent = Haiku, summarize Zalo log = Qwen).
- T-P11-06 Migrate mọi LLM call hiện tại sang gateway.

**Files expected:**
```
src/clinicai/ai/
├── model_gateway.py
├── providers/
│   ├── anthropic.py
│   ├── qwen_local.py
│   └── base.py
└── cost_tracker.py
```

**DoD:**
- Call gateway với complexity='trivial' → Qwen được gọi (nếu available).
- Mac Mini down → fallback Haiku, log warning.
- Weekly cost report query OK.

**Tests:**
- `test_routing_by_complexity`.
- `test_fallback_on_qwen_down`.
- `test_cost_logged_per_call`.

**Risks:** Qwen quality khác Haiku → output regression. Mitigation: golden task eval suite (Phase 13).

**Rollback:** Force complexity='complex' globally → Sonnet only (đắt nhưng quality).

---

### Phase 12 — Zalo / Pancake Integration (real, không stub)

**Goal:** Token Zalo OA + Pancake API key cấu hình xong, send Zalo thật hoạt động.

**Prerequisites:** Phase 11 done. **Quang/Hoa cấp token.**

**Tasks:**
- T-P12-01 Pancake Adapter: webhook receiver + normalize → InteractionEvent.
- T-P12-02 Zalo OA outbound: `send_zalo_message()` real, không stub.
- T-P12-03 Zalo OA inbound webhook: secondary path (Pancake primary).
- T-P12-04 Rate limit handling (Zalo OA limit unknown — bắt đầu 60/min/conversation conservative).
- T-P12-05 Retry-on-fail (exponential backoff, 3 lần, sau cùng human queue).
- T-P12-06 End-to-end test: gửi Zalo test → BN nhận → reply → ClinicAI process.

**Files expected:**
```
src/clinicai/adapters/
├── pancake_adapter.py
├── zalo_adapter.py
└── _common/rate_limiter.py
```

**DoD:**
- BN test (Quang) gửi tin nhắn "Đặt lịch" → Communication Graph route → reply qua Zalo trong <10s.
- Pancake webhook duplicate event → idempotent (event_id dedup).

**Tests:** E2E test với test Zalo account.

**Risks:** Pancake API thay đổi (đã có precedent). Mitigation: version pin + integration test chạy nightly.

**Rollback:** Disable webhook receiver, queue events buffer.

---

### Phase 13 — Production Hardening

**Goal:** Hệ thống chạy production 24/7 ổn định. Quan sát được. Backup được. Bảo mật.

**Prerequisites:** Phase 12 done.

**Tasks:**
- T-P13-01 Structured JSON logging + log shipping (Loki hoặc Supabase Logs).
- T-P13-02 Health check endpoints + Uptime monitor (UptimeRobot/BetterStack).
- T-P13-03 Supabase backup restore test (real restore vào staging).
- T-P13-04 Secrets management: GitHub Secrets + VPS env file mode 0600.
- T-P13-05 Checkpoint cleanup job (Q-N11): TTL 30 days.
- T-P13-06 Crypto-erase pattern (Q-N01): encrypted PII columns, drop key on "forget" request.
- T-P13-07 Eval suite: 50 golden Zalo messages + 20 golden lab results + 5 golden pre-visit briefs. Chạy CI mỗi commit.
- T-P13-08 Incident runbook in `wiki/operations/runbook/`.

**Files expected:**
```
src/clinicai/observability/logging.py
src/clinicai/observability/health.py
src/clinicai/jobs/checkpoint_cleanup.py
src/clinicai/security/crypto_erase.py
tests/eval/golden_*.jsonl
wiki/operations/runbook/incident_response.md
```

**DoD:**
- Uptime monitor → green for 1 week consecutive.
- Restore từ backup → khôi phục đủ.
- Eval suite ≥95% pass.

**Tests:** Eval suite + restore test.

**Risks:** Eval suite drift. Mitigation: weekly review.

**Rollback:** Production rollback procedure trong runbook.

---

## 3. Cơ chế thay đổi task khi PM đổi hướng (Change Request — CR)

```
CHANGE REQUEST FORMAT (file: .ai/change_requests/CR-YYYYMMDD-NN.md)

# CR-YYYYMMDD-NN — <tiêu đề>

**Source:** Quang (chat) | clinic stakeholder | discovery
**Date:** YYYY-MM-DD
**Phase affected:** P3 | P9.2 | etc.
**Severity:** small | medium | large

## Yêu cầu thay đổi
<1-3 câu mô tả thay đổi>

## Impact analysis
- Decisions ảnh hưởng (D###): ...
- Constraints ảnh hưởng (§C##): ...
- Files cần sửa: ...
- Tests cần thêm/sửa: ...
- Migration mới? yes/no
- Phase cần re-do? yes/no

## Scope boundary
- Trong scope CR này: ...
- KHÔNG trong scope (CR khác): ...

## Decision
Accept | Reject | Needs more info

## Owner
<AI agent hoặc người chịu trách nhiệm>
```

**Quy tắc:**

1. **Small CR** (1-2 file, không phá decision): tự handle, ghi trong report task hiện tại.
2. **Medium CR** (1 phase, không phá architecture): tạo CR file, escalate Claude Chat, update task list.
3. **Large CR** (phá architecture, đổi schema lớn, đổi tech stack): **STOP code**, schedule review session, có thể tạo ADR mới.

**Không bao giờ:**
- Bỏ qua impact analysis "vì nhỏ thôi."
- Sửa Loại A decision mà không có CR explicit.
- Sửa schema production mà không có migration.

**Khi nào cần review lại architecture:**
- Tech stack change (đổi Supabase → Self-host).
- Channel change (thêm Telegram chẳng hạn — nhưng đã bị cấm).
- Safety gate change (đổi GROUP_C rule).
- Sub-graph re-shape.

## 4. Task template (GitHub issue style)

Xem `03_TASK_DELEGATION_RULES.md` cho format đầy đủ. Tóm tắt:

```markdown
# T-YYYYMMDD-NN — <imperative title>

**Assigned to:** Claude Code | Codex | Antigravity | Qwen
**Priority:** P0 | P1 | P2 | P3
**Phase:** P<N>
**Estimated:** S | M | L | XL

## Goal (1-2 câu)
## Why (link Decisions / Open Questions)
## Scope
### In-scope (file list)
### Out-of-scope (explicit)
## Acceptance criteria (measurable)
- [ ] ...
## Constraints to respect
## Decisions referenced
## Assumptions to confirm before coding
## DoD
```

## 5. Quy tắc không code lan man

```
1. Mỗi task touch ≤5 file (trừ migration). Hơn 5 → split task.
2. Không refactor adjacent code. K3.
3. Không "while I was here" config change.
4. Không thêm dependency mới mà không có CR.
5. Không sửa file ngoài in-scope list.
6. Khi gặp bug khác trong scope task → ghi note vào report, KHÔNG fix.
7. Khi gặp doc sai trong scope task → ghi note vào report, KHÔNG sửa.
8. Khi hoài nghi về architecture decision → STOP, hỏi Claude Chat.
9. Khi test fail vì lý do không liên quan task → STOP, escalate.
10. Khi cần thêm time → escalate; KHÔNG yawn code overnight.
```

---

*01_IMPLEMENTATION_ROADMAP_AND_TASKS.md · 2026-05-20 · 13 phases · CR framework · task template ref to file 03.*
