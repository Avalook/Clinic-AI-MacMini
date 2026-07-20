"""Unit tests for clinicai.services.patient_context_service.

Service uses `pool.acquire()` + `asyncio.gather` over a single connection
against five queries:

    fetchrow #1 — patient_summary VIEW (identity + visits + next appt + lab snapshot)
    fetchrow #2 — patient_medical_profile
    fetchrow #3 — pregnancy (ONGOING)
    fetch    #1 — lab_result (recent N)
    fetch    #2 — ultrasound_record (recent N)

The mock pool fixture programs each call's side_effect to match that order.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from clinicai.services.patient_context_service import (
    PatientContext,
    PatientNotFoundError,
    aggregate_patient_context,
)
from clinicai.tools._common.context import new_trace

_PATIENT_ID = UUID("11111111-1111-1111-1111-111111111111")
_NOW = datetime.now(tz=timezone.utc)


def _summary_record(
    *,
    last_visit_at: datetime | None = None,
    total_visits: int = 0,
    next_appointment_at: datetime | None = None,
    next_appointment_status: str | None = None,
    phone_primary: str | None = "0901234567",
) -> dict[str, Any]:
    return {
        "clinic_patient_id": _PATIENT_ID,
        "patient_code": "BN-2026-000001",
        "full_name": "Nguyễn Thị A",
        "date_of_birth": date(1992, 4, 15),
        "phone_primary": phone_primary,
        "last_visit_at": last_visit_at,
        "total_visits": total_visits,
        "next_appointment_at": next_appointment_at,
        "next_appointment_status": next_appointment_status,
    }


def _profile_record(
    *,
    blood_type: str | None = "A+",
    allergies: list[str] | None = None,
    chronic: list[str] | None = None,
    meds: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "blood_type": blood_type,
        "allergies": allergies or [],
        "chronic_diseases": chronic or [],
        "current_medications": meds or [],
    }


def _pregnancy_record(
    *,
    is_high_risk: bool = False,
    high_risk_reason: str | None = None,
    lmp_date: date | None = None,
) -> dict[str, Any]:
    return {
        "pregnancy_id": uuid4(),
        "lmp_date": lmp_date,
        "edd_date": None,
        "gestational_age_at_registration": None,
        "outcome": "ONGOING",
        "is_high_risk": is_high_risk,
        "high_risk_reason": high_risk_reason,
    }


def _lab_record(
    *,
    triage_group: str = "GROUP_A",
    requires_review: bool = False,
    is_finalized: bool = True,
) -> dict[str, Any]:
    return {
        "lab_result_id": uuid4(),
        "test_code": "CBC",
        "test_name": "Complete Blood Count",
        "panel_code": "CBC",
        "result_value": "OK",
        "flag": "NORMAL",
        "triage_group": triage_group,
        "triage_reason": None,
        "requires_doctor_review": requires_review,
        "is_finalized": is_finalized,
        "result_received_at": _NOW,
    }


def _ultrasound_record(
    *,
    ultrasound_type: str = "2D",
    ga_weeks: float | None = 24.5,
    impression: str | None = "Bình thường",
    performed_at: datetime | None = None,
) -> dict[str, Any]:
    return {
        "ultrasound_id": uuid4(),
        "ultrasound_type": ultrasound_type,
        "gestational_age_weeks": ga_weeks,
        "findings": {"BPD": "5.8cm"},
        "impression": impression,
        "performed_at": performed_at or _NOW,
    }


def _build_pool(
    *,
    summary: dict[str, Any] | None,
    profile: dict[str, Any] | None,
    pregnancy: dict[str, Any] | None,
    labs: list[dict[str, Any]],
    ultrasounds: list[dict[str, Any]],
) -> MagicMock:
    """Build a mock pool wired to the 5 gather'd queries (in service order)."""
    pool = MagicMock()
    conn = MagicMock()
    conn.fetchrow = AsyncMock(side_effect=[summary, profile, pregnancy])
    conn.fetch = AsyncMock(side_effect=[labs, ultrasounds])
    acquire_ctx = AsyncMock()
    acquire_ctx.__aenter__.return_value = conn
    acquire_ctx.__aexit__.return_value = False
    pool.acquire.return_value = acquire_ctx
    return pool


@pytest.mark.asyncio
async def test_aggregate__pregnant_patient__pregnancy_fields_populated() -> None:
    """ONGOING pregnancy with LMP → GA computed, complication surfaced."""
    from datetime import timedelta

    lmp_24w = date.today() - timedelta(weeks=24)
    pool = _build_pool(
        summary=_summary_record(),
        profile=_profile_record(),
        pregnancy=_pregnancy_record(
            is_high_risk=True,
            high_risk_reason="Tiền sử tiền sản giật",
            lmp_date=lmp_24w,
        ),
        labs=[],
        ultrasounds=[],
    )

    ctx = await aggregate_patient_context(pool, _PATIENT_ID, new_trace())

    assert isinstance(ctx, PatientContext)
    assert ctx.current_pregnancy_id is not None
    assert ctx.current_ga_weeks is not None
    assert 23.5 <= ctx.current_ga_weeks <= 24.5
    assert ctx.pregnancy_complications == ["Tiền sử tiền sản giật"]


