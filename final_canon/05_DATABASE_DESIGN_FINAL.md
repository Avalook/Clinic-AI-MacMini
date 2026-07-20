# 05 — Database Design Final (Thiết kế DB cuối cùng)

> Schema canon: v6 (35 entities · 9 domains). Field-level reference: `~/Documents/ClinicAI/ClinicAI_v6_Schema_Memory_1.md`.
> File này: giải thích **vì sao** + **migration strategy** + **so sánh với chuẩn quốc tế**.
> Cập nhật: 2026-05-20 · Status: **CANON**

---

## 1. Final domain model — 9 domains · 35 entities

```
D1 Cross-domain Master Data     3 tables       Phase 1
   ├── ClinicLocation
   ├── ServiceType
   └── BookingChannel

D2 Patient                       5 tables       Phase 1 (toàn bộ)
   ├── Patient ⭐
   ├── PatientContactChannel
   ├── PatientMedicalProfile
   ├── Pregnancy
   └── PatientNextOfKin

D3 Clinical (Khám & Bệnh án)    5 tables       Phase 2
   ├── Visit ⭐
   ├── ClinicalRecord (SOAP)
   ├── VisitAmendment
   ├── UltrasoundRecord
   └── Prescription

D4 Staff & Scheduling            5 tables       Phase 1 (4) + Phase 2 (1)
   ├── Staff
   ├── StaffCapability           (Phase 2)
   ├── WorkSession ⭐
   ├── WorkSessionStaff
   └── Appointment

D5 Lab                            3 tables       Phase 2
   ├── LabPartner
   ├── LabOrder
   └── LabResult

D6 Task Management                2 tables       Phase 2
   ├── Task ⭐
   └── TaskEvent (append-only)

D7 Finance                        2 tables       Phase 2
   ├── Invoice
   └── InvoiceLineItem

D8 Inventory                      6 tables       Phase 3
   ├── Drug
   ├── DrugBatch
   ├── DrugInventoryTransaction (append-only)
   ├── Supply
   ├── ServiceSupplyMapping
   └── SupplyInventoryTransaction (append-only)

D9 Infrastructure                 4 tables       Phase 1 (1) + Phase 2 (3)
   ├── EventLog ⭐ (append-only)
   ├── KBPage
   ├── KBChunk (pgvector)
   └── KBPolicyRule
```

## 2. Master data BUILD FIRST (D1)

```
LÝ DO:
- Tất cả entity vận hành (Appointment, Visit, Task, LabOrder, ...) đều FK đến
  ClinicLocation / ServiceType / BookingChannel.
- Sai master data sau khi có data → backfill khó, vì FK đã tồn tại.

BUILD ORDER:
1. ClinicLocation (2 rows: KN, HN)
2. ServiceType (15 rows từ Notion data, aliases TEXT[] cho fuzzy)
3. BookingChannel (9 rows từ session log Q4 analysis)

TRƯỚC khi build D2, D3, D4 nào.
```

## 3. Patient identity design — TƯ LIỆU CHỦ ĐỀ

### 3.1 Three-layer identifier

