"""Tool: scheduling.find_work_sessions — list work sessions + available doctors.

Used by sub-graph find_doctor_node to discover which doctors are on duty
for a given (location, date, session_type) tuple.
"""

from __future__ import annotations

import json
from datetime import date as date_type
from typing import TYPE_CHECKING, Any, Literal
from uuid import UUID

import structlog
from pydantic import BaseModel

if TYPE_CHECKING:
    import asyncpg

logger = structlog.get_logger()


SessionTypeStr = Literal["EVENING", "WEEKEND_MORNING", "WEEKEND_AFTERNOON"]


class FindWorkSessionsInput(BaseModel):
    """Input schema for find_work_sessions."""

    location_id: UUID
    session_date: date_type
    session_type: SessionTypeStr


class WorkSessionResult(BaseModel):
    """One work session with available doctors."""

    session_id: UUID
    session_date: date_type
    session_type: str
    start_time: str
    end_time: str
    max_patients: int | None
    available_doctors: list[dict[str, Any]]


class FindWorkSessionsOutput(BaseModel):
    """List of work sessions matching the query."""

    sessions: list[WorkSessionResult]


_SQL = """
    SELECT
        ws.id            AS session_id,
        ws.session_date,
        ws.session_type,
        ws.start_time::text  AS start_time,
        ws.end_time::text    AS end_time,
        ws.max_patients,
        jsonb_agg(jsonb_build_object(
            'staff_id',     wss.staff_id,
            'full_name',    s.full_name,
            'on_call_flag', wss.on_call_flag
        ) ORDER BY wss.on_call_flag DESC) AS available_doctors
    FROM work_session ws
    JOIN work_session_staff wss ON wss.work_session_id = ws.id
    JOIN staff s ON s.id = wss.staff_id
    WHERE ws.location_id  = $1
      AND ws.session_date  = $2
      AND ws.session_type  = $3
      AND wss.role         = 'DOCTOR'
      AND wss.is_training  = FALSE
    GROUP BY ws.id, ws.session_date, ws.session_type,
             ws.start_time, ws.end_time, ws.max_patients
"""


async def find_work_sessions(
    input: FindWorkSessionsInput,
    pool: asyncpg.Pool,
) -> FindWorkSessionsOutput:
    """Return work sessions matching (location, date, session_type) with doctors.

    Excludes trainees (is_training=FALSE). Doctors sorted by on_call_flag DESC.
    """
    logger.info(
        "tool.scheduling.find_work_sessions",
        location_id=str(input.location_id),
        session_date=input.session_date.isoformat(),
        session_type=input.session_type,
    )

    rows = await pool.fetch(
        _SQL,
        input.location_id,
        input.session_date,
        input.session_type,
    )

    sessions: list[WorkSessionResult] = []
    for r in rows:
        doctors = r["available_doctors"]
        if isinstance(doctors, str):
            doctors = json.loads(doctors)
        sessions.append(
            WorkSessionResult(
                session_id=r["session_id"],
                session_date=r["session_date"],
                session_type=r["session_type"],
                start_time=r["start_time"],
                end_time=r["end_time"],
                max_patients=r["max_patients"],
                available_doctors=doctors or [],
            )
        )

    return FindWorkSessionsOutput(sessions=sessions)
