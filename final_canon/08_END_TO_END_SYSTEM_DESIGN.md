# 08 — End-to-End System Design (Thiết kế hệ thống chi tiết)

> Repo structure, deploy flow, Docker, env, observability, security, backup, security.
> Cập nhật: 2026-05-20 · Status: **CANON**

---

## 1. Physical infrastructure

```
┌────────────────────────────────────────────────────────────────┐
│  HOME — Mac Mini M4 Pro 48GB                                   │
│  ─────────────────────────                                     │
│  Role:    Dev machine + AI worker fallback                     │
│  OS:      macOS 15 (Sequoia)                                    │
│  Tools:   Python 3.12, Poetry, Docker Desktop, VS Code,        │
│           Claude Code CLI, Codex, ngrok (dev webhook)          │
│  Running services:                                              │
│           - PhoWhisper-large-v3 (FastAPI server, port 8081)    │
│           - Qwen3-14B (vLLM server, port 8082)                  │
│           - MiniLM-L12-v2 (embedding service, port 8083)        │
│           - Tailscale VPN client                                │
│  Failure mode: graceful degradation. If down → API fallback.   │
└────────────────────────────────────────────────────────────────┘
                         │
                         │ Tailscale VPN (mesh)
                         ▼
┌────────────────────────────────────────────────────────────────┐
│  VPS — Production server 24/7                                  │
│  ─────────────────────────                                     │
│  Provider:  Vultr / DigitalOcean / Hetzner (Singapore region)   │
│  Spec:      4 vCPU / 8GB RAM / 80GB SSD (Phase 1)               │
│  OS:        Ubuntu 24.04 LTS                                    │
│  Stack:     Docker + Docker Compose                             │
│  Services:                                                       │
│           - clinicai-api          (FastAPI :8000)                │
│           - clinicai-worker       (LangGraph workers)            │
│           - clinicai-scheduler    (cron: pre-visit brief, etc.)  │
│           - clinicai-dashboard    (Next.js :3000)                │
│           - rabbitmq              (broker :5672, mgmt :15672)    │
│           - caddy                 (reverse proxy + Let's Encrypt)│
│           - tailscale             (VPN to Mac Mini)              │
│  Backups:   /etc backup hourly to S3-compatible. DB via Supabase│
│  Monitor:   UptimeRobot ping every 5 min.                       │
└────────────────────────────────────────────────────────────────┘
                         │
                         │ HTTPS (Caddy auto-TLS)
                         ▼
┌────────────────────────────────────────────────────────────────┐
│  SUPABASE CLOUD — Database / Auth / Storage                    │
│  ──────────────────────────────────                             │
│  Region:    Singapore (cùng VPS)                                │
│  Plan:      Pro (PITR 7-day, custom domains)                    │
│  Components:                                                     │
│           - PostgreSQL 16 + pgvector 0.7                        │
│           - Auth (Supabase Auth for dashboard users)            │
│           - Storage (small, mostly local audio NOT here)         │
│           - Realtime (subscriptions cho dashboard)               │
│  Backups:   Auto daily, PITR 7-day, manual logical dump weekly  │
│             to Backblaze B2.                                     │
└────────────────────────────────────────────────────────────────┘
                         │
       ┌─────────────────┼─────────────────┐
       ▼                 ▼                 ▼
┌──────────┐    ┌──────────────┐    ┌──────────────┐
│Anthropic │    │  Zalo OA     │    │ Lab Partners │
│  API     │    │  Pancake     │    │ Diag/Medlatec│
│          │    │              │    │              │
│ Claude   │    │ Webhook in   │    │ API + Email  │
│ Sonnet + │    │ + REST out   │    │ OCR fallback │
│ Haiku    │    │              │    │              │
└──────────┘    └──────────────┘    └──────────────┘
```

## 2. Deployment flow

