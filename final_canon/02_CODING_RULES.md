# 02 — Coding Rules (Quy tắc code production)

> Quy tắc bắt buộc cho mọi code commit vào ClinicAI repo. AI agents và human đều theo.
> Vi phạm rule này → reviewer block PR, không có ngoại lệ.
> Cập nhật: 2026-05-20 · Status: **CANON**

---

## 1. Tech versions (cứng)

```
Python:           3.12.x          (cứng — không 3.11, không 3.13)
PostgreSQL:       16              (Supabase Cloud default)
Node.js:          20 LTS          (dashboard Next.js)
TypeScript:       5.5+
FastAPI:          0.110+
LangGraph:        1.0+
Pydantic:         2.7+
SQLAlchemy:       2.0+            (async)
pgvector:         0.7+
RabbitMQ:         3.13+
Docker Engine:    25+
Poetry:           1.8+            (package manager)
```

**Lý do version cứng:** tránh "works on my machine." Bump version chỉ qua CR.

## 2. Backend style (Python / FastAPI)

### 2.1 Type hints bắt buộc

```python
# YES
def get_patient(patient_id: UUID) -> Patient | None:
    ...

# NO — thiếu return type
def get_patient(patient_id):
    ...
```

Mọi function public phải có type hint đầy đủ (input + return). `mypy --strict` chạy trong CI.

### 2.2 Async-first

```python
# YES — async cho mọi I/O (DB, HTTP, queue)
async def fetch_patient(patient_id: UUID) -> Patient | None:
    return await db.fetch_one("SELECT * FROM patient WHERE clinic_patient_id = $1", patient_id)

# NO — sync DB call trong handler async
@router.get("/patient/{id}")
async def get_patient(id: UUID):
    return sync_db_call(id)  # BLOCKS event loop
```

### 2.3 Pydantic schema cho mọi I/O boundary

```python
class CreatePatientRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=200)
    date_of_birth: date
    phone: str = Field(pattern=r"^\+84\d{9,10}$")
    national_id_number: str | None = Field(default=None, pattern=r"^\d{12}$")

class PatientResponse(BaseModel):
    clinic_patient_id: UUID
    patient_code: str
    full_name: str
    # ... explicit fields, never dict[str, Any]
```

**Không dùng** `dict[str, Any]` trong API response. Mọi field explicit.

### 2.4 Dependency injection FastAPI

```python
# YES
async def get_db_session() -> AsyncIterator[AsyncSession]:
    async with async_session_maker() as session:
        yield session

@router.post("/patient")
async def create_patient(
    request: CreatePatientRequest,
    db: AsyncSession = Depends(get_db_session),
    trace: TraceContext = Depends(get_trace_context),
) -> PatientResponse:
    ...
```

**Không** module-level global state cho DB/Redis/etc.

## 3. LangGraph style

### 3.1 State schema typed (TypedDict hoặc Pydantic)

```python
from typing import TypedDict
from clinicai.types import TraceContext, PatientContext, WorkSessionContext

class OrchestratorState(TypedDict):
    event: InteractionEvent
    patient_ctx: PatientContext | None
    work_session_ctx: WorkSessionContext | None
    trace: TraceContext
    route: Literal["scheduling", "lab_triage", "task_manager", "communication", "pre_visit_brief", "voice_emr"] | None
    error: str | None
```

### 3.2 Node = pure function nhận state, return state delta

```python
# YES
async def extract_intent(state: CommunicationState) -> dict:
    intent = await model_gateway.classify_intent(state["event"].message)
    return {"intent": intent}

# NO — return mutated state, side-effect write to DB
async def extract_intent_bad(state):
    intent = await model_gateway.classify_intent(...)
    state["intent"] = intent  # mutation
    await db.execute("INSERT INTO event_log ...")  # side-effect ngoài tool
    return state
```

### 3.3 Tools (Layer 3) là cách duy nhất node side-effect