```
┌──────────────────────────────────────────────────────────────────┐
│  IDENTITY LAYER 1: clinic_patient_id (UUID)                      │
│  ─────────────────────────────────────────                       │
│  - Primary key bất biến                                          │
│  - System-generated (gen_random_uuid())                           │
│  - KHÔNG bao giờ hiển thị cho user                                │
│  - KHÔNG bao giờ thay đổi sau insert                              │
│  - FK target cho mọi child entity                                 │
│                                                                   │
│  WHY: SĐT là tài sản nhà mạng. Tên dupes. Zalo ID đổi device.    │
│       UUID không phụ thuộc ngoài clinic control.                  │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│  IDENTITY LAYER 2: patient_code (TEXT, UNIQUE)                   │
│  ─────────────────────────────────────────                       │
│  - Format: BN-YYYY-XXXXXX (e.g., BN-2026-000123)                  │
│  - Human-readable, immutable                                      │
│  - HIỂN THỊ cho user, in thẻ, đọc qua điện thoại                  │
│  - Generated khi tạo Patient (advisory lock đảm bảo sequential)   │
│                                                                   │
│  WHY: UUID không thể đọc qua điện thoại, không in được thẻ.       │
│       patient_code cho UX + audit.                                │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│  IDENTITY ANCHOR 3: national_id_number (CCCD, NULLABLE)          │
│  ────────────────────────────────────────────────                │
│  - 12 digits Vietnam Citizen ID                                   │
│  - NULLABLE (collected gradually, không bắt buộc)                 │
│  - Partial UNIQUE: WHERE national_id_number IS NOT NULL           │
│  - Khi present: OVERRIDE phone trong MPI dedup                    │
│  - KHÔNG dùng làm PK/FK                                           │
│  - KHÔNG hiển thị cho BN (internal only)                          │
│                                                                   │
│  WHY: CCCD là identity strongest từ nhà nước, không duplicate.    │
│       Nhưng làm mandatory sẽ block onboarding BN không có sẵn.    │
└──────────────────────────────────────────────────────────────────┘

KÊNH RIÊNG: Patient.phone (NOT NULL) + PatientContactChannel rows
─────────────────────────────────────────────────────────────────
Patient.phone           — IDENTITY ANCHOR (verify, ground truth khi digital fails)
PatientContactChannel   — ROUTING (Zalo, Phone, FB, Email…)
                          Channel-agnostic: thêm kênh = thêm row, không migrate.
```

### 3.2 Master Patient Index (MPI) — dedup logic

```
INPUT: full_name, date_of_birth, phone, national_id_number, zalo_user_id

SCORING (weighted):
- CCCD match (both have, both equal):                +1.0  (winning)
- Phone match (E.164 normalized):                    +0.5
- DOB match:                                          +0.3
- Name fuzzy (Levenshtein normalized):               +0.2
- Zalo user_id match:                                +0.4

THRESHOLDS:
- score ≥ 1.0  → AUTO_MERGE (CCCD wins always)
- 0.7 ≤ score < 1.0 → AUTO_MATCH (no merge needed, just link)
- 0.4 ≤ score < 0.7 → HUMAN_REVIEW_QUEUE
- score < 0.4 → CREATE_NEW

PREFER FALSE-POSITIVE (queue) over FALSE-MERGE (silent merge wrong patient).

WHY: phòng khám đã có duplicate thực tế (Loại B Session 4): cùng người,
SĐT mẹ + SĐT cá nhân. CCCD là cứu cánh duy nhất.
```

### 3.3 PatientContactChannel — schema channel-agnostic

```sql
CREATE TABLE patient_contact_channel (
    channel_record_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_patient_id UUID NOT NULL REFERENCES patient(clinic_patient_id),
    channel_type TEXT NOT NULL CHECK (channel_type IN ('ZALO','PHONE','FACEBOOK','EMAIL','WHATSAPP','TIKTOK')),
    channel_value TEXT NOT NULL,         -- zalo_user_id, +84..., FB PSID, email, ...
    is_verified BOOLEAN NOT NULL DEFAULT FALSE,
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    verified_at TIMESTAMPTZ,
    last_active_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (channel_type, channel_value)
);

CREATE INDEX idx_pcc_patient ON patient_contact_channel(clinic_patient_id);
CREATE INDEX idx_pcc_lookup  ON patient_contact_channel(channel_type, channel_value);
```

**Patient.phone vẫn giữ song song** — Patient.phone là identity anchor (verify), PatientContactChannel là routing (gửi tin).

## 4. Staff / StaffCapability / WorkSession