@pytest.mark.asyncio
async def test_aggregate__no_recent_visits__last_visit_none_no_error() -> None:
    """Empty visit history in VIEW → last_visit_date None, total_visits 0."""
    pool = _build_pool(
        summary=_summary_record(last_visit_at=None, total_visits=0),
        profile=_profile_record(),
        pregnancy=None,
        labs=[],
        ultrasounds=[],
    )

    ctx = await aggregate_patient_context(pool, _PATIENT_ID, new_trace())

    assert ctx.last_visit_date is None
    assert ctx.last_visit_summary is None
    assert ctx.last_visit_diagnosis == []
    assert ctx.total_visits == 0


@pytest.mark.asyncio
async def test_aggregate__group_c_pending__included_in_pending_lab_review() -> None:
    """GROUP_C + requires_review + not finalized → surfaces in pending_lab_review."""
    pool = _build_pool(
        summary=_summary_record(),
        profile=_profile_record(),
        pregnancy=None,
        labs=[
            _lab_record(
                triage_group="GROUP_A", requires_review=False, is_finalized=True
            ),
            _lab_record(
                triage_group="GROUP_C", requires_review=True, is_finalized=False
            ),
        ],
        ultrasounds=[],
    )

    ctx = await aggregate_patient_context(pool, _PATIENT_ID, new_trace())

    assert len(ctx.latest_lab_results) == 2
    assert len(ctx.pending_lab_review) == 1
    assert ctx.pending_lab_review[0]["triage_group"] == "GROUP_C"


@pytest.mark.asyncio
async def test_aggregate__patient_not_found__raises_value_error() -> None:
    """Missing patient_summary row → PatientNotFoundError (ValueError subclass)."""
    pool = _build_pool(
        summary=None,
        profile=None,
        pregnancy=None,
        labs=[],
        ultrasounds=[],
    )

    with pytest.raises(PatientNotFoundError):
        await aggregate_patient_context(pool, _PATIENT_ID, new_trace())


@pytest.mark.asyncio
async def test_aggregate__view_columns_propagated__phone_visits_next_appt() -> None:
    """patient_summary VIEW columns (P9.7c wiring) appear in PatientContext."""
    next_at = datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc)
    pool = _build_pool(
        summary=_summary_record(
            last_visit_at=datetime(2026, 5, 1, 9, 0, tzinfo=timezone.utc),
            total_visits=3,
            next_appointment_at=next_at,
            next_appointment_status="CONFIRMED",
            phone_primary="0987654321",
        ),
        profile=_profile_record(),
        pregnancy=None,
        labs=[],
        ultrasounds=[],
    )

    ctx = await aggregate_patient_context(pool, _PATIENT_ID, new_trace())

    assert ctx.phone_primary == "0987654321"
    assert ctx.total_visits == 3
    assert ctx.next_appointment_at == next_at
    assert ctx.next_appointment_status == "CONFIRMED"
    assert ctx.last_visit_date == datetime(2026, 5, 1, 9, 0, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_aggregate__ultrasound_records__exposed_in_summary() -> None:
    """ultrasound_record rows → latest_ultrasound_summary entries (P9.7c)."""
    pool = _build_pool(
        summary=_summary_record(),
        profile=_profile_record(),
        pregnancy=None,
        labs=[],
        ultrasounds=[
            _ultrasound_record(
                ultrasound_type="2D",
                ga_weeks=24.5,
                impression="Bình thường",
            ),
            _ultrasound_record(
                ultrasound_type="Doppler",
                ga_weeks=25.0,
                impression="Theo dõi",
            ),
        ],
    )

    ctx = await aggregate_patient_context(pool, _PATIENT_ID, new_trace())

    assert len(ctx.latest_ultrasound_summary) == 2
    assert ctx.latest_ultrasound_summary[0]["ultrasound_type"] == "2D"
    assert ctx.latest_ultrasound_summary[0]["gestational_age_weeks"] == 24.5
    assert ctx.latest_ultrasound_summary[1]["ultrasound_type"] == "Doppler"


@pytest.mark.asyncio
async def test_aggregate__no_medical_profile__defaults_empty_lists() -> None:
    """profile row absent → defaults to empty lists, blood_type None, no crash."""
    pool = _build_pool(
        summary=_summary_record(),
        profile=None,
        pregnancy=None,
        labs=[],
        ultrasounds=[],
    )

    ctx = await aggregate_patient_context(pool, _PATIENT_ID, new_trace())

    assert ctx.blood_type is None
    assert ctx.chronic_diseases == []
    assert ctx.current_medications == []
    assert ctx.allergies == []
