"""Unit tests for tools.task.update_task_status."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from clinicai.tools._common.context import new_trace
from clinicai.tools.task.update_task_status import (
    TaskNotFoundError,
    UpdateTaskStatusInput,
    update_task_status,
)


def _row(
    *,
    task_id: UUID | None = None,
    status: str = "DONE",
    completed_at: datetime | None = None,
) -> dict:
    now = datetime.now(tz=timezone.utc)
    return {
        "task_id": task_id or uuid4(),
        "location_id": None,
        "task_type": "LAB_REVIEW",
        "priority": "URGENT",
        "status": status,
        "assigned_to": None,
        "source_type": "LAB_RESULT",
        "source_id": uuid4(),
        "title": "t",
        "description": None,
        "due_at": None,
        "sla_hours": 4,
        "completed_at": completed_at,
        "created_at": now,
        "updated_at": now,
    }


@pytest.mark.asyncio
async def test_update_status__done__completed_at_auto_set(
    mock_pool_conn: tuple[MagicMock, AsyncMock],
) -> None:
    """DONE with completed_at=None must auto-populate completed_at = now()."""
    pool, conn = mock_pool_conn
    auto_now = datetime.now(tz=timezone.utc)
    conn.fetchrow = AsyncMock(return_value=_row(status="DONE", completed_at=auto_now))

    inp = UpdateTaskStatusInput(task_id=uuid4(), status="DONE")
    out = await update_task_status(pool, inp, new_trace())

    args = conn.fetchrow.call_args.args
    # signature: (sql, task_id, status, completed_at)
    assert args[2] == "DONE"
    assert args[3] is not None  # auto-set
    assert isinstance(args[3], datetime)
    assert out.status == "DONE"


@pytest.mark.asyncio
async def test_update_status__cancelled__ok(
    mock_pool_conn: tuple[MagicMock, AsyncMock],
) -> None:
    """CANCELLED status must NOT set completed_at."""
    pool, conn = mock_pool_conn
    conn.fetchrow = AsyncMock(return_value=_row(status="CANCELLED", completed_at=None))

    inp = UpdateTaskStatusInput(task_id=uuid4(), status="CANCELLED")
    out = await update_task_status(pool, inp, new_trace())

    args = conn.fetchrow.call_args.args
    assert args[2] == "CANCELLED"
    assert args[3] is None  # not DONE → cleared / not set
    assert out.status == "CANCELLED"


def test_update_status__invalid_status__pydantic_error() -> None:
    with pytest.raises(ValidationError):
        UpdateTaskStatusInput(
            task_id=uuid4(),
            status="BOGUS",  # type: ignore[arg-type]
        )


@pytest.mark.asyncio
async def test_update_status__task_not_found__raises_lookup_error(
    mock_pool_conn: tuple[MagicMock, AsyncMock],
) -> None:
    """fetchrow returns None when no row matches → TaskNotFoundError."""
    pool, conn = mock_pool_conn
    conn.fetchrow = AsyncMock(return_value=None)

    inp = UpdateTaskStatusInput(task_id=uuid4(), status="DONE")
    with pytest.raises(TaskNotFoundError):
        await update_task_status(pool, inp, new_trace())
