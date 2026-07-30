import os
from typing import Annotated, Optional, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from clinicai.api.identity import ClinicRole, StaffIdentity, require_role
from clinicai.api.rate_limit import InMemoryRateLimiter
from clinicai.orchestrator.service import OrchestratorService

router = APIRouter(prefix="/orchestrator", tags=["orchestrator"])
_ORCHESTRATOR_GUARD = require_role(ClinicRole.MANAGEMENT)
ORCHESTRATOR_RATE_LIMIT = InMemoryRateLimiter(
    scope="ai-orchestrator",
    limit=20,
    window_seconds=60,
)


def require_orchestrator_enabled() -> None:
    """The unfinished AI workflow is opt-in and disabled in production."""
    if os.environ.get("ENABLE_AI_ORCHESTRATOR", "").strip().lower() != "true":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI orchestrator is disabled",
        )


def scoped_thread_id(clinic_id: str, staff_id: str, thread_id: str) -> str:
    """Namespace a client label so checkpoints cannot cross actor or tenant."""
    return f"{clinic_id}:{staff_id}:{thread_id}"


def get_orchestrator_service(request: Request) -> OrchestratorService:
    svc = getattr(request.app.state, "orchestrator_service", None)
    if svc is None:
        raise RuntimeError("OrchestratorService chưa init trong lifespan")
    return cast(OrchestratorService, svc)


class ChatInput(BaseModel):
    user_message: str = Field(min_length=1, max_length=4000)
    patient_id: Optional[UUID] = None
    trace_id: Optional[UUID] = None
    thread_id: Optional[str] = Field(default=None, min_length=1, max_length=128)


class ChatOutput(BaseModel):
    trace_id: UUID
    route: Optional[str] = None
    response: Optional[str] = None
    error: Optional[str] = None


@router.post("/chat", response_model=ChatOutput)
async def chat(
    input: ChatInput,
    identity: Annotated[StaffIdentity, Depends(_ORCHESTRATOR_GUARD)],
    svc: OrchestratorService = Depends(get_orchestrator_service),
    _enabled: None = Depends(require_orchestrator_enabled),
    _rate_limit: None = Depends(ORCHESTRATOR_RATE_LIMIT),
) -> ChatOutput:
    """Debug endpoint. Phase 9.0 → real LLM dispatch."""
    result = await svc.chat(
        user_message=input.user_message,
        clinic_id=UUID(identity.clinic_id),
        patient_id=input.patient_id,
        trace_id=input.trace_id,
        thread_id=(
            scoped_thread_id(
                identity.clinic_id,
                identity.staff_id,
                input.thread_id,
            )
            if input.thread_id
            else None
        ),
    )
    return ChatOutput(**result)