```
Staff (persistent)
├── staff_id              UUID PK
├── full_name, short_name  TEXT
├── primary_department    DOCTOR | ULTRASOUND_DOCTOR | NURSE_ULTRASOUND | RECEPTION | CSKH | MANAGEMENT
├── primary_location_id   FK → ClinicLocation (nullable; Q-23 chưa rõ rotate hay fixed)
├── is_training           BOOLEAN  → gate exclude auto-assign
├── is_active             BOOLEAN
└── employment_type       FULL_TIME | PART_TIME | CONTRACT

StaffCapability (junction, Phase 2)
├── id                    UUID PK
├── staff_id              FK → Staff
├── capability            RECEPTION | CASHIER | PHLEBOTOMY | ULTRASOUND_NURSE | CSKH | DOCTOR_CONSULTATION
├── proficiency_level     TRAINING | COMPETENT | EXPERT
└── UNIQUE (staff_id, capability)

WHY junction: phòng khám nhỏ VN nhân viên bắt buộc đa năng. Hardcode 1 role
→ không auto-assign backup được. Capability persistent, station per-session.

WorkSession (per-session)
├── session_id            UUID PK
├── location_id           FK → ClinicLocation (NOT NULL)
├── session_date          DATE
├── session_type          EVENING | WEEKEND_MORNING | WEEKEND_AFTERNOON
├── start_time, end_time  TIME
├── max_patients          INT
└── UNIQUE (location_id, session_date, session_type)

WorkSessionStaff (junction per session)
├── id                    UUID PK
├── work_session_id       FK
├── staff_id              FK
├── role                  TEXT
├── station               ULTRASOUND_1 | EXAM_ROOM_1 | RECEPTION | PHLEBOTOMY | ...
├── on_call_flag          BOOLEAN
└── is_training           BOOLEAN  (snapshot at session creation)

PREREQUISITE: WorkSession là prerequisite cho Task auto-assignment.
Không có WorkSession → Orchestrator không biết ai on-duty → không assign được.
```

## 5. Appointment vs Visit — 2 entity riêng

```
WHY 2 entities:
- Walk-in: không có Appointment, có Visit.
- No-show: có Appointment, không có Visit.
- Reschedule: 1 Patient có nhiều Appointment cancel; 1 Visit duy nhất khi đến.

Appointment (booking intent)
├── appointment_id         UUID PK
├── clinic_patient_id      FK
├── doctor_id              FK → Staff
├── work_session_id        FK
├── location_id            FK
├── service_type_id        FK
├── booking_channel_id     FK
├── slot_start, slot_end   TIMESTAMP
├── assigned_station       TEXT
├── queue_number           TEXT       (CSKH quyết; "2A", "ƯT1")
├── is_priority_slot       BOOLEAN
├── is_walkin              BOOLEAN
├── status                 SCHEDULED → CONFIRMED → CHECKED_IN → COMPLETED | NO_SHOW | CANCELLED
└── confirmed_at, cancellation_reason, cancelled_at

Visit (actual encounter)
├── visit_id               UUID PK
├── clinic_patient_id      FK
├── appointment_id         FK (NULLABLE — walk-in không có)
├── work_session_id        FK
├── attending_doctor_id    FK
├── location_id            FK (denormalized from appointment for historical accuracy)
├── service_type_id        FK (denormalized)
├── status                 OPEN → IN_PROGRESS → FINALIZED → AMENDED
├── finalized_at, finalized_by
└── checked_in_at, checked_in_by

VISIT STATUS MACHINE GATE:
- OPEN / IN_PROGRESS → UPDATE cho phép (staff sửa lỗi thời gian thực).
- FINALIZED          → application layer + DB trigger CHẶN UPDATE.
- AMENDED            → trang thái sau khi có ≥1 VisitAmendment.

Chỉ tạo VisitAmendment để đính chính sau FINALIZED. Đây là yêu cầu pháp lý
(TT13/2011/TT-BYT).
```

## 6. Clinical Record (SOAP) + Visit Amendment

