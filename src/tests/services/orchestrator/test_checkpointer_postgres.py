"""Integration test Postgres checkpointer. Skip nếu DSN không set."""

import os
from uuid import UUID, uuid4

import pytest

from clinicai.orchestrator.checkpointer import make_checkpointer
from clinicai.orchestrator.service import OrchestratorService

CLINIC_ID = UUID("a0000000-0000-4000-8000-000000000001")


@pytest.mark.asyncio
@pytest.mark.skipif(
    not (os.getenv("CHECKPOINT_DSN") or os.getenv("DATABASE_URL")),
    reason="CHECKPOINT_DSN/DATABASE_URL not set",
)
async def test_postgres_checkpointer_persistence() -> None:
    """Cùng thread_id → state persist qua 2 lần invoke khác nhau."""
    thread_id = f"test-thread-{uuid4()}"

    async with make_checkpointer(backend="postgres") as cp:
        svc = OrchestratorService(checkpointer=cp)
        r1 = await svc.chat(
            user_message="đặt lịch", clinic_id=CLINIC_ID, thread_id=thread_id
        )
        assert r1["error"] is None
        assert r1["route"] == "scheduling"

        r2 = await svc.chat(
            user_message="khác đi", clinic_id=CLINIC_ID, thread_id=thread_id
        )
        assert r2["error"] is None
        assert r2["route"] == "general"
