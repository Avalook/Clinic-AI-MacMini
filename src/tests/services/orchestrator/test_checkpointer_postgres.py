"""Integration test Postgres checkpointer. Skip nếu DSN không set."""

import os
from uuid import uuid4

import pytest

from clinicai.orchestrator.checkpointer import make_checkpointer
from clinicai.orchestrator.service import OrchestratorService


@pytest.mark.asyncio
@pytest.mark.skipif(
    not (os.getenv("CHECKPOINT_DSN") or os.getenv("DATABASE_URL")),
    reason="CHECKPOINT_DSN/DATABASE_URL not set",
)
async def test_postgres_checkpointer_persistence():
    """Cùng thread_id → state persist qua 2 lần invoke khác nhau."""
    thread_id = f"test-thread-{uuid4()}"

    async with make_checkpointer(backend="postgres") as cp:
        svc = OrchestratorService(checkpointer=cp)
        r1 = await svc.chat(user_message="đặt lịch", thread_id=thread_id)
        assert r1["error"] is None
        assert r1["route"] == "scheduling"

        r2 = await svc.chat(user_message="khác đi", thread_id=thread_id)
        assert r2["error"] is None
        assert r2["route"] == "general"
