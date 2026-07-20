"""E2E orchestrator → lab_triage sub-graph integration tests.

Covers the wrapper-node behaviour added in T-P9.2-04:

1. lab route without `lab_result_id` → generic Vietnamese acknowledgement.
2. lab route with `lab_result_id` → real sub-graph runs (fetch + classify).
3. No `lab_triage_pool` wired → falls back to legacy stub.
4. GROUP_C surfaces the safety-gate response from the orchestrator wrapper.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

import clinicai.graphs.lab_triage.nodes as _lt_nodes
from clinicai.llm.anthropic_client import AnthropicClient, LLMResponse
from clinicai.orchestrator.graph import build_orchestrator_graph
from clinicai.orchestrator.state import OrchestratorState
from clinicai.tools.lab.classify import ClassifyResult
from clinicai.tools.lab.query_lab_result import LabResultRow

_NOW = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)


def _mock_llm_route(route: str) -> AnthropicClient:
    fake = LLMResponse(
        text=f'{{"route": "{route}", "confidence": 0.95, "reasoning": "x"}}',
        model="claude-haiku-4-5-20251001",
        input_tokens=10,
        output_tokens=20,
        latency_ms=30,
        stop_reason="end_turn",
    )
    mock = MagicMock(spec=AnthropicClient)
    mock.chat = AsyncMock(return_value=fake)
    return mock


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


def _mock_db_pool(row: LabResultRow | None) -> MagicMock:
    pool = MagicMock()
    conn = MagicMock()
    conn.fetchrow = AsyncMock(
        return_value=row.model_dump(mode="python") if row is not None else None
    )
    acquire_ctx = AsyncMock()
    acquire_ctx.__aenter__.return_value = conn
    pool.acquire.return_value = acquire_ctx
    return pool


@pytest.mark.asyncio
async def test_e2e_lab_triage__no_lab_result_id__ack_response() -> None:
    """Without lab_result_id the wrapper returns the Vietnamese ack."""
    llm = _mock_llm_route("lab")
    graph = build_orchestrator_graph(
        llm_client=llm,
        use_llm_respond=False,
        lab_triage_pool=MagicMock(),
    )

    initial: OrchestratorState = {
        "trace_id": uuid4(),
        "user_message": "kết quả xét nghiệm của tôi ra sao?",
    }
    config = {"configurable": {"thread_id": "e2e-lab-noid"}}
    final = await graph.ainvoke(initial, config=config)

    assert final.get("handled_by") == "lab_triage_subgraph"
    assert "mã kết quả" in final.get("response", "")


@pytest.mark.asyncio
async def test_e2e_lab_triage__group_a_real_subgraph(monkeypatch) -> None:
    """Lab branch with lab_result_id runs the real sub-graph and returns
    the patient-facing advise message for GROUP_A.
    """
    row = _lab_row(panel_code="CBC", flag="N")
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

    llm = _mock_llm_route("lab")
    pool = _mock_db_pool(row)
    graph = build_orchestrator_graph(
        llm_client=llm,
        use_llm_respond=False,
        lab_triage_pool=pool,
    )

    initial: OrchestratorState = {
        "trace_id": uuid4(),
        "user_message": "kết quả xét nghiệm",
        "lab_result_id": row.lab_result_id,
        "patient_id": row.clinic_patient_id,
    }
    config = {"configurable": {"thread_id": "e2e-lab-groupa"}}
    final = await graph.ainvoke(initial, config=config)

    assert final.get("handled_by") == "lab_triage_subgraph"
    assert final.get("triage_group") == "GROUP_A"
    assert "bình thường" in final.get("response", "")
    assert final.get("requires_doctor_review") is False


@pytest.mark.asyncio
async def test_e2e_lab_triage__group_c_safety_gate_visible(monkeypatch) -> None:
    """GROUP_C → wrapper surfaces the safety-gate response."""
    row = _lab_row(panel_code="HIV", flag="POSITIVE")
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

    llm = _mock_llm_route("lab")
    pool = _mock_db_pool(row)
    graph = build_orchestrator_graph(
        llm_client=llm,
        use_llm_respond=False,
        lab_triage_pool=pool,
    )

    initial: OrchestratorState = {
        "trace_id": uuid4(),
        "user_message": "kết quả xét nghiệm HIV",
        "lab_result_id": row.lab_result_id,
        "patient_id": row.clinic_patient_id,
    }
    config = {"configurable": {"thread_id": "e2e-lab-groupc"}}
    final = await graph.ainvoke(initial, config=config)

    assert final.get("triage_group") == "GROUP_C"
    assert final.get("requires_doctor_review") is True
    assert final.get("escalation_note") is not None
    # Wrapper substitutes a safe Vietnamese ack instead of leaking GROUP_C details.
    assert "bác sĩ" in final.get("response", "")


@pytest.mark.asyncio
async def test_e2e_lab_triage__no_pool_falls_back_to_stub() -> None:
    """Without lab_triage_pool the route still resolves via legacy stub."""
    llm = _mock_llm_route("lab")
    graph = build_orchestrator_graph(
        llm_client=llm,
        use_llm_respond=False,
        # lab_triage_pool intentionally omitted
    )

    initial: OrchestratorState = {
        "trace_id": uuid4(),
        "user_message": "kết quả xét nghiệm",
    }
    config = {"configurable": {"thread_id": "e2e-lab-stub"}}
    final = await graph.ainvoke(initial, config=config)

    assert final.get("handled_by") == "lab_triage_stub"
    assert "[STUB-lab_triage]" in final.get("response", "")