```python
# YES
async def store_intent_node(state: CommunicationState) -> dict:
    await tools.event_log.append(
        actor_type="AGENT",
        event_type="INTENT_EXTRACTED",
        payload={"intent": state["intent"]},
        trace=state["trace"],
    )
    return {}

# NO — node viết SQL trực tiếp
async def store_intent_node_bad(state):
    await db.execute("INSERT INTO event_log ...")
    return {}
```

### 3.4 Prompts trong file riêng

```python
# YES
from clinicai.graphs.communication.prompts import INTENT_EXTRACTION_PROMPT

async def extract_intent(state):
    response = await model_gateway.chat(
        system=INTENT_EXTRACTION_PROMPT,
        user=state["event"].message,
        complexity="simple",
    )

# NO — prompt inline
async def extract_intent_bad(state):
    response = await anthropic.messages.create(
        system="You are a clinic assistant. Classify the intent...",  # inline = bad
        ...
    )
```

**Prompt location:**
- Phase 1-9: `src/clinicai/graphs/<name>/prompts/<purpose>.md`
- Phase 10+: `wiki/agent-policy/prompts/<purpose>.md` (KB-loaded)

### 3.5 Checkpoint mandatory

```python
from langgraph.checkpoint.postgres import AsyncPostgresSaver

graph = StateGraph(OrchestratorState)
# ... add nodes ...
compiled = graph.compile(checkpointer=async_postgres_saver)
```

Mọi sub-graph có checkpointer. Không có graph "ad-hoc" không checkpoint.

## 4. Service / Tool boundary

```
SERVICE (Layer 2)                       TOOL (Layer 3)
- Business logic                         - Thin wrapper expose service to graph
- DB transaction                         - Pure function, deterministic
- Multiple step orchestration           - 1 verb, 1 outcome
- Examples:                              - Examples:
  - patient_service.create_patient()       - tools.patient.find_by_phone()
  - mpi_service.resolve_identity()        - tools.scheduling.book_appointment()
  - lab_service.classify_and_route()      - tools.kb.read_policy(policy_key)
                                          - tools.event_log.append(...)
```

**Quy tắc:**

```
✓ Graph node gọi Tool, không gọi Service trực tiếp.
✓ Tool gọi Service.
✓ Service gọi DB + Service khác.
✗ Tool gọi Tool. (sai layer, gây loop)
✗ Service gọi Graph. (đảo chiều)
✗ Graph gọi DB trực tiếp. (bypass tool boundary)
```

## 5. Error handling

### 5.1 Use exceptions, không return error tuple

```python
# YES
class PatientNotFoundError(ClinicAIError):
    pass

async def get_patient_or_raise(pid: UUID) -> Patient:
    p = await patient_service.find_by_id(pid)
    if p is None:
        raise PatientNotFoundError(f"Patient {pid} not found")
    return p

# NO — Go-style
async def get_patient_bad(pid: UUID) -> tuple[Patient | None, str | None]:
    p = await patient_service.find_by_id(pid)
    if p is None:
        return None, "not_found"
    return p, None
```

### 5.2 Exception hierarchy

```python
ClinicAIError                       # base
├── DomainError                     # business logic errors
│   ├── PatientNotFoundError
│   ├── DuplicatePatientError
│   ├── InvalidVisitStateError
│   └── SafetyGateBlockedError      # GROUP_C, FINALIZED, etc.
├── IntegrationError                # external API errors
│   ├── ZaloAPIError
│   ├── PancakeAPIError
│   └── SupabaseError
├── ValidationError                 # input invalid (Pydantic raises this)
└── ConfigError                     # missing env, bad config
```

### 5.3 Bắt exception cụ thể, không `except Exception`

```python
# YES
try:
    await zalo_send(...)
except ZaloRateLimitError:
    await queue_for_retry(...)
except ZaloAPIError as e:
    logger.error("zalo_send_failed", error=str(e), trace_id=trace.id)
    raise

# NO
try:
    await zalo_send(...)
except Exception:  # too broad
    pass
```

