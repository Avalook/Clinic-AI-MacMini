"""One way to write an audit row, so every write path leaves the same trail.

WHY THIS FILE EXISTS. An audit of 2026-08-03 asked a simple question of every
service that writes to the database — "does this leave a record of who did it?"
— and found the answer was no for the writes that matter most:

    clinical_record_service   clinical_record, patient_medical_profile,
                              prescription, visit
    clinical_form_service     clinical_form_response
    ultrasound_service        ultrasound_record
    staff_service             staff, clinic_membership  ← role/privilege changes
    scheduling_service        appointment, work_session

Booking, payment, CSKH and lab all wrote to ``event_log``; the clinical half of
the system wrote nothing. So "Lịch sử thao tác" could tell a manager who moved
an appointment but not who wrote the medical note, and a staff member's role
could be changed with no record that it happened. For a clinic that is the wrong
way round: the appointment is operational, the note is the legal document.

The reason was not neglect so much as friction — each service would have needed
its own twenty-line INSERT with its own JSON shape, so the easy thing was to
skip it. This makes writing the row the easy thing.

WHAT IS NEVER PUT IN A PAYLOAD. Identifiers, not content. `clinical_record_id`,
not the note; `patient_id`, not the name; field NAMES that changed, not their
values. The audit trail answers who/when/which-record and deliberately cannot
answer "what did the note say" — that question has a different screen, a
different RLS policy, and a different set of people allowed to ask it. Putting
clinical text here would quietly widen who can read it, because the audit screen
is open to operations roles that cannot open a chart.

TRANSACTIONAL, ALWAYS. ``conn`` is the caller's connection, so the audit row
commits with the write it describes or not at all. A trail that can be missing
exactly when a write half-failed is worse than no trail, because it reads as
"this did not happen".
"""

from __future__ import annotations

import json
from typing import Any

import asyncpg
import structlog

from clinicai.api.identity import StaffIdentity

logger = structlog.get_logger()


async def record_event(
    conn: asyncpg.Connection,
    *,
    event_type: str,
    aggregate_type: str,
    aggregate_id: str,
    identity: StaffIdentity,
    origin: str,
    payload: dict[str, Any] | None = None,
) -> None:
    """Append one row to ``event_log`` on the caller's transaction.

    ``event_type``      dotted verb, e.g. ``clinical_record.saved``
    ``aggregate_type``  the table/entity the event is about
    ``aggregate_id``    its id
    ``origin``          which code path wrote it, e.g. ``api:clinical-record``
    ``payload``         identifiers and field names only — never clinical text
    """
    await conn.execute(
        """
        INSERT INTO event_log
            (clinic_id, event_type, aggregate_type, aggregate_id, payload,
             metadata, source, event_published)
        VALUES ($1::uuid, $2, $3, $4, $5, $6, $7, FALSE)
        """,
        identity.clinic_id,
        event_type,
        aggregate_type,
        aggregate_id,
        json.dumps(payload or {}),
        json.dumps(
            {
                "clinic_role": identity.role.value,
                "clinic_staff_id": identity.staff_id,
                "actor_auth_user_id": identity.auth_user_id,
                "origin": origin,
            }
        ),
        origin,
    )


def changed_fields(payload: dict[str, Any] | None) -> list[str]:
    """The NAMES of the fields a write touched, sorted; never their values.

    Enough for "the doctor changed the diagnosis at 14:02" without putting the
    diagnosis in a table that operations roles can read.
    """
    if not payload:
        return []
    return sorted(k for k, v in payload.items() if v is not None)