```
ClinicalRecord (1:1 với Visit)
├── record_id              UUID PK
├── visit_id               FK UNIQUE
├── pregnancy_id           FK NULLABLE
├── soap_subjective        JSONB    (S: BN kể gì)
├── soap_objective         JSONB    (O: BS khám/đo gì + vitals)
├── soap_assessment        JSONB    (A: Chuẩn đoán + ICD-10)
├── soap_plan              JSONB    (P: kế hoạch + thuốc + tái khám)
├── chief_complaint_at_visit  TEXT
├── voice_note_url         TEXT      (LOCAL storage, KHÔNG cloud)
├── voice_transcript       TEXT      (PhoWhisper output)
└── voice_note_reviewed    BOOLEAN   (GATE: voice draft → final)

SOAP backbone từ BS Hùng (Session 24, Loại B):
- S: Lý do đến khám
- O: Kết quả khám lâm sàng (gồm vitals)
- A: Chuẩn đoán
- P: Kế hoạch điều trị + Thuốc kê + Lịch tái khám/XN

VisitAmendment (APPEND-ONLY)
├── amendment_id           UUID PK
├── visit_id               FK
├── amended_by             FK → Staff
├── amended_at             TIMESTAMP IMMUTABLE
├── reason                 TEXT (bắt buộc)
├── corrected_fields       TEXT[]
├── original_values        JSONB
└── corrected_values       JSONB

Trigger enforce_append_only() chặn UPDATE/DELETE.
```

## 7. Lab GROUP_A/B/C and SAFETY GATE

```
LabResult.result_classification ENUM:
- GROUP_A   Bình thường              CSKH notify BN trực tiếp.
- GROUP_B   Cần theo dõi             Q-27 OPEN: BS review trước hay CSKH notify thẳng?
- GROUP_C   Cần can thiệp            HARD GATE: CSKH KHÔNG được notify
                                      cho đến bs_reviewed_at IS NOT NULL.
- PENDING   Chưa classify             Block notification until classified.

ENFORCE 2-layer:
1. Application layer (Lab Triage Graph + lab_service.notify_patient):
   IF classification = 'GROUP_C' AND bs_reviewed_at IS NULL:
       raise SafetyGateBlockedError(gate='GROUP_C_REVIEW')

2. DB function check_can_notify(result_id) trả về BOOLEAN.
   notification service phải gọi function này trước khi gửi Zalo.

Test bắt buộc: negative test — GROUP_C unreviewed → notify raises error.
```

## 8. Task management + TaskEvent

```
Task
├── task_id               UUID PK
├── task_type             LAB_REVIEW | LAB_NOTIFY | SLOT_FILL | APPOINTMENT_CONFIRM |
│                          INTAKE_FOLLOWUP | PRESCRIPTION_DISPENSE | PATIENT_CALLBACK
├── clinic_patient_id     FK NULLABLE
├── assigned_to           FK → Staff NULLABLE (NULL = unassigned)
├── work_session_id       FK
├── location_id           FK
├── context_ref           JSONB  (entity_type + entity_id)
├── policy_snapshot       JSONB  (SLA snapshot at creation — KEY DECISION)
├── sla_warn_at, sla_breach_at, due_at
├── status                OPEN → ASSIGNED → IN_PROGRESS → SLA_WARN → ESCALATED
│                          → REASSIGNED → DONE | CANCELLED
├── compensation_tag      CSKH_CALL | CSKH_CONFIRM | CSKH_NOTIFY | CSKH_ADMIN | ...
├── escalated_to, escalated_at
└── completed_at, completed_by, completion_notes

POLICY SNAPSHOT KEY DECISION:
Khi tạo task, snapshot SLA từ KB vào policy_snapshot JSONB.
KB rule changes KHÔNG retroactive — task đã tạo dùng policy lúc tạo.

WHY: Không snapshot → Hoa edit SLA → task đang OPEN bỗng dưng breach retroactively.

TaskEvent (APPEND-ONLY)
├── event_id              UUID PK
├── task_id               FK
├── event_type            CREATED | ASSIGNED | STARTED | SLA_WARNED | ESCALATED |
│                          REASSIGNED | FORWARDED | COMPLETED | CANCELLED | NOTE_ADDED
├── actor_id              FK → Staff NULLABLE (NULL = system)
├── payload               JSONB
└── event_at              TIMESTAMP IMMUTABLE
```