### 5.4 Safety gate violations → raise, không return

```python
async def notify_patient_lab_result(patient_id, lab_result_id):
    result = await lab_service.get_result(lab_result_id)
    if result.classification == "GROUP_C" and result.bs_reviewed_at is None:
        raise SafetyGateBlockedError(
            gate="GROUP_C_REVIEW",
            resource=lab_result_id,
            reason="Doctor has not reviewed this critical result yet",
        )
    # ... proceed to notify
```

## 6. Logging

### 6.1 Structured JSON, không print/format string

```python
import structlog
logger = structlog.get_logger()

# YES
logger.info(
    "patient_created",
    patient_id=str(patient.clinic_patient_id),
    patient_code=patient.patient_code,
    source_channel=event.channel,
    trace_id=trace.id,
)

# NO
print(f"Created patient {patient.clinic_patient_id}")
logger.info(f"Created patient {patient.clinic_patient_id}")  # f-string trong log = no structured fields
```

### 6.2 Always include `trace_id`

Mọi log line từ một request/event phải có cùng `trace_id`. Propagation:
```
Adapter (assigns trace_id) → Event Bus (carries) → Graph state (carries) →
  Service (receives via context) → DB (writes to event_log.trace_id)
```

### 6.3 Không log PII

```python
# YES
logger.info("patient_lookup", patient_code="BN-2026-000123", trace_id=trace.id)

# NO — log full name, phone, CCCD
logger.info("patient_lookup", full_name=patient.full_name, phone=patient.phone)
```

Nếu cần debug PII: ghi vào `event_log` (audit table) chứ không phải application logs.

## 7. Testing

### 7.1 Pyramid

```
       /\
      /  \  E2E (few, slow)
     /----\
    /      \  Integration (some, medium)
   /--------\
  /          \  Unit (many, fast)
 /------------\
```

Mục tiêu coverage Phase 1:
- Unit: ≥80% line coverage cho services + tools.
- Integration: 1 cho mỗi sub-graph + 1 cho mỗi adapter.
- E2E: 1 happy path cho mỗi user-facing workflow.

### 7.2 Naming

```python
def test_<module>__<scenario>__<expected>():
    ...

# Examples
def test_patient_service__create_with_existing_phone__creates_with_warning():
    ...

def test_lab_triage__group_c_unreviewed__blocks_notification():
    ...

def test_mpi__cccd_match_overrides_phone__returns_existing_patient():
    ...
```

### 7.3 Safety gate negative test BẮT BUỘC

```python
async def test_lab_triage__group_c_unreviewed__raises_safety_gate_error():
    """GATE: CSKH MUST NOT notify patient about GROUP_C lab when bs_reviewed_at IS NULL."""
    lab_result = await create_test_lab(classification="GROUP_C", bs_reviewed_at=None)

    with pytest.raises(SafetyGateBlockedError) as exc:
        await lab_service.notify_patient(lab_result.id)

    assert exc.value.gate == "GROUP_C_REVIEW"
```

Mọi sub-graph touching safety gate có ≥1 negative test.

### 7.4 Fixtures qua factory-boy hoặc trực tiếp

```python
# YES — async fixture với cleanup
@pytest.fixture
async def test_patient(db_session) -> Patient:
    p = await patient_service.create(
        full_name="Test User",
        phone="+84900000001",
        date_of_birth=date(1990, 1, 1),
    )
    yield p
    await db_session.execute("DELETE FROM patient WHERE clinic_patient_id = $1", p.clinic_patient_id)
```

### 7.5 No `time.sleep` trong test

Dùng `asyncio.wait_for` + event-based async. Sleep = flaky test.

## 8. Migrations

### 8.1 Format file

