"""Patient context aggregation for the pre-visit brief flow (P9.7c).

Pulls patient demographics + last/next visit + medical profile + current
pregnancy + recent labs + latest ultrasound into a single PatientContext
value. The brief LLM consumes this object — no clinical decisions are
encoded here, only data shaping.

Data sources (per P9.7c wiring):
- `patient_summary` VIEW (migration 018): identity (incl. phone_primary),
  total_visits, last_visit_at, next upcoming appointment, last-lab snapshot.
- `patient_medical_profile`: chronic diseases, medications, allergies, blood type.
- `pregnancy` (ONGOING): LMP → gestational age, high-risk reason.
- `lab_result` (recent N): full set for the brief; the VIEW only carries
  the single latest snapshot.
- `ultrasound_record` (migration 018, latest by performed_at): mốc siêu âm
  gần nhất cho BS xem trước ca khám.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timezone
from typing import TYPE_CHECKING, Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from clinicai.tools._common.context import TraceContext

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    import asyncpg

logger = logging.getLogger(__name__)

# Recent record caps — keep the LLM input tight.
_RECENT_LAB_LIMIT = 5
_RECENT_ULTRASOUND_LIMIT = 3


class PatientContext(BaseModel):
    """Aggregated patient data — input to the pre-visit brief LLM."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    clinic_patient_id: UUID
    patient_code: str
    full_name: str
    date_of_birth: date | None
    phone_primary: str | None = None

    # Pregnancy (nullable when no ONGOING pregnancy)
    current_ga_weeks: float | None
    current_pregnancy_id: UUID | None
    pregnancy_complications: list[str] = Field(default_factory=list)

    # Medical profile
    chronic_diseases: list[str] = Field(default_factory=list)
    current_medications: list[str] = Field(default_factory=list)
    allergies: list[str] = Field(default_factory=list)
    blood_type: str | None

    # Visit snapshot — sourced from patient_summary VIEW (real visit table)
    last_visit_date: datetime | None
    last_visit_summary: dict[str, Any] | None
    last_visit_diagnosis: list[str] = Field(default_factory=list)
    total_visits: int = 0

    # Upcoming appointment (next SCHEDULED/CONFIRMED in the future)
    next_appointment_at: datetime | None = None
    next_appointment_status: str | None = None

    # Latest lab results (recent N) + pending GROUP_C queue
    latest_lab_results: list[dict[str, Any]] = Field(default_factory=list)
    pending_lab_review: list[dict[str, Any]] = Field(default_factory=list)

    # Latest ultrasound studies (recent N), oldest sourced from ultrasound_record
    latest_ultrasound_summary: list[dict[str, Any]] = Field(default_factory=list)

    # Ongoing issues — no structured source today
    ongoing_issues: list[str] = Field(default_factory=list)

    # Metadata
    data_freshness: datetime


# ---------------------------------------------------------------------------
# SQL — small, parameterized, no f-string interpolation of values.
# ---------------------------------------------------------------------------

_PATIENT_SUMMARY_SQL = """
    SELECT
        clinic_patient_id,
        patient_code,
        full_name,
        date_of_birth,
        phone_primary,
        last_visit_at,
        total_visits,
        next_appointment_at,
        next_appointment_status
    FROM patient_summary
    WHERE clinic_patient_id = $1
      AND clinic_id = $2::uuid
    LIMIT 1
"""

_MEDICAL_PROFILE_SQL = """
    SELECT
        blood_type,
        allergies,
        chronic_diseases,
        current_medications
    FROM patient_medical_profile
    WHERE clinic_patient_id = $1
      AND clinic_id = $2::uuid
    LIMIT 1
"""

_CURRENT_PREGNANCY_SQL = """
    SELECT
        id AS pregnancy_id,
        lmp_date,
        edd_date,
        gestational_age_at_registration,
        outcome,
        is_high_risk,
        high_risk_reason
    FROM pregnancy
    WHERE clinic_patient_id = $1
      AND clinic_id = $2::uuid
      AND outcome = 'ONGOING'
    ORDER BY created_at DESC
    LIMIT 1
"""

_RECENT_LABS_SQL = """
    SELECT
        lab_result_id,
        test_code,
        test_name,
        panel_code,
        result_value,
        flag,
        triage_group,
        triage_reason,
        requires_doctor_review,
        is_finalized,
        result_received_at
    FROM lab_result
    WHERE clinic_patient_id = $1
      AND clinic_id = $3::uuid
    ORDER BY result_received_at DESC
    LIMIT $2
"""

