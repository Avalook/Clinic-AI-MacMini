"""Unit tests for the kb.read_policy tool."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import asyncpg
import pytest
from structlog.testing import capture_logs

from clinicai.tools._common.context import new_trace
from clinicai.tools.kb.read_policy import (
    PolicyOutput,
    ReadPolicyInput,
    read_policy,
)


@pytest.fixture
def mock_pool() -> tuple[MagicMock, AsyncMock]:
    """Mocked asyncpg Pool + Connection."""
    pool = MagicMock()
    conn = AsyncMock()
    acquire_ctx = AsyncMock()
    acquire_ctx.__aenter__.return_value = conn
    pool.acquire.return_value = acquire_ctx
    return pool, conn


@pytest.mark.asyncio
async def test_read_policy_table_missing_returns_none(
    mock_pool: tuple[MagicMock, AsyncMock],
) -> None:
    """kb_policy_rule table absent → graceful return, no crash."""
    pool, conn = mock_pool
    conn.fetchrow.side_effect = asyncpg.UndefinedTableError(
        "relation kb_policy_rule does not exist"
    )

    inp = ReadPolicyInput(policy_key="LAB_REVIEW.sla.warn", ctx=new_trace())
    out = await read_policy(inp, pool)

    assert isinstance(out, PolicyOutput)
    assert out.rule_data is None
    assert out.version is None
    assert out.policy_key == "LAB_REVIEW.sla.warn"
    assert out.trace_id == inp.ctx.trace_id


@pytest.mark.asyncio
async def test_read_policy_happy_path(
    mock_pool: tuple[MagicMock, AsyncMock],
) -> None:
    """Row found → PolicyOutput carries rule_data + version."""
    pool, conn = mock_pool
    conn.fetchrow.return_value = {
        "rule_data": {"sla_minutes": 30, "severity": "WARN"},
        "version": 3,
    }

    inp = ReadPolicyInput(policy_key="LAB_REVIEW.sla.warn", ctx=new_trace())
    out = await read_policy(inp, pool)

    assert out.rule_data == {"sla_minutes": 30, "severity": "WARN"}
    assert out.version == 3


@pytest.mark.asyncio
async def test_read_policy_logs_trace_id(
    mock_pool: tuple[MagicMock, AsyncMock],
) -> None:
    """trace_id must appear in structlog entries."""
    pool, conn = mock_pool
    conn.fetchrow.return_value = None

    inp = ReadPolicyInput(policy_key="ANY", ctx=new_trace())

    with capture_logs() as logs:
        await read_policy(inp, pool)

    assert any(log.get("trace_id") == str(inp.ctx.trace_id) for log in logs)
