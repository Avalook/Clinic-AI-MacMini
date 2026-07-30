"""Least-privilege recall projection for customer-care staff."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

import asyncpg

_LOOKBACK_DAYS = 183
_UPCOMING_DAYS = 7
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass(frozen=True)
class RecallFollowup:
    clinic_patient_id: str
    full_name: str
    phone_primary: str | None
    due_date: date
    repeat_tests: list[str] = field(default_factory=list)
    instruction: str = ""


_DUE_FOLLOWUPS_SQL = r"""
    WITH candidates AS (
        SELECT v.clinic_patient_id,
               p.full_name,
               p.phone_primary,
               v.created_at,
               cr.soap_plan #>> '{tai_kham,ngay}' AS due_text,
               CASE
                 WHEN jsonb_typeof(cr.soap_plan #> '{tai_kham,xn}') = 'array'
                 THEN ARRAY(
                     SELECT jsonb_array_elements_text(
                         cr.soap_plan #> '{tai_kham,xn}'
                     )
                 )
                 ELSE ARRAY[]::text[]
               END AS repeat_tests,
               COALESCE(
                   cr.soap_plan #>> '{tai_kham,ghi_chu}', ''
               ) AS instruction
          FROM visit v
          JOIN appointment source_appt
            ON source_appt.id = v.appointment_id
           AND source_appt.clinic_id = v.clinic_id
           AND source_appt.clinic_patient_id = v.clinic_patient_id
           AND source_appt.status = 'COMPLETED'
          JOIN clinical_record cr
            ON cr.visit_id = v.visit_id
           AND cr.clinic_id = v.clinic_id
          JOIN patient p
            ON p.clinic_patient_id = v.clinic_patient_id
           AND p.clinic_id = v.clinic_id
         WHERE v.clinic_id = $1::uuid
           AND v.status IN ('FINALIZED', 'AMENDED')
           AND v.created_at >= (
               $2::date AT TIME ZONE 'Asia/Ho_Chi_Minh'
           )
    ),
    latest_source AS (
        SELECT DISTINCT ON (clinic_patient_id)
               clinic_patient_id,
               full_name,
               phone_primary,
               due_text,
               repeat_tests,
               instruction
          FROM candidates
         ORDER BY clinic_patient_id, created_at DESC
    )
    SELECT r.clinic_patient_id::text,
           r.full_name,
           r.phone_primary,
           r.due_text,
           r.repeat_tests,
           r.instruction
      FROM latest_source r
     WHERE NOT EXISTS (
         SELECT 1
           FROM appointment future_appt
          WHERE future_appt.clinic_id = $1::uuid
            AND future_appt.clinic_patient_id = r.clinic_patient_id
            AND future_appt.slot_start >= (
                $3::date AT TIME ZONE 'Asia/Ho_Chi_Minh'
            )
            AND future_appt.status IN (
                'SCHEDULED', 'CSKH_CONFIRMED', 'CONFIRMED', 'CHECKED_IN'
            )
     )
     ORDER BY r.full_name
"""


def _parse_due_date(value: Any) -> date | None:
    """Parse one untrusted JSON date without letting it abort the whole batch."""
    if not isinstance(value, str) or _ISO_DATE.fullmatch(value) is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


class RecallService:
    """Return only the doctor's recall instruction needed by CSKH."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def due_followups(
        self,
        *,
        clinic_id: str,
        today: date,
    ) -> list[RecallFollowup]:
        since = today - timedelta(days=_LOOKBACK_DAYS)
        due_through = today + timedelta(days=_UPCOMING_DAYS)
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                _DUE_FOLLOWUPS_SQL,
                clinic_id,
                since,
                today,
            )
        followups: list[RecallFollowup] = []
        for row in rows:
            due_date = _parse_due_date(row["due_text"])
            if due_date is None or due_date > due_through:
                continue
            followups.append(
                RecallFollowup(
                    clinic_patient_id=str(row["clinic_patient_id"]),
                    full_name=row["full_name"] or "(không rõ tên)",
                    phone_primary=row["phone_primary"],
                    due_date=due_date,
                    repeat_tests=list(row["repeat_tests"] or []),
                    instruction=row["instruction"] or "",
                )
            )
        return sorted(followups, key=lambda item: (item.due_date, item.full_name))