```
[Code on Mac Mini]
       │
       │ git commit + push
       ▼
[GitHub repo: clinicai/]
       │
       │ GitHub Actions trigger
       ▼
[CI Pipeline]
       ├── pip install (poetry)
       ├── ruff check
       ├── mypy --strict
       ├── pytest (unit + integration)
       ├── docker build (api + worker + scheduler + dashboard)
       └── docker push to ghcr.io/clinicai/<service>:<sha>
       │
       │ On main branch: notify Quang
       ▼
[Quang manual approve]
       │
       │ ssh deploy command (one-liner)
       ▼
[VPS deploy]
       ├── docker compose pull (new images)
       ├── docker compose up -d --no-deps <service>
       ├── healthcheck wait 60s
       ├── smoke test (curl /health)
       └── rollback if smoke test fail (docker compose up <previous tag>)
       │
       ▼
[Production live]
       │
       └── UptimeRobot continuous monitoring
```

**Không có auto-deploy** (Loại A D056). Quang luôn manual approve. Reason: compliance + clinical impact.

## 3. Repo structure final

```
clinicai/                                  # GitHub: <org>/clinicai
│
├── README.md
├── CLAUDE.md                              # Claude session entry point
├── LICENSE                                # MIT or proprietary (Quang decide)
├── pyproject.toml                         # Poetry
├── poetry.lock
├── docker-compose.yml                      # local dev
├── docker-compose.prod.yml                 # production overlay
├── Dockerfile.api
├── Dockerfile.worker
├── Dockerfile.scheduler
├── Dockerfile.dashboard
├── Caddyfile                               # reverse proxy config
├── .env.example
├── .gitignore
├── .pre-commit-config.yaml
├── .editorconfig
│
├── .github/
│   └── workflows/
│       ├── ci.yml                          # lint + test + build on PR
│       ├── deploy-staging.yml              # auto staging on main
│       ├── kb-sync.yml                     # wiki/** change → trigger sync
│       └── nightly-eval.yml                # eval suite
│
├── context/                                # canon docs (CANON)
│   ├── PROJECT_BRIEF.md
│   ├── CONSTRAINTS.md
│   ├── DECISIONS.md
│   ├── ARCHITECTURE_SUMMARY.md
│   ├── CURRENT_ARCHITECTURE_STATE.md
│   ├── OPEN_QUESTIONS.md
│   ├── FILE_MAP.md
│   └── AI_TEAM_OPERATING_MODEL.md
│
├── final_canon/                            # decisive canon (this folder)
│   ├── 00_SYSTEM_OVERVIEW_AND_FINAL_ARCHITECTURE.md
│   ├── 01_IMPLEMENTATION_ROADMAP_AND_TASKS.md
│   ├── 02_CODING_RULES.md
│   ├── 03_TASK_DELEGATION_RULES.md
│   ├── 04_MULTI_AI_WORKING_MODEL.md
│   ├── 05_DATABASE_DESIGN_FINAL.md
│   ├── 06_HARD_DECISIONS_AND_STYLE.md
│   ├── 07_CONTEXT_AND_MEMORY_RULES.md
│   ├── 08_END_TO_END_SYSTEM_DESIGN.md
│   ├── 09_CLAUDE_AND_AGENT_INSTRUCTIONS.md
│   ├── 10_RESEARCH_AND_BENCHMARK_2026-05-20.md
│   └── 11_REVIEW_AGENDA_FOR_HUMAN.md
│
├── _audit/                                  # provenance (read-on-demand)
│   ├── INVENTORY.md
│   ├── VERSION_MAP.md
│   ├── BENCHMARK_2026Q2.md
│   └── REVIEW_AGENDA.md
│
├── _archive/                                # archived stale files
│   └── 2026-05/
│       ├── ClinicAI_SystemOverview.md
│       ├── ClinicAI_DevGuide_v3.md
│       └── ...
│
├── .ai/                                     # AI dev workflow
│   ├── TASK_TEMPLATE.md
│   ├── REPORT_TEMPLATE.md
│   ├── REVIEW_CHECKLIST.md
│   ├── tasks/
│   │   └── T-YYYYMMDD-NN.md
│   ├── reports/
│   │   └── T-YYYYMMDD-NN.md
│   ├── change_requests/
│   │   └── CR-YYYYMMDD-NN.md
│   └── worklog/
│       └── YYYYMMDD.md
│
├── wiki/                                    # KB markdown (source of truth)
│   ├── agent-policy/
│   │   ├── sla.md
│   │   ├── routing.md
│   │   ├── escalation.md
│   │   ├── contracts/
│   │   │   ├── orchestrator.md
│   │   │   ├── communication.md
│   │   │   ├── scheduling.md
│   │   │   ├── lab_triage.md
│   │   │   ├── task_manager.md
│   │   │   └── pre_visit_brief.md
│   │   └── prompts/
│   │       ├── intent_extraction.md
│   │       ├── reply_composer.md
│   │       ├── brief_assembler.md
│   │       └── ...
│   ├── clinical/
│   │   ├── obstetrics/
│   │   │   ├── trimester_milestones.md
│   │   │   ├── ultrasound_checklist.md
│   │   │   └── ...
│   │   └── gynecology/
│   ├── operations/
│   │   ├── sop/
│   │   │   ├── csk h_intake.md
│   │   │   ├── lab_handoff.md
│   │   │   └── ...
│   │   ├── runbook/
│   │   │   ├── incident_response.md
│   │   │   ├── deploy.md
│   │   │   ├── rollback.md
│   │   │   └── ...
│   │   └── faq-internal/
│   └── compliance/
│       ├── tt13-2011.md
│       ├── nd13-2023.md
│       └── fhir-mapping.md
│
└── src/                                      # code
    ├── clinicai/                             # Python package
    │   ├── __init__.py
    │   ├── __main__.py
    │   ├── settings.py
    │   ├── types.py
    │   ├── exceptions.py
    │   │
    │   ├── adapters/
    │   │   ├── _base.py
    │   │   ├── pancake_adapter.py
    │   │   ├── zalo_adapter.py
    │   │   ├── walkin_adapter.py
    │   │   └── hotline_adapter.py            (Phase 2/3)
    │   │
    │   ├── event_bus/
    │   │   ├── __init__.py
    │   │   ├── consumer.py
    │   │   ├── publisher.py
    │   │   └── topics.py                     # topic constants
    │   │
    │   ├── golden_record/
    │   │   ├── engine.py
    │   │   └── identity_resolver.py
    │   │
    │   ├── services/
    │   │   ├── patient_service.py
    │   │   ├── mpi_service.py
    │   │   ├── scheduling_service.py
    │   │   ├── staff_service.py
    │   │   ├── lab_service.py
    │   │   ├── task_service.py
    │   │   ├── kb_service.py
    │   │   ├── communication_service.py
    │   │   ├── inventory_service.py          (Phase 3)
    │   │   ├── billing_service.py            (Phase 2)
    │   │   └── _common/
    │   │       ├── db.py                     # SQLAlchemy async session
    │   │       └── transactional.py
    │   │
    │   ├── tools/
    │   │   ├── patient/
    │   │   │   ├── get_summary.py
    │   │   │   ├── find_by_phone.py
    │   │   │   ├── find_by_cccd.py
    │   │   │   └── ...
    │   │   ├── scheduling/
    │   │   ├── lab/
    │   │   ├── task/
    │   │   ├── kb/
    │   │   ├── communication/
    │   │   └── event_log/
    │   │
    │   ├── graphs/
    │   │   ├── _common/
    │   │   │   ├── checkpointer.py            # PostgresSaver config
    │   │   │   ├── state_helpers.py
    │   │   │   └── trace.py
    │   │   ├── orchestrator/
    │   │   │   ├── state.py
    │   │   │   ├── nodes.py
    │   │   │   ├── graph.py
    │   │   │   ├── router.py
    │   │   │   └── prompts/                  # Phase 1-9 inline; Phase 10+ from KB
    │   │   ├── scheduling/
    │   │   ├── lab_triage/
    │   │   ├── task_manager/
    │   │   ├── communication/
    │   │   ├── pre_visit_brief/
    │   │   └── voice_emr/                    # Phase 3
    │   │
    │   ├── ai/
    │   │   ├── model_gateway.py
    │   │   ├── cost_tracker.py
    │   │   └── providers/
    │   │       ├── anthropic_provider.py
    │   │       ├── qwen_local_provider.py
    │   │       └── _base.py
    │   │
    │   ├── kb/
    │   │   ├── sync.py
    │   │   ├── retriever.py
    │   │   ├── embedder.py
    │   │   └── front_matter.py
    │   │
    │   ├── api/
    │   │   ├── main.py                       # FastAPI app
    │   │   ├── v1/
    │   │   │   ├── patient.py
    │   │   │   ├── appointment.py
    │   │   │   ├── task.py
    │   │   │   ├── webhook.py                # Zalo, Pancake
    │   │   │   └── health.py
    │   │   └── dependencies.py
    │   │
    │   ├── observability/
    │   │   ├── logging.py                    # structlog
    │   │   ├── tracing.py
    │   │   └── metrics.py
    │   │
    │   ├── jobs/
    │   │   ├── checkpoint_cleanup.py
    │   │   ├── patient_summary_refresh.py
    │   │   ├── kb_sync_job.py
    │   │   └── pre_visit_brief_scheduler.py
    │   │
    │   └── security/
    │       ├── crypto_erase.py               # Phase 1.5
    │       └── webhook_verifier.py
    │
    ├── dashboard/                            # Next.js 15
    │   ├── package.json
    │   ├── tsconfig.json
    │   ├── next.config.js
    │   ├── app/
    │   │   ├── (auth)/
    │   │   │   └── login/page.tsx
    │   │   └── (dashboard)/
    │   │       ├── layout.tsx
    │   │       ├── work-sessions/page.tsx
    │   │       ├── patients/page.tsx
    │   │       ├── tasks/page.tsx
    │   │       └── kb-stale/page.tsx
    │   ├── components/
    │   ├── lib/
    │   │   └── supabase.ts
    │   └── Dockerfile
    │
    ├── migrations/
    │   ├── 20260521_001_create_clinic_location.sql
    │   ├── 20260521_001_create_clinic_location.down.sql
    │   └── seed/
    │
    └── tests/
        ├── conftest.py
        ├── unit/
        ├── integration/
        ├── e2e/
        └── eval/
            ├── golden_zalo_messages.jsonl
            ├── golden_lab_results.jsonl
            ├── golden_pre_visit_briefs.jsonl
            └── runner.py
```

