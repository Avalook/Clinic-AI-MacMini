"""Unit tests for tools.task.create_task."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from clinicai.tools._common.context import new_trace
from clinicai.tools.task.create_task import (
    CreateTaskInput,
    TaskRow,
    create_task,
)


def _row(
    *,
    task_id: UUID | None = None,
    location_id: UUID | None = None,
    task_type: str = "LAB_REVIEW",
    priority: str = "URGENT",
    status: str = "PENDING",
    assigned_to: UUID | None = None,
    source_type: str | None = "LAB_RESULT",
    source_id: UUID | None = None,
    title: str = "Review CBC — GROUP_C",
    description: str | None = None,
    due_at: datetime | None = None,
    sla_hours: int = 4,
    completed_at: datetime | None = None,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
) -> dict:
    now = datetime.now(tz=timezone.utc)
    return {
        "task_id": task_id or uuid4(),
        "location_id": location_id,
        "task_type": task_type,
        "priority": priority,
        "status": status,
        "assigned_to": assigned_to,
        "source_type": source_type,
        "source_id": source_id or uuid4(),
        "title": title,
        "description": description,
        "due_at": due_at,
        "sla_hours": sla_hours,
        "completed_at": completed_at,
        "created_at": created_at or now,
        "updated_at": updated_at or now,
    }


@pytest.mark.asyncio
async def test_create_task__valid_input__returns_task_row(
    mock_pool_conn: tuple[MagicMock, AsyncMock],
) -> None:
    pool, conn = mock_pool_conn
    expected = _row()
    conn.fetchrow = AsyncMock(return_value=expected)

    inp = CreateTaskInput(
        task_type="LAB_REVIEW",
        priority="URGENT",
        title="Review CBC — GROUP_C",
        sla_hours=4,
    )
    out = await create_task(pool, inp, new_trace())

    assert isinstance(out, TaskRow)
    assert out.task_type == "LAB_REVIEW"
    assert out.priority == "URGENT"
    assert out.sla_hours == 4


@pytest.mark.asyncio
async def test_create_task__lab_review_type__source_fields_populated(
    mock_pool_conn: tuple[MagicMock, AsyncMock],
) -> None:
    pool, conn = mock_pool_conn
    source_id = uuid4()
    expected = _row(source_type="LAB_RESULT", source_id=source_id)
    conn.fetchrow = AsyncMock(return_value=expected)

    inp = CreateTaskInput(
        task_type="LAB_REVIEW",
        priority="URGENT",
        source_type="LAB_RESULT",
        source_id=source_id,
        title="Review",
        sla_hours=4,
    )
    out = await create_task(pool, inp, new_trace())

    # Verify the INSERT received the source fields as params.
    args = conn.fetchrow.call_args.args
    # signature: (sql, location_id, task_type, priority, assigned_to,
    #             source_type, source_id, title, description, due_at, sla_hours)
    assert args[5] == "LAB_RESULT"
    assert args[6] == source_id
    assert out.source_type == "LAB_RESULT"
    assert out.source_id == source_id


def test_create_task__missing_title__pydantic_error() -> None:
    """`title` is required — Pydantic rejects construction without it."""
    with pytest.raises(ValidationError):
        CreateTaskInput(  # type: ignore[call-arg]
            task_type="LAB_REVIEW",
        )


@pytest.mark.asyncio
async def test_create_task__due_at_in_past__still_creates(
    mock_pool_conn: tuple[MagicMock, AsyncMock],
) -> None:
    """Tool layer does NOT validate due_at — that's a business-rule concern."""
    pool, conn = mock_pool_conn
    past = datetime.now(tz=timezone.utc) - timedelta(days=2)
    expected = _row(due_at=past)
    conn.fetchrow = AsyncMock(return_value=expected)

    inp = CreateTaskInput(
        task_type="PATIENT_CALLBACK",
        title="Callback overdue",
        due_at=past,
    )
    out = await create_task(pool, inp, new_trace())

    assert out.due_at == past


@pytest.mark.asyncio
async def test_create_task__assigned_to_none__ok(
    mock_pool_conn: tuple[MagicMock, AsyncMock],
) -> None:
    """Unassigned tasks are valid and end up with assigned_to=NULL."""
    pool, conn = mock_pool_conn
    expected = _row(assigned_to=None)
    conn.fetchrow = AsyncMock(return_value=expected)

    inp = CreateTaskInput(
        task_type="LAB_REVIEW",
        title="Unassigned review",
    )
    out = await create_task(pool, inp, new_trace())

    assert out.assigned_to is None
    args = conn.fetchrow.call_args.args
    assert args[4] is None  # assigned_to param


@pytest.mark.asyncio
async def test_create_task__returns_all_fields_populated(
    mock_pool_conn: tuple[MagicMock, AsyncMock],
) -> None:
    """Returned TaskRow must surface all DB-populated defaults."""
    pool, conn = mock_pool_conn
    expected = _row()
    conn.fetchrow = AsyncMock(return_value=expected)

    inp = CreateTaskInput(
        task_type="LAB_REVIEW",
        title="t",
    )
    out = await create_task(pool, inp, new_trace())

    assert isinstance(out.task_id, UUID)
    assert out.status == "PENDING"
    assert out.created_at is not None
    assert out.updated_at is not None