```
src/migrations/
└── YYYYMMDD_NNN_<description>.sql      # UP
└── YYYYMMDD_NNN_<description>.down.sql  # DOWN (mandatory)
```

Ví dụ: `20260521_001_create_clinic_location.sql` + `20260521_001_create_clinic_location.down.sql`.

### 8.2 Mỗi migration phải:

```sql
-- 20260521_001_create_clinic_location.sql
BEGIN;

CREATE TABLE clinic_location (
    location_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_code TEXT NOT NULL UNIQUE,
    location_name TEXT NOT NULL,
    address TEXT,
    phone TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_clinic_location_active ON clinic_location(is_active) WHERE is_active = TRUE;

COMMENT ON TABLE clinic_location IS 'Master data: clinic sites (KN, HN, future)';

COMMIT;
```

```sql
-- 20260521_001_create_clinic_location.down.sql
BEGIN;
DROP TABLE IF EXISTS clinic_location CASCADE;
COMMIT;
```

### 8.3 Quy tắc migration

```
✓ Mọi migration trong TRANSACTION (BEGIN/COMMIT).
✓ Mọi migration có DOWN script.
✓ Apply order theo timestamp prefix.
✓ Idempotent: apply 2 lần không error (dùng IF NOT EXISTS, IF EXISTS).
✓ Test trên DB local trước khi push.
✓ Comment cho mọi table + complex column.
✗ Không sửa migration đã merged vào main — tạo migration mới reverse.
✗ Không UPDATE/DELETE data trong migration trừ khi seed.
✗ Không drop column production mà không backward-compat ≥30 days.
✗ Không sửa schema bằng tay trên Supabase Dashboard.
```

### 8.4 Breaking changes

Drop column / change column type / rename column:
1. Migration N: thêm column mới (nullable).
2. Migration N+1: backfill data từ column cũ → mới.
3. Code change: read mới, write cả mới + cũ.
4. Wait 30 days production.
5. Migration N+2: code chỉ read/write mới.
6. Migration N+3: drop column cũ.

## 9. Config / env

### 9.1 Không hardcode

```python
# YES
import os
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]

# NO
ANTHROPIC_API_KEY = "sk-ant-xxx"  # never
```

### 9.2 Pydantic Settings

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    anthropic_api_key: str
    supabase_url: str
    supabase_service_role_key: str
    rabbitmq_url: str
    zalo_oa_access_token: str | None = None  # nullable trong dev
    qwen_local_url: str = "http://mac-mini.local:8080"
    log_level: str = "INFO"
    environment: Literal["dev", "staging", "prod"] = "dev"

    class Config:
        env_file = ".env"

settings = Settings()
```

### 9.3 `.env.example` trong repo

`.env` trong `.gitignore`. `.env.example` trong git với placeholder values.

### 9.4 Secrets

- Production: VPS env file mode 0600, owner = service user.
- CI: GitHub Secrets.
- Local dev: `.env` (gitignored).
- Không bao giờ commit secret. `pre-commit` hook scan secret pattern.

## 10. Security

```
✓ Mọi SQL qua parameterized query (SQLAlchemy hoặc asyncpg với $1, $2).
✗ Không string interpolation SQL (SQL injection).

✓ Authentication: Supabase Auth + JWT cho dashboard, service-role key cho backend.
✓ RLS (Row-Level Security) enable Phase 2+ cho dashboard tables.
✗ Không bypass RLS bằng service-role key trong code chạy thay user.

✓ HTTPS only production. Let's Encrypt qua Caddy.
✗ Không HTTP cho external endpoint.

✓ CORS whitelist explicit (dashboard origin only).
✗ Không `Access-Control-Allow-Origin: *`.

✓ Rate limiting: external API + webhook ingress.
✓ Webhook signature verification (Zalo, Pancake nếu support).

✓ PII handling: log → event_log only, không application logs.
✓ Crypto-erase pattern Phase 13 cho NĐ13/2023 right-to-forget.
✗ Không gửi audio ra ngoài clinic (PhoWhisper on-prem only).