## 4. Docker strategy

### 4.1 Multi-stage builds

```dockerfile
# Dockerfile.api (sample)
FROM python:3.12-slim AS builder

WORKDIR /build
RUN pip install poetry==1.8.3
COPY pyproject.toml poetry.lock ./
RUN poetry config virtualenvs.create false && \
    poetry install --no-dev --no-root --no-interaction

FROM python:3.12-slim AS runtime
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY src/clinicai ./clinicai
EXPOSE 8000
USER 1000
CMD ["uvicorn", "clinicai.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 4.2 Docker Compose — production

```yaml
# docker-compose.prod.yml
services:
  api:
    image: ghcr.io/clinicai/api:${VERSION}
    restart: unless-stopped
    env_file: .env.prod
    networks: [internal]
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      retries: 3

  worker:
    image: ghcr.io/clinicai/worker:${VERSION}
    restart: unless-stopped
    env_file: .env.prod
    networks: [internal]
    depends_on: [rabbitmq]

  scheduler:
    image: ghcr.io/clinicai/scheduler:${VERSION}
    restart: unless-stopped
    env_file: .env.prod
    networks: [internal]

  dashboard:
    image: ghcr.io/clinicai/dashboard:${VERSION}
    restart: unless-stopped
    env_file: .env.prod.dashboard
    networks: [internal]

  rabbitmq:
    image: rabbitmq:3.13-management-alpine
    restart: unless-stopped
    volumes:
      - rabbitmq_data:/var/lib/rabbitmq
    networks: [internal]

  caddy:
    image: caddy:2.8-alpine
    restart: unless-stopped
    ports: ["80:80", "443:443"]
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy_data:/data
      - caddy_config:/config
    networks: [internal, public]

