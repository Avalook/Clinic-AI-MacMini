"""API tests for POST /api/v1/lab/triage/{lab_result_id} (T-P9.4).

The endpoint runs the lab_triage sub-graph and enforces the API-layer
safety gate: GROUP_C + reviewed_at IS NULL → HTTP 403 via SafetyGateError.

We mock the pool to return a chosen lab_result row and monkeypatch
`classify_lab_result` on the nodes module (same pattern as the graph
skeleton tests) to drive the triage branch deterministically. The LLM
dependency is overridden with a MagicMock since classify is patched.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Iterator, Literal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import clinicai.graphs.lab_triage.nodes as _lt_nodes
from clinicai.api.v1.routers.lab import get_llm_client
from clinicai.core.database import get_db_pool
from clinicai.main import app
from clinicai.tools.lab.classify import ClassifyResult
from clinicai.tools.lab.query_lab_result import LabResultRow

_NOW = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)


def _lab_row(
    *,
    reviewed_at: datetime | None = None,
    test_name: str = "Generic test",
    panel_code: str | None = None,
) -> LabResultRow:
    return LabResultRow(
        lab_result_id=uuid4(),
        clinic_patient_id=uuid4(),
        visit_id=None,
        appointment_id=None,
        test_code="TEST",
        test_name=test_name,
        panel_code=panel_code,
        result_value=None,
        result_numeric=Decimal("0.0"),
        result_unit=None,
        reference_range_low=None,
        reference_range_high=None,
        flag=None,
        triage_group="PENDING",
        triage_reason=None,
        requires_doctor_review=False,
        reviewed_by_staff_id=None,
        reviewed_at=reviewed_at,
        is_finalized=False,
        lab_provider=None,
        sample_collected_at=None,
        result_received_at=_NOW,
    )


def _mock_pool_returning_row(row: LabResultRow) -> MagicMock:
    pool = MagicMock()
    conn = MagicMock()
    conn.fetchrow = AsyncMock(return_value=row.model_dump(mode="python"))
    acquire_ctx = AsyncMock()
    acquire_ctx.__aenter__.return_value = conn
    pool.acquire.return_value = acquire_ctx
    return pool


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def override_llm() -> Iterator[MagicMock]:
    """Hand back the LLM mock so individual tests can introspect it.

    The autouse _default_overrides fixture below already installs a
    MagicMock LLM, so this just hands back the installed mock for tests
    that want to assert on it. (classify is monkeypatched in all cases,
    so the LLM mock itself is never invoked.)
    """
    yield app.dependency_overrides[get_llm_client]()


def _set_classify_result(
    monkeypatch: pytest.MonkeyPatch,
    triage_group: Literal["GROUP_A", "GROUP_B", "GROUP_C", "PENDING"],
    requires_review: bool,
) -> None:
    monkeypatch.setattr(
        _lt_nodes,
        "classify_lab_result",
        AsyncMock(
            return_value=ClassifyResult(
                triage_group=triage_group,
                requires_doctor_review=requires_review,
                reason=f"{triage_group} reason",
                matched_rule_key="TEST_RULE",
                source="RULE",
                confidence=1.0,
            )
        ),
    )


def _override_pool(row: LabResultRow) -> MagicMock:
    pool = _mock_pool_returning_row(row)
    app.dependency_overrides[get_db_pool] = lambda: pool
    return pool


@pytest.fixture(autouse=True)
def _default_overrides() -> Iterator[None]:
    """Install default pool + LLM dep overrides for every test.

    Without these, `get_db_pool` / `get_llm_client` would read
    `app.state.db_pool` / `app.state.llm_client` — both unset under
    TestClient (no lifespan). Individual tests overwrite the pool via
    `_override_pool(row)` to drive the graph; classify is monkeypatched
    so the LLM mock itself is never actually invoked.
    """
    app.dependency_overrides[get_db_pool] = lambda: MagicMock()
    app.dependency_overrides[get_llm_client] = lambda: MagicMock()
    yield
    app.dependency_overrides.pop(get_db_pool, None)
    app.dependency_overrides.pop(get_llm_client, None)


# ──────────────────────────────────────────────────────────────────────────
# NEGATIVE — the medical safety gate (T-P9.4 packet requirement)
# ──────────────────────────────────────────────────────────────────────────


def test_lab_triage__group_c_unreviewed__raises_safety_gate_error(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    override_llm: MagicMock,
) -> None:
    """GROUP_C + reviewed_at IS NULL → SafetyGateError → HTTP 403.

    This is the medical safety gate locked by canon: BS phải review trước
    khi GROUP_C result được trả về cho BN.
    """
    row = _lab_row(reviewed_at=None, test_name="HIV antibody", panel_code="HIV")
    _override_pool(row)
    _set_classify_result(monkeypatch, "GROUP_C", requires_review=True)

    response = client.post(f"/api/v1/lab/triage/{row.lab_result_id}")

    assert response.status_code == 403, response.text
    body = response.json()
    assert body["error"] == "SAFETY_GATE_ERROR"
    assert "GROUP_C" in body["message"]
    assert "BS review" in body["message"]


# ──────────────────────────────────────────────────────────────────────────
# POSITIVE — gate releases when BS đã review
# ──────────────────────────────────────────────────────────────────────────


def test_lab_triage__group_c_reviewed__gate_releases_returns_200(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    override_llm: MagicMock,
) -> None:
    """GROUP_C + reviewed_at IS NOT NULL → gate releases → 200 OK.

    Response still suppresses patient-facing text (graph's hard_block path)
    but the API does not raise. Escalation note + task_ids remain visible.
    """
    reviewed = datetime(2026, 5, 22, 11, 30, tzinfo=timezone.utc)
    row = _lab_row(reviewed_at=reviewed, test_name="HIV antibody", panel_code="HIV")
    _override_pool(row)
    _set_classify_result(monkeypatch, "GROUP_C", requires_review=True)

    response = client.post(f"/api/v1/lab/triage/{row.lab_result_id}")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["triage_group"] == "GROUP_C"
    assert body["response_to_patient"] is None  # hard_block still suppresses
    assert body["escalation_note"] is not None
    assert body["requires_doctor_review"] is True


# ──────────────────────────────────────────────────────────────────────────
# POSITIVE — GROUP_A returns the patient response without raising
# ──────────────────────────────────────────────────────────────────────────


def test_lab_triage__group_a__returns_patient_response_200(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    override_llm: MagicMock,
) -> None:
    """GROUP_A → 200 + composed Vietnamese patient message. No gate."""
    row = _lab_row(test_name="CBC", panel_code="CBC")
    _override_pool(row)
    _set_classify_result(monkeypatch, "GROUP_A", requires_review=False)

    response = client.post(f"/api/v1/lab/triage/{row.lab_result_id}")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["triage_group"] == "GROUP_A"
    assert body["response_to_patient"] is not None
    assert body["escalation_note"] is None
    assert body["requires_doctor_review"] is False


# ──────────────────────────────────────────────────────────────────────────
# INPUT — invalid UUID is rejected by FastAPI before the graph runs
# ──────────────────────────────────────────────────────────────────────────


def test_lab_triage__invalid_uuid__422_pydantic(client: TestClient) -> None:
    """Non-UUID path param → 422 from FastAPI/pydantic, never reaches the graph."""
    response = client.post("/api/v1/lab/triage/not-a-uuid")
    assert response.status_code == 422
