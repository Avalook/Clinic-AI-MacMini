"""Shared fixtures for tools.brief tests."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

from clinicai.llm.anthropic_client import LLMResponse
from clinicai.services.patient_context_service import PatientContext


def make_patient_context(**overrides) -> PatientContext:
    """Construct a baseline PatientContext, allowing per-test overrides."""
    defaults: dict = {
        "clinic_patient_id": UUID("11111111-1111-1111-1111-111111111111"),
        "patient_code": "BN-2026-000001",
        "full_name": "Nguyễn Thị A",
        "date_of_birth": None,
        "phone_primary": None,
        "current_ga_weeks": None,
        "current_pregnancy_id": None,
        "pregnancy_complications": [],
        "chronic_diseases": [],
        "current_medications": [],
        "allergies": [],
        "blood_type": None,
        "last_visit_date": None,
        "last_visit_summary": None,
        "last_visit_diagnosis": [],
        "total_visits": 0,
        "next_appointment_at": None,
        "next_appointment_status": None,
        "latest_lab_results": [],
        "pending_lab_review": [],
        "latest_ultrasound_summary": [],
        "ongoing_issues": [],
        "data_freshness": datetime.now(tz=timezone.utc),
    }
    defaults.update(overrides)
    return PatientContext(**defaults)


def make_llm_response(text: str, model: str = "claude-sonnet-4-6") -> LLMResponse:
    return LLMResponse(
        text=text,
        model=model,
        input_tokens=10,
        output_tokens=20,
        latency_ms=50,
        stop_reason="end_turn",
    )


@pytest.fixture
def patient_context() -> PatientContext:
    return make_patient_context()


@pytest.fixture
def make_llm():
    """Factory: returns a MagicMock AnthropicClient whose .chat returns text."""

    def _factory(text: str, model: str = "claude-sonnet-4-6") -> MagicMock:
        llm = MagicMock()
        llm.chat = AsyncMock(return_value=make_llm_response(text, model))
        return llm

    return _factory