## 9. KB tables (Phase 2)

```
KBPage
├── page_id               UUID PK
├── page_key              TEXT UNIQUE   (e.g., "agent-policy/sla")
├── title                 TEXT
├── category              agent_policy | clinical | operations | faq_internal
├── content_md            TEXT          (Markdown body)
├── file_path             TEXT          (path trong wiki/)
├── owner_role            CLINICAL_LEAD | CLINICAL_DOCTOR | OPS_MANAGER | DEVELOPER
├── status                DRAFT | REVIEW | ACTIVE | DEPRECATED
├── last_reviewed_at, review_cycle_days  (event-driven, không scheduled)
├── retrieval_strategy    structured_jsonb | semantic | fulltext
└── tsvector_content      tsvector      (for category='operations')

KBChunk (pgvector, for category='clinical')
├── chunk_id              UUID PK
├── page_id               FK
├── chunk_index           INT
├── chunk_text            TEXT
└── embedding             vector(384)   (MiniLM-L12-v2)

CREATE INDEX idx_kbchunk_embedding ON kb_chunk USING hnsw (embedding vector_cosine_ops);

KBPolicyRule (for category='agent_policy')
├── rule_id               UUID PK
├── page_id               FK
├── policy_key            TEXT UNIQUE   (e.g., "LAB_REVIEW.sla.warn")
├── rule_data             JSONB
├── is_active             BOOLEAN
└── created_at, updated_at

KBRoleAssignment (mapping role → staff)
├── id                    UUID PK
├── owner_role            ENUM
├── staff_id              FK
├── is_active             BOOLEAN
└── CHECK: mỗi role có ≥1 active assignment (enforce at app layer)
```

## 10. EventLog (append-only, audit central)

```
EventLog
├── log_id                UUID PK
├── actor_id              FK → Staff NULLABLE
├── actor_type            STAFF | AGENT | SYSTEM | MIGRATION
├── event_type            TEXT (e.g., PATIENT_CREATED, LAB_RESULT_REVIEWED, TASK_ASSIGNED)
├── entity_type           TEXT (e.g., 'patient', 'visit', 'task')
├── entity_id             TEXT (UUID as text)
├── payload               JSONB
├── location_id           FK
├── session_id_ref        FK → WorkSession NULLABLE
├── trace_id              UUID                (per-request correlation)
├── ip_address, user_agent TEXT
└── logged_at             TIMESTAMP IMMUTABLE

Trigger enforce_append_only_event_log() — block UPDATE/DELETE.

Retention: ≥7 years (TT13/2011).

KEY: trace_id propagate adapter → graph → service → event_log row.
Future debug: SELECT * FROM event_log WHERE trace_id = '...' ORDER BY logged_at;
```

## 11. PatientSummary — materialized vs on-demand

**Q-19 OPEN, đề xuất quyết định:**

```
RECOMMEND: MATERIALIZED (background job incremental update)

Reasoning:
- Pre-visit Brief cần 7 fields từ 5 bảng + KB lookup. On-demand = ~2-5s latency
  cho mỗi brief. 30 BN/ngày × 5s = 2.5 phút tổng — chấp nhận được nhưng peaky.
- Materialized: brief = 1 SELECT (~10ms). Background job update khi: Patient/Visit/
  Lab/Pregnancy event. Stale tối đa ~60s.
- Trade-off: 1 thêm bảng `patient_summary` + 1 background job + drift risk 60s.
- Verdict: drift 60s acceptable vì brief gửi 30' trước WorkSession; 60s drift
  không bao giờ là vấn đề clinical critical.

SCHEMA:
patient_summary
├── clinic_patient_id     FK PK (1:1)
├── current_ga_weeks      NUMERIC
├── current_pregnancy_id  FK
├── chronic_diseases      TEXT[]
├── current_medications   TEXT[]
├── allergies             TEXT[]
├── last_visit_summary    JSONB
├── latest_ultrasound_summary  JSONB
├── latest_lab_summary    JSONB
├── ongoing_issues        TEXT[]
├── last_updated_at       TIMESTAMP
└── update_trigger_event_id  UUID  (debug: event nào triggered update)

QUYẾT ĐỊNH: tentative cho đến Quang xác nhận trong review.
```