✓ Dependency scan: `pip-audit` + `safety` chạy CI.
✓ Secret scan: `truffleHog` hoặc `gitleaks` pre-commit.
```

## 11. Naming conventions

```
SQL:
  Table:        snake_case singular        patient, work_session, lab_result
  Column:       snake_case                 clinic_patient_id, created_at
  FK:           <referenced>_id            patient_id, location_id
  Index:        idx_<table>_<columns>      idx_patient_phone
  Constraint:   <table>_<purpose>_check    patient_phone_format_check
  Trigger:      <table>_<action>_trigger   event_log_append_only_trigger

Python:
  Module:       snake_case                 patient_service.py
  Class:        PascalCase                 PatientService
  Function:     snake_case                 create_patient()
  Constant:     UPPER_SNAKE                MAX_PATIENT_PER_DAY
  Type alias:   PascalCase                 PatientID = UUID

TypeScript:
  Component:    PascalCase                 PatientList.tsx
  Function:     camelCase                  fetchPatient()
  Type:         PascalCase                 PatientResponse

File:
  Migration:    YYYYMMDD_NNN_<desc>.sql    20260521_001_create_clinic_location.sql
  Test:         test_<module>.py           test_patient_service.py
  Task:         T-YYYYMMDD-NN              T-20260601-01
  Report:       <task-id>.md               T-20260601-01.md
  CR:           CR-YYYYMMDD-NN.md          CR-20260615-01.md
```

## 12. File organization

```
clinicai/                                    # repo root
├── CLAUDE.md                                # Claude session entry point
├── README.md
├── pyproject.toml
├── docker-compose.yml
├── .env.example
├── .gitignore
├── .pre-commit-config.yaml
├── .github/
│   └── workflows/
│       ├── ci.yml
│       └── kb_sync.yml
│
├── context/                                  # canon docs
├── final_canon/                              # this directory
├── _audit/
├── .ai/
│   ├── TASK_TEMPLATE.md
│   ├── REPORT_TEMPLATE.md
│   ├── REVIEW_CHECKLIST.md
│   ├── tasks/
│   ├── reports/
│   ├── worklog/
│   └── change_requests/
│
├── wiki/                                     # KB markdown source of truth
│   ├── agent-policy/
│   │   ├── sla.md
│   │   ├── routing.md
│   │   ├── escalation.md
│   │   ├── contracts/                       # Context Contracts
│   │   └── prompts/                          # prompts after KB sync (Phase 10+)
│   ├── clinical/
│   │   ├── obstetrics/
│   │   └── gynecology/
│   └── operations/
│       ├── sop/
│       └── runbook/
│
└── src/                                      # code
    ├── clinicai/
    │   ├── __init__.py
    │   ├── settings.py                       # Pydantic Settings
    │   ├── types.py                          # shared types
    │   ├── exceptions.py                     # exception hierarchy
    │   │
    │   ├── adapters/
    │   │   ├── _base.py
    │   │   ├── pancake_adapter.py
    │   │   ├── zalo_adapter.py
    │   │   └── walkin_adapter.py
    │   │
    │   ├── event_bus/
    │   │   ├── consumer.py
    │   │   └── publisher.py
    │   │
    │   ├── golden_record/
    │   │   └── engine.py
    │   │
    │   ├── services/
    │   │   ├── patient_service.py
    │   │   ├── mpi_service.py
    │   │   ├── scheduling_service.py
    │   │   ├── staff_service.py
    │   │   ├── lab_service.py
    │   │   ├── task_service.py
    │   │   ├── kb_service.py
    │   │   └── communication_service.py
    │   │
    │   ├── tools/
    │   │   ├── patient/
    │   │   ├── scheduling/
    │   │   ├── lab/
    │   │   ├── task/
    │   │   ├── kb/
    │   │   ├── communication/
    │   │   └── event_log/
    │   │
    │   ├── graphs/
    │   │   ├── _common/                      # state types, base node helpers
    │   │   ├── orchestrator/
    │   │   ├── scheduling/
    │   │   ├── lab_triage/
    │   │   ├── task_manager/
    │   │   ├── communication/
    │   │   ├── pre_visit_brief/
    │   │   └── voice_emr/
    │   │
    │   ├── ai/
    │   │   ├── model_gateway.py
    │   │   ├── providers/
    │   │   └── cost_tracker.py
    │   │
    │   ├── kb/
    │   │   ├── sync.py
    │   │   └── retriever.py
    │   │
    │   ├── api/
    │   │   └── v1/
    │   │
    │   ├── observability/
    │   │   ├── logging.py
    │   │   └── tracing.py
    │   │
    │   └── jobs/                              # background jobs
    │       └── checkpoint_cleanup.py
    │
    ├── migrations/
    │   ├── seed/
    │   └── *.sql
    │
    └── tests/
        ├── conftest.py
        ├── unit/
        ├── integration/
        ├── e2e/
        └── eval/                              # golden task suite