networks:
  internal:
    internal: true
  public:

volumes:
  rabbitmq_data:
  caddy_data:
  caddy_config:
```

### 4.3 Docker discipline

```
✓ Multi-stage builds (giảm image size).
✓ Non-root user trong runtime image.
✓ Healthcheck cho mọi service.
✓ Restart policy `unless-stopped`.
✓ Volume cho stateful (RabbitMQ data, Caddy data).
✓ Network internal (services không expose port public, chỉ qua Caddy).
✓ Image tag = git SHA (immutable).
✗ Không `latest` tag.
✗ Không root user runtime.
✗ Không inline secret trong Dockerfile.
✗ Không bind-mount source code production (immutable image).
```

## 5. Environment management

### 5.1 Env files

```
.env.example         → in git, placeholder values
.env                 → local dev, in .gitignore
.env.prod            → on VPS only, mode 0600, owner = clinicai user
.env.test            → for CI, github secrets
```

### 5.2 .env.example

```ini
# === Core ===
ENVIRONMENT=dev                      # dev | staging | prod
LOG_LEVEL=DEBUG                      # DEBUG | INFO | WARN | ERROR

# === Database ===
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=           # backend only, never expose
DATABASE_URL=postgresql+asyncpg://...

# === RabbitMQ ===
RABBITMQ_URL=amqp://guest:guest@localhost:5672/

