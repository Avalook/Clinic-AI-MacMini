"""API tests for POST /api/v1/brief/{clinic_patient_id} (P9.5).

The endpoint instantiates the pre_visit_brief sub-graph internally. We
mock the service-layer aggregation via monkeypatch, override the LLM
dependency, and override the DB pool dependency.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

import clinicai.graphs.pre_visit_brief.nodes as _pvb_nodes
from clinicai.api.v1.routers.brief import get_llm_client
from clinicai.core.database import get_db_pool
from clinicai.llm.anthropic_client import LLMResponse
from clinicai.main import app
from clinicai.services.patient_context_service import (
    PatientContext,
    PatientNotFoundError,
)

_PATIENT_ID = UUID("11111111-1111-1111-1111-111111111111")
_NOW = datetime.now(tz=timezone.utc)

_VALID_BRIEF_JSON = {
    "headline": "Brief test.",
    "key_points": ["KP1"],
    "follow_up_items": [],
    "pending_reviews": [],
    "medications": [],
    "allergies": [],
    "pregnancy_context": None,
    "risk_flags": [],
    "suggested_questions": [],
    "confidence": 0.8,
}


def _patient_context() -> PatientContext:
    return PatientContext(
        clinic_patient_id=_PATIENT_ID,
        patient_code="BN-2026-000001",
        full_name="Nguyễn Thị A",
        date_of_birth=None,
        phone_primary=None,
        current_ga_weeks=None,
        current_pregnancy_id=None,
        pregnancy_complications=[],
        chronic_diseases=[],
        current_medications=[],
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


def _llm_returning(text: str) -> MagicMock:
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


@pytest.fixture(autouse=True)
def override_deps():
    """Override DB pool + LLM client deps for every test in this module."""
    pool = MagicMock()
    llm = _llm_returning(json.dumps(_VALID_BRIEF_JSON))
    app.dependency_overrides[get_db_pool] = lambda: pool
    app.dependency_overrides[get_llm_client] = lambda: llm
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_post_brief__valid_patient__returns_200_with_brief_and_markdown(
    client, monkeypatch
) -> None:
    monkeypatch.setattr(
        _pvb_nodes,
        "aggregate_patient_context",
        AsyncMock(return_value=_patient_context()),
    )

    response = client.post(f"/api/v1/brief/{_PATIENT_ID}")

    assert response.status_code == 200, response.text
    body = response.json()
    assert "brief" in body and "markdown" in body and "elapsed_ms" in body
    assert body["brief"]["headline"] == "Brief test."
    assert "# Brief — BN-2026-000001" in body["markdown"]
    assert isinstance(body["elapsed_ms"], int)


def test_post_brief__invalid_uuid__422_pydantic(client) -> None:
    response = client.post("/api/v1/brief/not-a-uuid")
    assert response.status_code == 422


def test_post_brief__patient_not_found__404(client, monkeypatch) -> None:
    monkeypatch.setattr(
        _pvb_nodes,
        "aggregate_patient_context",
        AsyncMock(side_effect=PatientNotFoundError("not found")),
    )

    response = client.post(f"/api/v1/brief/{_PATIENT_ID}")

    assert response.status_code == 404
    assert "patient_not_found" in response.json()["detail"]
