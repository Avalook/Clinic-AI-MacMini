# ClinicAI — Dr4women
AI-powered clinic management cho phòng khám sản Dr4women.

## Stack
FastAPI · Supabase Cloud · LangGraph 1.0 · RabbitMQ · Anthropic Claude · Qwen3-14B local

## Quick Start
1. Prerequisites: Python 3.12+, Docker Desktop, Poetry 2.4+
2. git clone https://github.com/nguyencongtuyenlp/Clinic-AI-Dr4Women.git
3. cd Clinic-AI-Dr4Women
4. cp .env.example .env  # điền credentials
5. docker-compose up -d
6. poetry install
7. poetry run uvicorn clinicai.main:app --reload
8. curl http://localhost:8000/health → {"status":"ok"}

## Environment Variables
| Variable | Required | Description |
|---|---|---|
| SUPABASE_URL | ✅ | Supabase project URL |
| SUPABASE_ANON_KEY | ✅ | Supabase anon key |
| DATABASE_URL | ✅ | PostgreSQL connection string |
| ANTHROPIC_API_KEY | ✅ | Anthropic API key |
| RABBITMQ_URL | ✅ | RabbitMQ connection (default: localhost) |
| APP_ENV | ✅ | development / staging / production |
| LOG_LEVEL | - | DEBUG (default) |

## Development
```bash
poetry run pytest src/tests/ -v      # run tests
poetry run ruff check src/           # lint
poetry run ruff format src/          # format
docker-compose up -d                 # start RabbitMQ
```

## Architecture
6 LangGraph sub-graphs: Orchestrator · Scheduling · Lab Triage ·
Task Manager · Communication · Pre-visit Brief.
Safety gates hard-coded: GROUP_C lab, FINALIZED visit — AI suggests, human decides.

## Security
- KHÔNG commit .env
- Audio không rời clinic (PhoWhisper on-premise)
- national_id_number encrypted at rest