## 12. LangGraph Checkpoint tables

```
LangGraph PostgresSaver tự tạo bảng. Schema mặc định:
- checkpoints                  (main checkpoint store)
- checkpoint_blobs             (large state)
- checkpoint_writes            (pending writes)

Cấu hình: schema riêng `langgraph_checkpoints` (không trộn với domain DB).

CLEANUP POLICY (Phase 13):
- TTL: 30 days post-completion.
- Background job: DELETE WHERE created_at < NOW() - INTERVAL '30 days' AND status='completed'.
- KHÔNG cleanup checkpoints với status='paused' (đang chờ human).
```

## 13. Migration strategy — chi tiết

### 13.1 Tool

```
NOT use:
- Alembic     — Magic too much, mismatched with our app code (no SQLAlchemy ORM full).
- Supabase migrations CLI  — Vendor lock-in.

USE:
- Simple Python runner: scan src/migrations/*.sql, track applied in
  schema_migrations table.

src/clinicai/migrations/runner.py:
- apply()      run all pending UP scripts in alphabetical order
- rollback()   run latest applied DOWN
- status()     show applied/pending
```

### 13.2 File naming

```
YYYYMMDD_NNN_<description>.sql       — UP
YYYYMMDD_NNN_<description>.down.sql  — DOWN

NNN = 001..999, sequential per day.

Ví dụ:
20260521_001_create_clinic_location.sql
20260521_001_create_clinic_location.down.sql
20260521_002_create_service_type.sql
20260521_002_create_service_type.down.sql
```

### 13.3 Migration discipline (REPEAT FROM 02_CODING_RULES §8)

```
✓ Trong BEGIN/COMMIT transaction.
✓ Có DOWN script.
✓ Idempotent (IF NOT EXISTS).
✓ Test local trước.
✓ Comment table + complex column.
✗ Không UPDATE/DELETE data (trừ seed).
✗ Không sửa migration đã merged → tạo migration mới reverse.
✗ Không drop column production mà không backward-compat 30 days.
```

## 14. Seed strategy

```
seed/
├── 001_clinic_locations.sql      (2 rows: KN, HN)
├── 002_service_types.sql         (15 rows + aliases TEXT[])
├── 003_booking_channels.sql      (9 rows)
├── 004_staff.sql                 (29 rows; pseudonymized in dev)
└── ...

QUY TẮC SEED:
- Idempotent: ON CONFLICT DO UPDATE / DO NOTHING.
- Production seed run 1 lần manual với Quang approval.
- Dev seed: fake data, không bao giờ real PII trong git.
- Test seed: pytest fixture, không qua file SQL.
```

## 15. Fix bug / schema evolution strategy

### 15.1 Add column safe (non-breaking)

```sql
-- Migration N
ALTER TABLE patient ADD COLUMN national_id_number TEXT;
CREATE UNIQUE INDEX patient_national_id_uniq
  ON patient (national_id_number) WHERE national_id_number IS NOT NULL;
COMMIT;

-- Application code: dùng được luôn (column nullable).
```

### 15.2 Add NOT NULL column (breaking, multi-step)

```
Step 1 — Migration N: add column nullable.
Step 2 — Backfill via script (not in migration).
Step 3 — Application: write to new column.
Step 4 — Migration N+1: ALTER COLUMN SET NOT NULL.

KHÔNG add NOT NULL trong 1 migration với data đã tồn tại.
```

### 15.3 Rename column (breaking)

```
Step 1 — Migration N: add new column (nullable).
Step 2 — Application: write to both, read from new.
Step 3 — Backfill: copy old → new.
Step 4 — Wait ≥30 days production.
Step 5 — Migration N+1: drop old column.
```