# === AI ===
ANTHROPIC_API_KEY=sk-ant-...
QWEN_LOCAL_URL=http://mac-mini.tailscale:8082
PHOWHISPER_LOCAL_URL=http://mac-mini.tailscale:8081
EMBEDDING_LOCAL_URL=http://mac-mini.tailscale:8083

# === External APIs ===
ZALO_OA_ACCESS_TOKEN=
ZALO_OA_OA_ID=
PANCAKE_API_KEY=
PANCAKE_PAGE_ID=
DIAG_API_KEY=
MEDLATEC_API_KEY=
KIOTVIET_CLIENT_ID=
KIOTVIET_CLIENT_SECRET=

# === Observability ===
SENTRY_DSN=                          # Phase 2+
LOG_SHIPPING_URL=                    # Phase 2+

# === Security ===
JWT_SECRET=                          # for dashboard auth (Supabase manages JWT, but custom claims need this)
WEBHOOK_SECRET_ZALO=
WEBHOOK_SECRET_PANCAKE=
CRYPTO_ERASE_KEY_PROVIDER=hashicorp  # or aws_kms | local_kms (Phase 1.5)
```

### 5.3 Pydantic Settings (typed)

```python
# src/clinicai/settings.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="forbid")

    environment: Literal["dev", "staging", "prod"] = "dev"
    log_level: str = "INFO"

    supabase_url: str
    supabase_service_role_key: str
    database_url: str
    rabbitmq_url: str

    anthropic_api_key: str
    qwen_local_url: str = "http://localhost:8082"
    phowhisper_local_url: str = "http://localhost:8081"
    embedding_local_url: str = "http://localhost:8083"

    zalo_oa_access_token: str | None = None
    pancake_api_key: str | None = None
    # ... rest
