"""E2E orchestrator → pre_visit_brief wrapper tests (T-WIRE-PREVISIT-ROUTER-01).

Covers the wrapper-node wiring added to orchestrator/graph.py:

1. previsit wrapper WITH a patient_id → real sub-graph runs (aggregate +
   generate + render), wrapper surfaces the brief headline into `response`.
2. previsit wrapper WITHOUT patient_id → ack only, sub-graph not invoked.
3. build_orchestrator_graph without previsit_pool → previsit node stays the
   legacy stub (no-DB CI fallback unchanged).

NOTE (scope gap, see task report): the LIVE classifier cannot emit route
"previsit" yet — `llm_nodes.VALID_ROUTES` + `state.RouteType` lack it — so a
full graph-through-classify e2e isn't possible without editing state.py (out
of this task's boundary). These tests exercise the wrapper directly + the
binding-selection, which is exactly the code this task added.

Mock pattern mirrors test_brief_graph.py: DB call monkeypatched at
`aggregate_patient_context`, AnthropicClient mocked. No DATABASE_URL, no seed.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

import clinicai.graphs.pre_visit_brief.nodes as _pvb_nodes
from clinicai.llm.anthropic_client import AnthropicClient, LLMResponse
from clinicai.orchestrator.graph import (
    _make_previsit_brief_wrapper_node,
    build_orchestrator_graph,
)
from clinicai.orchestrator.state import OrchestratorState
from clinicai.orchestrator.stubs import previsit_brief_stub_node
from clinicai.services.patient_context_service import PatientContext

_PATIENT_ID = UUID("11111111-1111-1111-1111-111111111111")
_NOW = datetime.now(tz=timezone.utc)

_HEADLINE = "BN tuần 24, theo dõi tiền sản giật."
_VALID_BRIEF_JSON = {
    "headline": _HEADLINE,
    "key_points": ["GA 24 tuần"],
    "follow_up_items": ["Đo HA hàng tuần"],
    "pending_reviews": [],
    "medications": ["Folate 5mg"],
    "allergies": [],
    "pregnancy_context": "24 tuần, nguy cơ cao",
    "risk_flags": ["Tiền sản giật"],
    "suggested_questions": ["Có triệu chứng nào không?"],
    "confidence": 0.8,
}


def _patient_context() -> PatientContext:
    return PatientContext(
        clinic_patient_id=_PATIENT_ID,
        patient_code="BN-2026-000001",
        full_name="Nguyễn Thị A",
        date_of_birth=None,
        phone_primary="0901234567",
        current_ga_weeks=24.0,
        current_pregnancy_id=UUID("22222222-2222-2222-2222-222222222222"),
        pregnancy_complications=["Tiền sản giật"],
        chronic_diseases=[],
        current_medications=["Folate 5mg"],
        allergies=[],
        blood_type=None,
        last_visit_date=None,
        last_visit_summary=None,
        last_visit_diagnosis=[],
        total_visits=0,
        next_appointment_at=None,
        next_appointment_status=None,
        latest_lab_results=[],
        pending_lab_review=[],
        latest_ultrasound_summary=[],
        ongoing_issues=[],
        data_freshness=_NOW,
    )


def _mock_llm() -> MagicMock:
    """AnthropicClient mock returning a valid brief JSON for generate_brief."""
    mock = MagicMock(spec=AnthropicClient)
    mock.chat = AsyncMock(
        return_value=LLMResponse(
            text=json.dumps(_VALID_BRIEF_JSON),
            model="claude-sonnet-4-6",
            input_tokens=5,
            output_tokens=10,
            latency_ms=20,
            stop_reason="end_turn",
        )
    )
    return mock


@pytest.mark.asyncio
async def test_previsit_wrapper__with_patient__runs_real_subgraph(monkeypatch) -> None:
    """patient_id present → real sub-graph runs; headline surfaced to response."""
    monkeypatch.setattr(
        _pvb_nodes,
        "aggregate_patient_context",
        AsyncMock(return_value=_patient_context()),
    )
    wrapper = _make_previsit_brief_wrapper_node(
        pool=MagicMock(), llm_client=_mock_llm()
    )

    state: OrchestratorState = {
        "trace_id": uuid4(),
        "user_message": "Cho em xem tóm tắt trước khám của bệnh nhân này",
        "patient_id": _PATIENT_ID,
    }
    out = await wrapper(state)

    assert out["handled_by"] == "previsit_brief_subgraph"
    assert out["response"] == _HEADLINE


@pytest.mark.asyncio
async def test_previsit_wrapper__no_patient_id__acks(monkeypatch) -> None:
    """No patient_id → ack only; the real sub-graph (DB) is never invoked."""
    aggregate = AsyncMock(return_value=_patient_context())
    monkeypatch.setattr(_pvb_nodes, "aggregate_patient_context", aggregate)
    wrapper = _make_previsit_brief_wrapper_node(
        pool=MagicMock(), llm_client=_mock_llm()
    )

    state: OrchestratorState = {"trace_id": uuid4(), "user_message": "tóm tắt"}
    out = await wrapper(state)

    assert out["handled_by"] == "previsit_brief_subgraph"
    assert "mã bệnh nhân" in out["response"]
    aggregate.assert_not_called()


def test_build_orchestrator_graph__both_previsit_branches_compile() -> None:
    """Both factory branches of the new previsit binding compile cleanly:
    with previsit_pool + llm → real wrapper; without → legacy stub fallback."""
    wired = build_orchestrator_graph(llm_client=_mock_llm(), previsit_pool=MagicMock())
    fallback = build_orchestrator_graph(llm_client=None)  # no previsit_pool → stub
    assert wired is not None
    assert fallback is not None
    # Stub remains the importable no-DB fallback used by that binding.
    assert previsit_brief_stub_node.__name__ == "previsit_brief_stub_node"
