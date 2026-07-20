import pytest
from langgraph.checkpoint.memory import MemorySaver

from clinicai.orchestrator.checkpointer import make_checkpointer


@pytest.mark.asyncio
async def test_factory_memory_default(monkeypatch):
    monkeypatch.delenv("CHECKPOINTER_BACKEND", raising=False)
    async with make_checkpointer() as cp:
        assert isinstance(cp, MemorySaver)


@pytest.mark.asyncio
async def test_factory_unknown_backend_raises():
    with pytest.raises(ValueError, match="Unknown CHECKPOINTER_BACKEND"):
        async with make_checkpointer(backend="redis"):
            pass