_LATEST_ULTRASOUND_SQL = """
    SELECT
        ultrasound_id,
        ultrasound_type,
        gestational_age_weeks,
        findings,
        impression,
        performed_at
    FROM ultrasound_record
    WHERE clinic_patient_id = $1
      AND clinic_id = $3::uuid
    ORDER BY COALESCE(performed_at, created_at) DESC
    LIMIT $2
"""


class PatientNotFoundError(ValueError):
    """Raised when no patient row matches the requested clinic_patient_id."""


def _compute_ga_weeks(lmp_date: date | None, today: date) -> float | None:
    """Compute current gestational age in weeks from LMP. Returns None if no LMP.

    Uses LMP rather than EDD because EDD is derived; LMP is the recorded
    anchor and matches OB convention (40w from LMP).
    """
    if lmp_date is None:
        return None
    days = (today - lmp_date).days
    if days < 0:
        return None
    return round(days / 7.0, 1)


def _pregnancy_complications(record: "asyncpg.Record | None") -> list[str]:
    """Surface high_risk_reason as the sole complication signal we have."""
    if record is None:
        return []
    if not record.get("is_high_risk"):
        return []
    reason = record.get("high_risk_reason")
    return [str(reason)] if reason else ["High-risk pregnancy"]


def _lab_to_dict(record: "asyncpg.Record") -> dict[str, Any]:
    """Project a lab_result row into a brief-friendly dict."""
    return {
        "lab_result_id": str(record["lab_result_id"]),
        "test_code": record["test_code"],
        "test_name": record["test_name"],
        "panel_code": record["panel_code"],
        "result_value": record["result_value"],
        "flag": record["flag"],
        "triage_group": record["triage_group"],
        "triage_reason": record["triage_reason"],
        "requires_doctor_review": record["requires_doctor_review"],
        "is_finalized": record["is_finalized"],
        "result_received_at": (
            record["result_received_at"].isoformat()
            if record["result_received_at"] is not None
            else None
        ),
    }


def _ultrasound_to_dict(record: "asyncpg.Record") -> dict[str, Any]:
    """Project an ultrasound_record row into a brief-friendly dict."""
    return {
        "ultrasound_id": str(record["ultrasound_id"]),
        "ultrasound_type": record["ultrasound_type"],
        "gestational_age_weeks": (
            float(record["gestational_age_weeks"])
            if record["gestational_age_weeks"] is not None
            else None
        ),
        "findings": record["findings"],
        "impression": record["impression"],
        "performed_at": (
            record["performed_at"].isoformat()
            if record["performed_at"] is not None
            else None
        ),
    }


async def _fetch_patient_summary(
    conn: "asyncpg.Connection", clinic_patient_id: UUID, clinic_id: str | None
) -> "asyncpg.Record | None":
    return await conn.fetchrow(_PATIENT_SUMMARY_SQL, clinic_patient_id, clinic_id)


async def _fetch_medical_profile(
    conn: "asyncpg.Connection", clinic_patient_id: UUID, clinic_id: str | None
) -> "asyncpg.Record | None":
    return await conn.fetchrow(_MEDICAL_PROFILE_SQL, clinic_patient_id, clinic_id)


async def _fetch_current_pregnancy(
    conn: "asyncpg.Connection", clinic_patient_id: UUID, clinic_id: str | None
) -> "asyncpg.Record | None":
    return await conn.fetchrow(_CURRENT_PREGNANCY_SQL, clinic_patient_id, clinic_id)


async def _fetch_recent_labs(
    conn: "asyncpg.Connection", clinic_patient_id: UUID, clinic_id: str | None
) -> "list[asyncpg.Record]":
    rows = await conn.fetch(
        _RECENT_LABS_SQL, clinic_patient_id, _RECENT_LAB_LIMIT, clinic_id
    )
    return list(rows)


async def _fetch_latest_ultrasounds(
    conn: "asyncpg.Connection", clinic_patient_id: UUID, clinic_id: str | None
) -> "list[asyncpg.Record]":
    rows = await conn.fetch(
        _LATEST_ULTRASOUND_SQL,
        clinic_patient_id,
        _RECENT_ULTRASOUND_LIMIT,
        clinic_id,
    )
    return list(rows)