### 15.4 Change column type

```
Same as rename: add new column with new type, backfill, switch, drop.
```

### 15.5 Drop column

```
Step 1 — Migration N: deprecate (rename to _deprecated_old_name).
Step 2 — Application: stop reading/writing.
Step 3 — Wait ≥30 days.
Step 4 — Migration N+1: drop.
```

### 15.6 Add index (non-blocking)

```sql
-- Use CONCURRENTLY for production
CREATE INDEX CONCURRENTLY idx_patient_phone ON patient(phone);

-- Note: CREATE INDEX CONCURRENTLY cannot be in transaction.
-- Migration runner must support non-transactional migrations (flag in filename).
```

## 16. Backfill strategy

```
KHÔNG trong migration. Backfill = separate Python script.

scripts/backfill_<name>.py:
- Idempotent (re-run safe).
- Batch processed (1000 rows/iteration).
- Log progress to event_log (actor_type=MIGRATION).
- Run với --dry-run trước.
- Manual trigger only — không tự run trên CI.
```

## 17. Rollback strategy

```
CODE rollback:    git revert + redeploy previous Docker image.
SCHEMA rollback:  run DOWN scripts in reverse order.
DATA rollback:    Supabase point-in-time recovery (PITR, 7-day window in Pro plan).

Rule of three:
- Every PR has tested rollback path.
- Every breaking migration has parallel-run window.
- Every deploy keeps last 5 Docker images for quick revert.
```

## 18. Stale / duplicate avoidance

```
DUPLICATE PREVENTION:
- UNIQUE constraint on natural key combinations:
  patient: (phone, full_name) NOT enforce (allow legit dupe, MPI handles)
  patient_contact_channel: (channel_type, channel_value) UNIQUE
  patient: partial UNIQUE on national_id_number
  appointment: (work_session_id, queue_number) UNIQUE
  work_session: (location_id, session_date, session_type) UNIQUE

STALE PREVENTION:
- updated_at column on all mutable tables + set_updated_at() trigger.
- patient_summary: last_updated_at field; if NOW() - last_updated > 5 min,
  trigger refresh.
- kb_page: last_reviewed_at + status; "stale" pages flagged in dashboard.

EVENT LOG: every mutation logged. SELECT * FROM event_log WHERE entity_id = ?
gives full history.
```

## 19. So sánh với hệ thống trưởng thành

### 19.1 HL7 FHIR (Health Level 7 — chuẩn US/EU)

```
ÁP DỤNG (đã có sẵn):
- ServiceType.loinc_code + snomed_code (pre-allocate)
- Resource pattern: Patient, Practitioner (≈ Staff), Encounter (≈ Visit),
  Observation (≈ LabResult), Procedure (≈ UltrasoundRecord)
- Append-only audit (FHIR AuditEvent)

KHÔNG ÁP DỤNG MVP:
- Full FHIR API (GET /Patient/{id} as FHIR JSON) — Phase 3+.
- Bundle / Composition resources — overkill.
- US-Core profile — Vietnam specific khác.

Phase 2 sẽ thêm:
- LOINC code mapping cho ServiceType lab.
- SNOMED code mapping cho diagnosis trong ClinicalRecord.soap_assessment.
```

### 19.2 OpenMRS (open-source EMR widely used in developing countries)

```
ÁP DỤNG:
- Concept dictionary pattern (chúng ta dùng master data tables).
- Encounter + Observation + Order pattern (chúng ta tách Visit/LabOrder/Prescription).
- Person + Patient distinction (chúng ta gộp; có thể tách nếu cần Provider làm BN).

KHÔNG ÁP DỤNG:
- Java/JSP stack — đã chọn Python.
- Bahmni-style hospital integration — không scope.
```

### 19.3 Salesforce Health Cloud / CRM identity principles

