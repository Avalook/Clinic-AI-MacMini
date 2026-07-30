"""Per-visit progress flags for the front desk (ROLE-02, ADR-0012).

WHY THIS EXISTS. /home shows a progress bar per patient: arrived → vitals taken
→ seen → paid. It built that by reading `clinical_record` and `prescription`
through the caller's own session, which meant reception — who opens /home all
day — had to be able to read the doctor's note. That single read was what kept
the role-level RLS tightening (ROLE-02) blocked: narrowing the policy while the
screen still did it would only have blanked the screen.

So the read moves here, and what goes back is the answer, not the evidence: four
booleans and the list of fees already collected. Reception learns that vitals
were taken; it does not learn the blood pressure. That is the distinction the
policy could not draw and an endpoint can.

Any signed-in staff member may call this — it is the same information the
progress bar has always shown — but the tables it reads are now closed to them
directly (migration 20260730000013).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone

import asyncpg
import structlog

from clinicai.api.exceptions import ValidationError

logger = structlog.get_logger()

# The clinic's day is a Vietnam-local day, not the server's.
_VN = timezone(timedelta(hours=7))

# /home asks for a week. The cap is there so a mistyped range cannot ask for a
# year of appointments in one query.
_MAX_RANGE_DAYS = 31


@dataclass(frozen=True)
class VisitProgress:
    appointment_id: str
    visit_id: str | None
    vitals_recorded: bool = False
    has_clinical_record: bool = False
    has_prescription: bool = False
    paid_kinds: list[str] = field(default_factory=list)


# One statement instead of the page's four round-trips. "Vitals recorded" means
# blood pressure, weight and height are all filled in — the rule the page used
# to apply after downloading every note, tested here where the rows already are.
_PROGRESS_SQL = """
    SELECT a.id::text                       AS appointment_id,
           v.visit_id::text                 AS visit_id,
           COALESCE(cr.vitals_recorded, FALSE) AS vitals_recorded,
           (cr.visit_id IS NOT NULL)        AS has_clinical_record,
           COALESCE(rx.has_prescription, FALSE) AS has_prescription,
           COALESCE(pay.kinds, ARRAY[]::text[]) AS paid_kinds
      FROM appointment a
      LEFT JOIN LATERAL (
          SELECT v2.visit_id
            FROM visit v2
           WHERE v2.appointment_id = a.id
           ORDER BY v2.created_at DESC
           LIMIT 1
      ) v ON TRUE
      LEFT JOIN LATERAL (
          SELECT r.visit_id,
                 bool_or(
                     NULLIF(TRIM(r.soap_objective #>> '{vitals,huyet_ap}'), '')
                         IS NOT NULL
                 AND NULLIF(TRIM(r.soap_objective #>> '{vitals,can_nang}'), '')
                         IS NOT NULL
                 AND NULLIF(TRIM(r.soap_objective #>> '{vitals,chieu_cao}'), '')
                         IS NOT NULL
                 ) AS vitals_recorded
            FROM clinical_record r
           WHERE r.visit_id = v.visit_id
           GROUP BY r.visit_id
      ) cr ON TRUE
      LEFT JOIN LATERAL (
          SELECT TRUE AS has_prescription
            FROM prescription p
           WHERE p.visit_id = v.visit_id
           LIMIT 1
      ) rx ON TRUE
      LEFT JOIN LATERAL (
          SELECT array_agg(DISTINCT pm.kind) AS kinds
            FROM payment pm
           WHERE pm.visit_id = v.visit_id
      ) pay ON TRUE
     WHERE a.clinic_id = COALESCE($1::uuid, public.default_clinic_id())
       AND a.slot_start >= $2::timestamptz
       AND a.slot_start <  $3::timestamptz
       AND a.status NOT IN ('CANCELLED', 'NO_SHOW')
"""


class VisitProgressService:
    """Read-only progress flags for a day's appointments."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def for_range(
        self, *, date_from: date, date_to: date, clinic_id: str | None
    ) -> list[VisitProgress]:
        """Flags for every live appointment from `date_from` to `date_to`.

        A range rather than a day because /home draws a week: one call for the
        board, instead of one per column. Both ends are Vietnam-local calendar
        days and both are inclusive — the clinic's day is what the board shows,
        and doing that conversion here stops each caller getting it slightly
        differently.
        """
        if date_to < date_from:
            raise ValidationError("Khoảng ngày không hợp lệ")
        if (date_to - date_from).days > _MAX_RANGE_DAYS:
            raise ValidationError(f"Khoảng ngày tối đa {_MAX_RANGE_DAYS} ngày")

        # Real datetimes, not ISO strings: asyncpg encodes the parameter on the
        # client from the inferred type, so a "::timestamptz" cast in the SQL
        # does not make a string acceptable.
        start = datetime.combine(date_from, time.min, tzinfo=_VN)
        end = datetime.combine(date_to, time.min, tzinfo=_VN) + timedelta(days=1)

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(_PROGRESS_SQL, clinic_id, start, end)

        return [
            VisitProgress(
                appointment_id=r["appointment_id"],
                visit_id=r["visit_id"],
                vitals_recorded=r["vitals_recorded"],
                has_clinical_record=r["has_clinical_record"],
                has_prescription=r["has_prescription"],
                paid_kinds=sorted(r["paid_kinds"] or []),
            )
            for r in rows
        ]
