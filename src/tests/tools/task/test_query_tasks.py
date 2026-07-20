"""Unit tests for tools.task.query_tasks."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from clinicai.tools._common.context import new_trace
from clinicai.tools.task.query_tasks import QueryTasksFilter, query_tasks


def _row(
    *,
    task_id: UUID | None = None,
    status: str = "PENDING",
    source_type: str | None = "LAB_RESULT",
    source_id: UUID | None = None,
    due_at: datetime | None = None,
) -> dict:
    now = datetime.now(tz=timezone.utc)
    return {
        "task_id": task_id or uuid4(),
        "location_id": None,
        "task_type": "LAB_REVIEW",
        "priority": "URGENT",
        "status": status,
        "assigned_to": None,
        "source_type": source_type,
        "source_id": source_id or uuid4(),
        "title": "t",
        "description": None,
        "due_at": due_at,
        "sla_hours": 4,
        "completed_at": None,
        "created_at": now,
        "updated_at": now,
    }


@pytest.mark.asyncio
async def test_query_tasks__overdue_only__returns_overdue(
    mock_pool_conn: tuple[MagicMock, AsyncMock],
) -> None:
    """overdue_only=True must inject the `due_at < NOW()` clause."""
    pool, conn = mock_pool_conn
    past = datetime.now(tz=timezone.utc) - timedelta(hours=2)
    conn.fetch = AsyncMock(return_value=[_row(due_at=past, status="PENDING")])

    out = await query_tasks(
        pool,
        QueryTasksFilter(overdue_only=True),
        new_trace(),
    )

    assert len(out) == 1
    args = conn.fetch.call_args.args
    sql = args[0]
    assert "due_at < NOW()" in sql
    assert "status = 'PENDING'" in sql


@pytest.mark.asyncio
async def test_query_tasks__filter_by_status__pending_only(
    mock_pool_conn: tuple[MagicMock, AsyncMock],
) -> None:
    pool, conn = mock_pool_conn
    conn.fetch = AsyncMock(return_value=[_row(status="PENDING")])

    out = await query_tasks(
        pool,
        QueryTasksFilter(status="PENDING"),
        new_trace(),
    )

    assert all(r.status == "PENDING" for r in out)
    args = conn.fetch.call_args.args
    sql = args[0]
    assert "status = $" in sql
    assert "PENDING" in args[1:]


@pytest.mark.asyncio
async def test_query_tasks__filter_by_source__lab_result(
    mock_pool_conn: tuple[MagicMock, AsyncMock],
) -> None:
    pool, conn = mock_pool_conn
    src_id = uuid4()
    conn.fetch = AsyncMock(
        return_value=[_row(source_type="LAB_RESULT", source_id=src_id)]
    )

    out = await query_tasks(
        pool,
        QueryTasksFilter(source_type="LAB_RESULT", source_id=src_id),
        new_trace(),
    )

    assert len(out) == 1
    args = conn.fetch.call_args.args
    sql = args[0]
    assert "source_type = $" in sql
    assert "source_id = $" in sql
    assert "LAB_RESULT" in args[1:]
    assert src_id in args[1:]


@pytest.mark.asyncio
async def test_query_tasks__limit_respected(
    mock_pool_conn: tuple[MagicMock, AsyncMock],
) -> None:
    pool, conn = mock_pool_conn
    conn.fetch = AsyncMock(return_value=[])

    await query_tasks(
        pool,
        QueryTasksFilter(limit=7),
        new_trace(),
    )

    args = conn.fetch.call_args.args
    sql = args[0]
    assert "LIMIT $" in sql
    assert 7 in args[1:]


@pytest.mark.asyncio
async def test_query_tasks__empty__returns_list(
    mock_pool_conn: tuple[MagicMock, AsyncMock],
) -> None:
    pool, conn = mock_pool_conn
    conn.fetch = AsyncMock(return_value=[])

    out = await query_tasks(
        pool,
        QueryTasksFilter(),
        new_trace(),
    )

    assert out == []