```

## 13. Forbidden (CẤM)

```
✗ Graph node ghi DB trực tiếp (phải qua tool).
✗ Tool gọi LLM trực tiếp (phải qua model_gateway).
✗ Service contain prompt string (phải import từ prompts/).
✗ Business rule hardcoded trong code (phải vào KB markdown).
✗ AI quyết định safety gate (gate phải code + human).
✗ Sửa schema production qua Supabase Dashboard (phải migration).
✗ DELETE từ append-only table (event_log, task_event, visit_amendment, drug_inventory_transaction, supply_inventory_transaction, FINALIZED visit).
✗ UPDATE FINALIZED visit row (chỉ tạo visit_amendment).
✗ Phone là PK/FK (clinic_patient_id only).
✗ ENUM hardcode cho ServiceType/BookingChannel/LabPartner (master data table).
✗ Adapter ghi Domain DB (chỉ emit event).
✗ Audio ra ngoài clinic (PhoWhisper local only).
✗ Telegram/SMS/email cho patient hoặc staff comm (Zalo only).
✗ Risk scoring AI (cấm cho đến N=50K outcomes).
✗ Free-form clinical advice AI cho BN (legal red line).
✗ Tool gọi Tool khác (sai layer).
✗ `dict[str, Any]` trong API response (explicit Pydantic).
✗ `except Exception` quá rộng.
✗ `print()` trong code production (structlog).
✗ Log PII vào application logs (event_log only).
✗ Hardcode API key/secret (env only).
✗ Sync DB call trong async handler.
✗ Migration không có DOWN script.
✗ Test phụ thuộc `time.sleep`.
✗ Commit `.env` hoặc secret.
✗ Refactor adjacent code khi đang fix bug khác (K3).
✗ `--no-verify` skip pre-commit hooks.
```

## 14. Mandatory (LUÔN LÀM)

```
✓ Type hints đầy đủ.
✓ Pydantic schema cho API I/O.
✓ Migration có DOWN script.
✓ Test cho mọi safety gate (negative test).
✓ trace_id propagation end-to-end.
✓ event_log row cho mọi mutation.
✓ Pre-commit hooks pass.
✓ CI pass trước merge.
✓ Update DECISIONS.md khi lock decision mới.
✓ Update OPEN_QUESTIONS.md khi tạo gap mới.
✓ Update CURRENT_ARCHITECTURE_STATE.md khi ORANGE → GREEN.
✓ Report sau mỗi task theo .ai/REPORT_TEMPLATE.md.
✓ Context Contract trước khi build agent mới.
✓ K1 K2 K3 K4 (Karpathy principles).
```

---

*02_CODING_RULES.md · 2026-05-20 · Vi phạm = block PR.*