```

## 6. Logging / monitoring / observability

### 6.1 Logging stack

```
PRODUCTION CODE:
    structlog (JSON output)
        │
        ▼
    stdout (Docker captures)
        │
        ▼
    Loki / Promtail (Phase 2)
        │
        ▼
    Grafana (Phase 2) for query
```

### 6.2 Per-call invariants

```python
logger.info(
    "event_processed",                 # event_type (snake_case verb_noun)
    trace_id=str(trace.id),
    entity_type="visit",
    entity_id=str(visit_id),
    action="finalized",
    duration_ms=duration_ms,
    actor_type="STAFF",
    actor_id=str(staff_id),
)
```

### 6.3 Health checks

```
GET /health             → 200 if API + DB + RabbitMQ reachable
GET /health/db          → 200 if DB query succeeds
GET /health/queue       → 200 if RabbitMQ alive
GET /health/dependencies → JSON status of each external (Anthropic, Zalo)
```

### 6.4 Metrics (Phase 2+)

```
clinicai_events_processed_total{event_type, status}
clinicai_task_duration_seconds{task_type}
clinicai_safety_gate_blocked_total{gate}      # GROUP_C, FINALIZED, etc.
clinicai_ai_calls_total{provider, model, complexity}
clinicai_ai_cost_usd_total{provider, model}
clinicai_db_query_duration_seconds{operation}
```

### 6.5 Uptime monitoring

```
UptimeRobot (free):
- https://api.clinicai.<domain>/health         (5-min interval)
- https://dash.clinicai.<domain>               (5-min interval)
- Slack webhook khi down 2 consecutive checks.

Phase 2: BetterStack hoặc Datadog cho deeper.
```

## 7. Backup

### 7.1 Database

```
Layer 1: Supabase PITR (point-in-time recovery)
         - Auto, 7-day window (Pro plan)
         - Restore via Supabase console
         - For accidental DELETE/UPDATE

Layer 2: Weekly logical dump
         - cron Sunday 02:00 SGT
         - pg_dump → encrypted → Backblaze B2 / Wasabi
         - Retention 90 days
         - Run from VPS via Supabase service-role key

Layer 3: Monthly restore test
         - Restore latest dump to staging Supabase project
         - Run smoke tests
         - Confirm restore is working
         - Document in .ai/worklog/

