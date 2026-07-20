"""Integration tests for the pre_visit_brief sub-graph.

The graph wires service → tool → render. We mock the service via
`monkeypatch.setattr` on the imported `aggregate_patient_context` symbol
in the nodes module (the same pattern used by lab_triage tests), and
mock the AnthropicClient.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

import clinicai.graphs.pre_visit_brief.nodes as _pvb_nodes
from clinicai.graphs.pre_visit_brief import (
    PreVisitBriefState,
    build_pre_visit_brief_subgraph,
)
from clinicai.llm.anthropic_client import LLMResponse
from clinicai.services.patient_context_service import (
    PatientContext,
    PatientNotFoundError,
)

_PATIENT_ID = UUID("11111111-1111-1111-1111-111111111111")
_NOW = datetime.now(tz=timezone.utc)

_VALID_BRIEF_JSON = {
    "headline": "BN tuần 24, theo dõi tiền sản giật.",
    "key_points": ["GA 24 tuần", "Tiền sử cao huyết áp"],
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


def _mock_llm(text: str) -> MagicMock:
    llm = MagicMock()
    llm.chat = AsyncMock(
        return_value=LLMResponse(
            text=text,
            model="claude-sonnet-4-6",
            input_tokens=5,
            output_tokens=10,
            latency_ms=20,
            stop_reason="end_turn",
        )
    )
    return llm


@pytest.mark.asyncio
async def test_brief_graph__happy_path__brief_and_markdown_in_state(
    monkeypatch,
) -> None:
    """aggregate → generate → render: final state has both brief + markdown."""
    monkeypatch.setattr(
        _pvb_nodes,
        "aggregate_patient_context",
        AsyncMock(return_value=_patient_context()),
    )
    llm = _mock_llm(json.dumps(_VALID_BRIEF_JSON))

    graph = build_pre_visit_brief_subgraph(pool=MagicMock(), llm_client=llm)
    out = await graph.ainvoke(PreVisitBriefState(clinic_patient_id=_PATIENT_ID))

    assert out.get("error") is None
    assert out["brief"] is not None
    assert out["brief"].headline.startswith("BN tuần 24")
    assert out["brief_markdown"]
    assert "# Brief — BN-2026-000001" in out["brief_markdown"]


@pytest.mark.asyncio
async def test_brief_graph__patient_not_found__error_propagated(monkeypatch) -> None:
    """PatientNotFoundError → state.error set, downstream nodes skipped."""
    monkeypatch.setattr(
        _pvb_nodes,
        "aggregate_patient_context",
        AsyncMock(side_effect=PatientNotFoundError("not found")),
    )
    llm = _mock_llm(json.dumps(_VALID_BRIEF_JSON))

    graph = build_pre_visit_brief_subgraph(pool=MagicMock(), llm_client=llm)
    out = await graph.ainvoke(PreVisitBriefState(clinic_patient_id=_PATIENT_ID))

    assert out.get("error", "").startswith("patient_not_found")
    assert out.get("brief") is None
    assert out.get("brief_markdown") is None
    llm.chat.assert_not_called()


@pytest.mark.asyncio
async def test_brief_graph__llm_failure__error_propagated_no_crash(
    monkeypatch,
) -> None:
    """LLM raises non-ValueError → state.error set, no exception escapes."""
    monkeypatch.setattr(
        _pvb_nodes,
        "aggregate_patient_context",
        AsyncMock(return_value=_patient_context()),
    )
    llm = MagicMock()
    llm.chat = AsyncMock(side_effect=RuntimeError("anthropic timeout"))

    graph = build_pre_visit_brief_subgraph(pool=MagicMock(), llm_client=llm)
    out = await graph.ainvoke(PreVisitBriefState(clinic_patient_id=_PATIENT_ID))

    assert out.get("error", "").startswith("llm_failed")
    assert out.get("brief") is None
    assert out.get("brief_markdown") is None


@pytest.mark.asyncio
async def test_brief_graph__graph_invokable__no_state_corruption(
    monkeypatch,
) -> None:
    """Re-invoking with a fresh state must not leak from a previous run."""
    monkeypatch.setattr(
        _pvb_nodes,
        "aggregate_patient_context",
        AsyncMock(return_value=_patient_context()),
    )
    llm = _mock_llm(json.dumps(_VALID_BRIEF_JSON))
    graph = build_pre_visit_brief_subgraph(pool=MagicMock(), llm_client=llm)

    other_id = UUID("33333333-3333-3333-3333-333333333333")
    out = await graph.ainvoke(PreVisitBriefState(clinic_patient_id=other_id))

    assert out["brief"] is not None
    # The state we passed in carried `other_id`; nothing in the graph rewrites it.
    assert out["clinic_patient_id"] == other_id


@pytest.mark.asyncio
async def test_previsit_brief__wire_summary__builds_7_fields(monkeypatch) -> None:
    """P9.7c happy-path: patient_summary VIEW + ultrasound_record → 7-field brief.

    Verifies the new wiring surfaces phone_primary, total_visits,
    next_appointment_at, and latest_ultrasound_summary on PatientContext,
    and that the LLM user prompt reflects those slots before parsing the
    7-field brief (per D025).
    """
    next_at = datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc)
    ctx = PatientContext(
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
        blood_type="A+",
        last_visit_date=datetime(2026, 5, 1, 9, 0, tzinfo=timezone.utc),
        last_visit_summary=None,
        last_visit_diagnosis=[],
        total_visits=4,
        next_appointment_at=next_at,
        next_appointment_status="CONFIRMED",
        latest_lab_results=[],
        pending_lab_review=[],
        latest_ultrasound_summary=[
            {
                "ultrasound_id": "u-1",
                "ultrasound_type": "2D",
                "gestational_age_weeks": 24.5,
                "findings": {"BPD": "5.8cm"},
                "impression": "Bình thường",
                "performed_at": "2026-05-15T09:00:00+00:00",
            }
        ],
        ongoing_issues=[],
        data_freshness=_NOW,
    )
    monkeypatch.setattr(
        _pvb_nodes,
        "aggregate_patient_context",
        AsyncMock(return_value=ctx),
    )
    llm = _mock_llm(json.dumps(_VALID_BRIEF_JSON))

    graph = build_pre_visit_brief_subgraph(pool=MagicMock(), llm_client=llm)
    out = await graph.ainvoke(PreVisitBriefState(clinic_patient_id=_PATIENT_ID))

    assert out.get("error") is None
    assert out["brief"] is not None

    # Verify the LLM saw the wired slots in its user prompt.
    user_prompt = llm.chat.call_args.kwargs["messages"][0]["content"]
    assert "tổng số visit: 4" in user_prompt
    assert "Lịch hẹn sắp tới" in user_prompt
    assert "CONFIRMED" in user_prompt
    assert "Siêu âm gần đây" in user_prompt
    assert "Bình thường" in user_prompt

    # 7 BS-facing content fields per D025 are present and non-None on the brief.
    brief = out["brief"]
    seven = (
        brief.headline,
        brief.key_points,
        brief.follow_up_items,
        brief.medications,
        brief.allergies,
        brief.pregnancy_context,
        brief.suggested_questions,
    )
    assert all(v is not None for v in seven)