```
ÁP DỤNG:
- Master record + ContactChannel (chúng ta dùng Patient + PatientContactChannel).
- Identity resolution scoring (chúng ta dùng MPI).
- Merge audit trail (chúng ta dùng event_log + Human Review Queue).

KHÔNG ÁP DỤNG:
- Multi-org / multi-tenant (single-tenant ClinicAI).
- Marketing automation cross-channel (không scope).
```

### 19.4 Event sourcing / audit log principles

```
ÁP DỤNG:
- Append-only event_log: every mutation generates event.
- Reproducible state: state = projection of events.
- TaskEvent: task lifecycle events.
- VisitAmendment: append-only corrections.

KHÔNG ÁP DỤNG:
- Full event sourcing (rebuild state from events) — not necessary at clinic scale.
- CQRS — overkill.
- Event store as primary DB — we use Postgres rows as primary, event_log as audit.
```

### 19.5 So sánh tóm tắt

| Aspect | FHIR | OpenMRS | Salesforce | Event Sourcing | ClinicAI |
|--------|------|---------|------------|----------------|----------|
| Patient PK | Resource ID | patient_id (UUID) | Account_ID | event aggregate | clinic_patient_id (UUID) ✓ |
| Master data | CodeSystem | Concept | Picklist | n/a | ServiceType/BookingChannel/Location ✓ |
| Audit | AuditEvent | Audit module | Field History | events ARE audit | event_log append-only ✓ |
| Identity | identifier slice | PersonAttribute | DupeJobs | n/a | MPI service + CCCD anchor ✓ |
| Multi-channel comm | Patient.telecom | PersonContactPoint | ContactChannel | n/a | PatientContactChannel ✓ |
| State machine | Encounter.status | Encounter.visitType | Stage | event types | Visit OPEN→FINALIZED→AMENDED + GROUP_C gate ✓ |

**Verdict:** ClinicAI schema **đã hấp thụ best practices** từ FHIR (identity + code system), OpenMRS (encounter pattern), Salesforce (CRM identity), event sourcing (audit). Không copy 1:1 cái nào — pragmatic hybrid.

## 20. Final recommendations — ClinicAI specific

```
RECOMMEND-1  KEEP v6 schema as canon (35 entities · 9 domains).
RECOMMEND-2  UPDATE 03_DATA_MODEL_AND_ENTITIES.md (currently 28 entities, stale).
RECOMMEND-3  ADD patient_summary materialized table (resolve Q-19 in favor of materialized).
RECOMMEND-4  ADD audit table schema_migration_log to track who applied what when.
RECOMMEND-5  ADD index: idx_patient_phone, idx_patient_cccd_partial, idx_appointment_session,
             idx_visit_patient, idx_lab_result_status, idx_task_assigned_status,
             idx_event_log_trace, idx_event_log_entity.
RECOMMEND-6  Foreign Key everywhere with ON DELETE RESTRICT (default) or ON DELETE CASCADE
             where appropriate (e.g., PatientContactChannel cascade delete with Patient).
RECOMMEND-7  Use Postgres GENERATED ALWAYS AS for derived columns where possible
             (e.g., Patient.age = GENERATED from date_of_birth).
RECOMMEND-8  Pgvector index = HNSW (default cosine), build_param: m=16, ef_construction=64.
             Tune after seeing real KB query patterns.
RECOMMEND-9  Enable RLS Phase 2+ for dashboard tables (staff can only see their own clinic).
RECOMMEND-10 Backup strategy: Supabase PITR + weekly logical dump to S3-compatible storage
             (Backblaze B2 cheap). Test restore monthly.

NEEDS_REVIEW (Quang quyết):
- Q-19 materialized vs on-demand patient_summary (RECOMMEND materialized).
- Q-23 staff.primary_location_id nullable vs NOT NULL when HN opens.
- Q-24 inventory per-location vs shared.
- Q-28 station ENUM mở rộng (PHLEBOTOMY, MEDICAL_SECRETARY, ...).
```

---

*05_DATABASE_DESIGN_FINAL.md · 2026-05-20 · Schema canon = v6. This file = rationale + migration strategy + benchmark.*
