"""Tests for the task_manager sub-graph.

Uses a programmable mock pool where each invocation of conn.fetchrow /
conn.fetch is queued via side_effect, so a single graph run can satisfy
both `create_task` (INSERT RETURNING) and `check_sla` (SELECT) calls.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from clinicai.graphs.lab_triage.graph import build_lab_triage_subgraph
from clinicai.graphs.lab_triage.state import LabTriageState, LabTriageStep
from clinicai.graphs.task_manager import (
    TaskManagerState,
    build_task_manager_subgraph,
)
from clinicai.tools.task.create_task import CreateTaskInput
from clinicai.tools.task.query_tasks import QueryTasksFilter
from clinicai.tools.task.update_task_status import UpdateTaskStatusInput

_NOW = datetime.now(tz=timezone.utc)


def _task_row(
    *,
    task_id: UUID | None = None,
    status: str = "PENDING",
    due_at: datetime | None = None,
    source_type: str | None = "LAB_RESULT",
    source_id: UUID | None = None,
    completed_at: datetime | None = None,
) -> dict:
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
        "completed_at": completed_at,
        "created_at": _NOW,
        "updated_at": _NOW,
    }


def _build_pool(fetchrow_returns: list, fetch_returns: list | None = None) -> MagicMock:
    """Build an asyncpg-shaped pool that queues fetchrow/fetch returns."""
    pool = MagicMock()
    conn = MagicMock()
    conn.fetchrow = AsyncMock(side_effect=list(fetchrow_returns))
    conn.fetch = AsyncMock(side_effect=list(fetch_returns or []))
    acquire_ctx = AsyncMock()
    acquire_ctx.__aenter__.return_value = conn
    acquire_ctx.__aexit__.return_value = False
    pool.acquire.return_value = acquire_ctx
    return pool


@pytest.mark.asyncio
async def test_task_manager__create_task__task_in_state() -> None:
    """create flow: state.task_input → state.created_task populated."""
    created = _task_row(status="PENDING")
    # fetchrow calls during a create-only flow:
    #   1. INSERT (create_task)
    #   2-N. SELECT-by-id from check_sla, one per queried_task. Here the
    #        query node falls back to filtering by created_task.source_*, so
    #        we also queue:
    #   - conn.fetch for query_tasks (returns the just-created task row)
    #   - conn.fetchrow for check_sla once
    sla_row = {
        "task_id": created["task_id"],
        "status": "PENDING",
        "due_at": None,
    }
    pool = _build_pool(
        fetchrow_returns=[created, sla_row],
        fetch_returns=[[created]],
    )
    graph = build_task_manager_subgraph(pool=pool)

    state = TaskManagerState(
        task_input=CreateTaskInput(
            task_type="LAB_REVIEW",
            priority="URGENT",
            title="t",
            source_type="LAB_RESULT",
            source_id=created["source_id"],
            sla_hours=4,
        ),
    )
    out = await graph.ainvoke(state)

    assert out["created_task"] is not None
    assert out["created_task"].task_type == "LAB_REVIEW"
    assert out["created_task"].priority == "URGENT"


@pytest.mark.asyncio
async def test_task_manager__query_with_sla__sla_results_populated() -> None:
    """query → check_sla path populates sla_results with one entry per task."""
    past = datetime.now(tz=timezone.utc) - timedelta(hours=2)
    t1 = _task_row(status="PENDING", due_at=past)
    t2 = _task_row(status="PENDING", due_at=None)
    pool = _build_pool(
        # check_sla SELECT for each queried task:
        fetchrow_returns=[
            {"task_id": t1["task_id"], "status": "PENDING", "due_at": past},
            {"task_id": t2["task_id"], "status": "PENDING", "due_at": None},
        ],
        fetch_returns=[[t1, t2]],
    )
    graph = build_task_manager_subgraph(pool=pool)

    state = TaskManagerState(
        query_filter=QueryTasksFilter(status="PENDING"),
    )
    out = await graph.ainvoke(state)

    assert len(out["queried_tasks"]) == 2
    assert len(out["sla_results"]) == 2
    overdue = [r for r in out["sla_results"] if r.is_overdue]
    assert len(overdue) == 1  # t1 is overdue, t2 has no due_at


@pytest.mark.asyncio
async def test_task_manager__update_status__updated_task_in_state() -> None:
    """update_input flows through to state.updated_task."""
    task_id = uuid4()
    updated = _task_row(
        task_id=task_id, status="DONE", completed_at=datetime.now(tz=timezone.utc)
    )
    pool = _build_pool(
        # No create, no query. check_sla won't be called because queried_tasks is [].
        # update_task_status UPDATE returns the updated row.
        fetchrow_returns=[updated],
        fetch_returns=[],
    )
    graph = build_task_manager_subgraph(pool=pool)

    state = TaskManagerState(
        update_input=UpdateTaskStatusInput(task_id=task_id, status="DONE"),
    )
    out = await graph.ainvoke(state)

    assert out["updated_task"] is not None
    assert out["updated_task"].status == "DONE"
    assert out["updated_task"].completed_at is not None


@pytest.mark.asyncio
async def test_task_manager__no_input__graceful_empty_flow() -> None:
    """All inputs None → graph runs to END without errors, outputs empty.

    LangGraph's ainvoke result only carries keys nodes explicitly wrote.
    The skip-paths intentionally omit per-output keys, so we use `.get`.
    """
    pool = _build_pool(fetchrow_returns=[], fetch_returns=[])
    graph = build_task_manager_subgraph(pool=pool)

    state = TaskManagerState()
    out = await graph.ainvoke(state)

    assert out.get("created_task") is None
    assert out.get("queried_tasks", []) == []
    assert out.get("sla_results", []) == []
    assert out.get("updated_task") is None
    # turn_count bumped by every node (4 nodes × +1).
    assert out.get("turn_count", 0) == 4


@pytest.mark.asyncio
async def test_task_manager__create_review_tasks__lab_triage_integration(
    monkeypatch,
) -> None:
    """End-to-end: lab_triage GROUP_C → create_review_tasks invokes create_task
    and appends to state.task_ids.

    Verified via the lab_triage sub-graph: we monkeypatch classify_lab_result
    to return GROUP_C, then assert the GROUP_C path enqueues one task.
    """
    import clinicai.graphs.lab_triage.nodes as _lt_nodes
    from clinicai.tools.lab.classify import ClassifyResult

    lab_id = uuid4()
    patient_id = uuid4()
    lab_row_dict = {
        "lab_result_id": lab_id,
        "clinic_patient_id": patient_id,
        "visit_id": None,
        "appointment_id": None,
        "test_code": "HIV",
        "test_name": "HIV antibody",
        "panel_code": "HIV",
        "result_value": "POSITIVE",
        "result_numeric": None,
        "result_unit": None,
        "reference_range_low": None,
        "reference_range_high": None,
        "flag": "POSITIVE",
        "triage_group": "PENDING",
        "triage_reason": None,
        "requires_doctor_review": False,
        "reviewed_by_staff_id": None,
        "reviewed_at": None,
        "is_finalized": False,
        "lab_provider": None,
        "sample_collected_at": None,
        "result_received_at": _NOW,
    }
    created_task_row = _task_row(source_type="LAB_RESULT", source_id=lab_id)

    pool = _build_pool(
        # 1. lab_triage fetch_node SELECT (lab_result row)
        # 2. create_review_tasks INSERT (task row)
        fetchrow_returns=[lab_row_dict, created_task_row],
    )

    monkeypatch.setattr(
        _lt_nodes,
        "classify_lab_result",
        AsyncMock(
            return_value=ClassifyResult(
                triage_group="GROUP_C",
                requires_doctor_review=True,
                reason="HIV reactive",
                matched_rule_key="HIV_REACTIVE",
                source="RULE",
                confidence=1.0,
            )
        ),
    )

    graph = build_lab_triage_subgraph(pool=pool, llm_client=MagicMock())
    state = LabTriageState(lab_result_id=lab_id, clinic_patient_id=patient_id)
    result = await graph.ainvoke(state)

    assert result["step"] == LabTriageStep.DONE
    assert result["triage_group"] == "GROUP_C"
    assert result["requires_doctor_review"] is True
    assert result.get("escalation_note") is not None
    # The key assertion: create_review_tasks ran and appended a task id.
    assert len(result["task_ids"]) == 1
    assert result["task_ids"][0] == created_task_row["task_id"]
