"""Tests for lab_triage sub-graph (T-P9.2-04 real wire).

The skeleton tests from T-P9.2-01 are kept here in adapted form so we still
verify the build/compile path and the receive validation. New tests cover
the real fetch+classify wire and the GROUP_C safety-gate routing.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

import clinicai.graphs.lab_triage.nodes as _lt_nodes
from clinicai.graphs.lab_triage.graph import build_lab_triage_subgraph
from clinicai.graphs.lab_triage.nodes import make_hard_block_node
from clinicai.graphs.lab_triage.state import LabTriageState, LabTriageStep
from clinicai.tools.lab.classify import ClassifyResult
from clinicai.tools.lab.query_lab_result import LabResultRow

_NOW = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)


def _lab_row(**overrides) -> LabResultRow:
    defaults = {
        "lab_result_id": uuid4(),
        "clinic_patient_id": uuid4(),
        "visit_id": None,
        "appointment_id": None,
        "test_code": "TEST",
        "test_name": "Generic test",
        "panel_code": None,
        "result_value": None,
        "result_numeric": None,
        "result_unit": None,
        "reference_range_low": None,
        "reference_range_high": None,
        "flag": None,
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
    defaults.update(overrides)
    return LabResultRow(**defaults)


def _mock_pool_returning_row(row: LabResultRow | None) -> MagicMock:
    """Build an asyncpg-shaped MagicMock pool whose fetchrow returns row dict."""
    pool = MagicMock()
    conn = MagicMock()
    conn.fetchrow = AsyncMock(
        return_value=row.model_dump(mode="python") if row is not None else None
    )
    acquire_ctx = AsyncMock()
    acquire_ctx.__aenter__.return_value = conn
    pool.acquire.return_value = acquire_ctx
    return pool


@pytest.fixture
def mock_pool() -> MagicMock:
    return _mock_pool_returning_row(_lab_row())


@pytest.fixture
def mock_llm() -> MagicMock:
    """Mock AnthropicClient — never used because classify is monkeypatched."""
    return MagicMock()


@pytest.fixture
def graph(mock_pool, mock_llm):
    return build_lab_triage_subgraph(pool=mock_pool, llm_client=mock_llm)


# ──────────────────────── Build + receive validation ────────────────────────


def test_graph_builds_without_error(mock_pool, mock_llm) -> None:
    g = build_lab_triage_subgraph(pool=mock_pool, llm_client=mock_llm)
    assert g is not None


def test_graph_builds_with_no_args() -> None:
    """Both pool and llm_client default to None — graph still compiles."""
    g = build_lab_triage_subgraph()
    assert g is not None


@pytest.mark.asyncio
async def test_missing_lab_result_id_returns_error(graph) -> None:
    state = LabTriageState()
    result = await graph.ainvoke(state)
    assert result["step"] == LabTriageStep.DONE
    assert result["error"] is not None


@pytest.mark.asyncio
async def test_hard_block_node_directly(mock_pool) -> None:
    node = make_hard_block_node(mock_pool)
    state = LabTriageState(
        lab_result_id=uuid4(),
        triage_group="GROUP_C",
        step=LabTriageStep.HARD_BLOCK,
    )
    result = await node(state)
    assert result.response_to_patient is None
    assert result.escalation_note is not None
    assert result.requires_doctor_review is True
    # P9.3: hard_block leaves step=HARD_BLOCK so create_review_tasks runs next.
    # The final DONE transition happens inside create_review_tasks_node.
    assert result.step == LabTriageStep.HARD_BLOCK


# ──────────────────────── Real fetch + classify wire ────────────────────────


@pytest.mark.asyncio
async def test_lab_triage__group_a_routes_to_advise(monkeypatch, mock_llm) -> None:
    """GROUP_A from classify → advise → patient response set, step=DONE."""
    row = _lab_row(
        test_name="CBC",
        panel_code="CBC",
        flag="N",
        result_numeric=Decimal("5.0"),
        reference_range_low=Decimal("4.0"),
        reference_range_high=Decimal("6.0"),
    )
    pool = _mock_pool_returning_row(row)

    monkeypatch.setattr(
        _lt_nodes,
        "classify_lab_result",
        AsyncMock(
            return_value=ClassifyResult(
                triage_group="GROUP_A",
                requires_doctor_review=False,
                reason="Kết quả bình thường",
                matched_rule_key="FLAG_NORMAL",
                source="RULE",
                confidence=1.0,
            )
        ),
    )

    g = build_lab_triage_subgraph(pool=pool, llm_client=mock_llm)
    state = LabTriageState(
        lab_result_id=row.lab_result_id,
        clinic_patient_id=row.clinic_patient_id,
    )
    result = await g.ainvoke(state)

    assert result["step"] == LabTriageStep.DONE
    assert result["triage_group"] == "GROUP_A"
    assert result["response_to_patient"] is not None
    assert result.get("escalation_note") is None
    assert result["requires_doctor_review"] is False


@pytest.mark.asyncio
async def test_lab_triage__group_c_unreviewed__safety_gate_populated(
    monkeypatch, mock_llm
) -> None:
    """GROUP_C → hard_block: no patient response, escalation_note set,
    requires_doctor_review=True. This is the medical safety gate path.
    """
    row = _lab_row(test_name="HIV antibody", panel_code="HIV", flag="POSITIVE")
    pool = _mock_pool_returning_row(row)

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

    g = build_lab_triage_subgraph(pool=pool, llm_client=mock_llm)
    state = LabTriageState(
        lab_result_id=row.lab_result_id,
        clinic_patient_id=row.clinic_patient_id,
    )
    result = await g.ainvoke(state)

    assert result["step"] == LabTriageStep.DONE
    assert result["triage_group"] == "GROUP_C"
    assert result.get("response_to_patient") is None  # HARD BLOCK
    assert result.get("escalation_note") is not None
    assert result["requires_doctor_review"] is True


@pytest.mark.asyncio
async def test_lab_triage__row_not_found__terminates_with_error(mock_llm) -> None:
    """fetchrow returns None → graph ends, error set, no classify call."""
    pool = _mock_pool_returning_row(None)
    g = build_lab_triage_subgraph(pool=pool, llm_client=mock_llm)
    state = LabTriageState(
        lab_result_id=uuid4(),
        clinic_patient_id=uuid4(),
    )
    result = await g.ainvoke(state)

    assert result["step"] == LabTriageStep.DONE
    assert result["error"] is not None
    assert result.get("triage_group") is None


@pytest.mark.asyncio
async def test_lab_triage__no_llm_client__safety_falls_back_to_hard_block() -> None:
    """No llm_client wired → classify_node escalates to hard_block (safety bias)."""
    row = _lab_row(test_name="Unknown panel", panel_code="UNKNOWN")
    pool = _mock_pool_returning_row(row)

    g = build_lab_triage_subgraph(pool=pool, llm_client=None)
    state = LabTriageState(
        lab_result_id=row.lab_result_id,
        clinic_patient_id=row.clinic_patient_id,
    )
    result = await g.ainvoke(state)

    assert result["step"] == LabTriageStep.DONE
    assert result["triage_group"] == "PENDING"
    assert result["requires_doctor_review"] is True
    assert result.get("escalation_note") is not None
    assert result.get("response_to_patient") is None


@pytest.mark.asyncio
async def test_lab_triage__classify_exception__safety_falls_back(
    monkeypatch, mock_llm
) -> None:
    """classify_lab_result raises → safety bias to hard_block."""
    row = _lab_row(test_name="Unknown panel", panel_code="UNKNOWN")
    pool = _mock_pool_returning_row(row)

    monkeypatch.setattr(
        _lt_nodes,
        "classify_lab_result",
        AsyncMock(side_effect=RuntimeError("LLM down")),
    )

    g = build_lab_triage_subgraph(pool=pool, llm_client=mock_llm)
    state = LabTriageState(
        lab_result_id=row.lab_result_id,
        clinic_patient_id=row.clinic_patient_id,
    )
    result = await g.ainvoke(state)

    assert result["step"] == LabTriageStep.DONE
    assert result["triage_group"] == "PENDING"
    assert result["requires_doctor_review"] is True
    assert result.get("escalation_note") is not None
