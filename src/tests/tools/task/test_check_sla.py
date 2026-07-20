"""Unit tests for tools.task.check_sla."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from clinicai.tools._common.context import new_trace
from clinicai.tools.task.check_sla import check_task_sla


@pytest.mark.asyncio
async def test_check_sla__overdue__is_overdue_true_hours_populated(
    mock_pool_conn: tuple[MagicMock, AsyncMock],
) -> None:
    """due_at 2h in the past + PENDING → is_overdue=True, hours_overdue≈2."""
    pool, conn = mock_pool_conn
    past = datetime.now(tz=timezone.utc) - timedelta(hours=2)
    task_id = uuid4()
    conn.fetchrow = AsyncMock(
        return_value={"task_id": task_id, "status": "PENDING", "due_at": past},
    )

    res = await check_task_sla(pool, task_id, new_trace())

    assert res.is_overdue is True
    assert res.hours_overdue is not None
    assert res.hours_remaining is None
    assert 1.9 < res.hours_overdue < 2.1


@pytest.mark.asyncio
async def test_check_sla__within_sla__is_overdue_false(
    mock_pool_conn: tuple[MagicMock, AsyncMock],
) -> None:
    """due_at 3h in the future + PENDING → is_overdue=False, hours_remaining≈3."""
    pool, conn = mock_pool_conn
    future = datetime.now(tz=timezone.utc) + timedelta(hours=3)
    task_id = uuid4()
    conn.fetchrow = AsyncMock(
        return_value={"task_id": task_id, "status": "PENDING", "due_at": future},
    )

    res = await check_task_sla(pool, task_id, new_trace())

    assert res.is_overdue is False
    assert res.hours_remaining is not None
    assert res.hours_overdue is None
    assert 2.9 < res.hours_remaining < 3.1


@pytest.mark.asyncio
async def test_check_sla__done_task__hours_remaining_none(
    mock_pool_conn: tuple[MagicMock, AsyncMock],
) -> None:
    """DONE is a terminal status → no SLA window to compute."""
    pool, conn = mock_pool_conn
    past = datetime.now(tz=timezone.utc) - timedelta(hours=5)
    task_id = uuid4()
    conn.fetchrow = AsyncMock(
        return_value={"task_id": task_id, "status": "DONE", "due_at": past},
    )

    res = await check_task_sla(pool, task_id, new_trace())

    assert res.is_overdue is False
    assert res.hours_remaining is None
    assert res.hours_overdue is None
    assert res.status == "DONE"


@pytest.mark.asyncio
async def test_check_sla__no_due_at__handled_gracefully(
    mock_pool_conn: tuple[MagicMock, AsyncMock],
) -> None:
    """due_at NULL → no SLA window; treat as not overdue."""
    pool, conn = mock_pool_conn
    task_id = uuid4()
    conn.fetchrow = AsyncMock(
        return_value={"task_id": task_id, "status": "PENDING", "due_at": None},
    )

    res = await check_task_sla(pool, task_id, new_trace())

    assert res.is_overdue is False
    assert res.hours_remaining is None
    assert res.hours_overdue is None