async def aggregate_patient_context(
    pool: "asyncpg.Pool",
    clinic_patient_id: UUID,
    trace: TraceContext,
    clinic_id: str,
) -> PatientContext:
    """Aggregate patient data for the pre-visit brief.

    The five reads run concurrently, each on its OWN pooled connection:
    patient_summary VIEW, medical profile, ONGOING pregnancy, recent labs,
    latest ultrasound studies. A single asyncpg connection cannot serve
    concurrent operations ("another operation is in progress"), so each
    coroutine acquires its own connection from the pool — matching the
    one-acquire-per-unit-of-work pattern used across the codebase.

    Args:
        pool: asyncpg connection pool.
        clinic_patient_id: target patient PK.
        trace: per-invocation TraceContext for observability.

    Returns:
        PatientContext.

    Raises:
        PatientNotFoundError: if patient_summary returns no row.
        asyncpg errors propagate unchanged.
    """
    logger.debug(
        "service.aggregate_patient_context",
        extra={
            "trace_id": str(trace.trace_id),
            "clinic_patient_id": str(clinic_patient_id),
        },
    )

    async def _run(
        fetch: "Callable[[asyncpg.Connection, UUID, str | None], Awaitable[Any]]",
    ) -> Any:
        async with pool.acquire() as conn:
            return await fetch(conn, clinic_patient_id, clinic_id)

    (
        summary_rec,
        profile_rec,
        pregnancy_rec,
        lab_rows,
        us_rows,
    ) = await asyncio.gather(
        _run(_fetch_patient_summary),
        _run(_fetch_medical_profile),
        _run(_fetch_current_pregnancy),
        _run(_fetch_recent_labs),
        _run(_fetch_latest_ultrasounds),
    )

    if summary_rec is None:
        raise PatientNotFoundError(
            f"patient not found: clinic_patient_id={clinic_patient_id}"
        )

    # Pregnancy slot
    current_ga_weeks: float | None = None
    current_pregnancy_id: UUID | None = None
    if pregnancy_rec is not None:
        current_pregnancy_id = pregnancy_rec["pregnancy_id"]
        current_ga_weeks = _compute_ga_weeks(
            pregnancy_rec.get("lmp_date"), date.today()
        )

    # Medical profile slot — VIEW does not carry it.
    chronic: list[str] = []
    meds: list[str] = []
    allergies: list[str] = []
    blood_type: str | None = None
    if profile_rec is not None:
        chronic = list(profile_rec["chronic_diseases"] or [])
        meds = list(profile_rec["current_medications"] or [])
        allergies = list(profile_rec["allergies"] or [])
        blood_type = profile_rec["blood_type"]

    # Lab slots
    latest_labs = [_lab_to_dict(r) for r in lab_rows]
    pending_review = [
        labd
        for labd in latest_labs
        if labd["triage_group"] == "GROUP_C"
        and labd["requires_doctor_review"]
        and not labd["is_finalized"]
    ]

    # Ultrasound slot — new in P9.7c via mig018.
    ultrasounds = [_ultrasound_to_dict(r) for r in us_rows]

    return PatientContext(
        clinic_patient_id=summary_rec["clinic_patient_id"],
        patient_code=summary_rec["patient_code"],
        full_name=summary_rec["full_name"],
        date_of_birth=summary_rec["date_of_birth"],
        phone_primary=summary_rec["phone_primary"],
        current_ga_weeks=current_ga_weeks,
        current_pregnancy_id=current_pregnancy_id,
        pregnancy_complications=_pregnancy_complications(pregnancy_rec),
        chronic_diseases=chronic,
        current_medications=meds,
        allergies=allergies,
        blood_type=blood_type,
        last_visit_date=summary_rec["last_visit_at"],
        last_visit_summary=None,  # visit-level SOAP retrieval deferred
        last_visit_diagnosis=[],  # ditto
        total_visits=int(summary_rec["total_visits"] or 0),
        next_appointment_at=summary_rec["next_appointment_at"],
        next_appointment_status=summary_rec["next_appointment_status"],
        latest_lab_results=latest_labs,
        pending_lab_review=pending_review,
        latest_ultrasound_summary=ultrasounds,
        ongoing_issues=[],
        data_freshness=datetime.now(tz=timezone.utc),
    )