KHÔNG để restore là "untested capability."
```

### 7.2 KB / wiki

```
Git remote = backup (GitHub).
Additional: nightly push to second remote (GitLab mirror) as paranoia.
```

### 7.3 Audio files (PhoWhisper output)

```
On-premise local disk (Mac Mini hoặc clinic NAS).
Backup:
- Daily rsync to external HDD trong clinic.
- KHÔNG cloud backup (NĐ13/2023).
- Retention: 90 days then archive offline.
```

## 8. Rollback

### 8.1 Code rollback (deploy)

```bash
# On VPS
docker compose -f docker-compose.prod.yml down api worker
VERSION=<previous-sha> docker compose -f docker-compose.prod.yml up -d api worker
# Smoke test
curl https://api.clinicai.<domain>/health
```

Time: <2 min. Quang only.

### 8.2 Schema rollback

```bash
python -m clinicai.migrations rollback   # DOWN latest migration
# Multi-step rollback:
python -m clinicai.migrations rollback --steps 3
```

If schema rollback dangerous (e.g., dropped column): PITR restore + redeploy old code.

### 8.3 Data rollback (PITR)

```
Supabase console → Settings → Database → Point-in-time Recovery
→ Select timestamp → Restore
```

10-30 min depending on DB size. Notify clinic during window.

## 9. Security

(Repeat key items từ 02_CODING_RULES §10, plus deploy-level.)

```
Network:
✓ Caddy (Let's Encrypt auto-TLS) front of every public service.
✓ Docker internal network — services không expose port public except Caddy.
✓ Tailscale VPN for Mac Mini ↔ VPS.
✗ No HTTP. HTTPS only.

Auth:
✓ Supabase Auth for dashboard (JWT + RLS).
✓ Service role key only in backend env, never frontend.
✓ Webhook signature verify (Zalo HMAC, Pancake nếu có).

Data:
✓ TLS in-transit (Caddy, Supabase, Anthropic all HTTPS).
✓ AES encryption at rest (Supabase managed).
✓ Crypto-erase pattern Phase 1.5 (NĐ13/2023 right-to-forget).
✗ No PII in logs.
✗ No audio cloud upload.

Code:
✓ Pre-commit secret scan (gitleaks/truffleHog).
✓ Dependency scan (pip-audit, safety) in CI.
✓ Branch protection on main (require PR review).
✓ Force-push disabled on main.

Runtime:
✓ Non-root container user.
✓ Read-only filesystem where possible.
✓ Resource limits (cpu, mem) in docker compose.
✓ Rate limit at Caddy layer (per-IP).
```

## 10. Local dev vs production

```
                          DEV (Mac Mini)              PRODUCTION (VPS)
                          ────────────                ─────────────
Database                  Local Postgres in Docker    Supabase Cloud
                          OR Supabase dev project

RabbitMQ                  Docker localhost            Docker VPS

AI cloud (Anthropic)      Real API (low budget)       Real API (production budget)

AI local                  Real (Mac Mini same box)    Via Tailscale VPN to Mac Mini
                                                      Fallback: Haiku API

PhoWhisper                Real (Mac Mini)             Via Tailscale OR Haiku fallback

Zalo OA                   Sandbox token (test BN)     Production token (real BN)

Pancake                   Sandbox / test page         Real clinic page

KiotViet                  Skip                         Real (read-only Phase 1)

Migrations                Apply local + Supabase dev   Quang manual apply Supabase prod

Logs                      Console (DEBUG)              JSON → log shipping (INFO+)

Tests                     Full pytest                  Only smoke test in deploy
```

## 11. CLAUDE files placement

```
clinicai/                          # repo root
├── CLAUDE.md                      # ROOT instruction; Claude Code reads first
├── context/
│   ├── PROJECT_BRIEF.md
│   ├── CONSTRAINTS.md
│   ├── DECISIONS.md
│   └── ... (8 files)
├── final_canon/                    # THIS folder, all 12 files
├── .ai/
│   ├── TASK_TEMPLATE.md
│   ├── REPORT_TEMPLATE.md
│   ├── REVIEW_CHECKLIST.md
│   ├── tasks/T-YYYYMMDD-NN.md
│   ├── reports/T-YYYYMMDD-NN.md
│   ├── change_requests/CR-YYYYMMDD-NN.md
│   └── worklog/YYYYMMDD.md
├── wiki/agent-policy/prompts/      # prompts AFTER Phase 10 (KB-loaded)
└── src/clinicai/graphs/<name>/prompts/  # prompts BEFORE Phase 10 (inline)
```

**Claude Code startup sequence:**
1. Read `CLAUDE.md` (root).
2. CLAUDE.md tells it: read `context/PROJECT_BRIEF.md`, `context/CONSTRAINTS.md`, `final_canon/06_HARD_DECISIONS_AND_STYLE.md`.
3. Then read assigned task file.

## 12. First implementation slice (after canon approve)

**Goal:** Phase 0 + Phase 1 + early Phase 2.

```
WEEK 1
- T-20260603-01  Create GitHub repo + init structure (Claude Code, 4h)
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

End of Week 3: Demo-able vertical slice.
  - Mock Zalo event → Pancake adapter → RabbitMQ → Golden Record → Patient row →
    Dashboard reflects new patient.
```

**Stop condition:** Sau slice này, review với Quang. Adjust Phase 2 plan.

---

*08_END_TO_END_SYSTEM_DESIGN.md · 2026-05-20 · Repo structure + deploy flow + Docker + security + first slice.*
