"""Queue call-order endpoint — the authoritative "who to call next" ordering.

The frontend renders THIS ordering instead of computing callRank in TSX
(Phase 4, cluster #5). Pure ranking lives in services/queue_order.py.
Returns a FLAT list already sorted by call order; the board just groups by doctor.
"""

from __future__ import annotations

from datetime import date as date_cls

import asyncpg
from fastapi import APIRouter, Depends, Query

from clinicai.api.identity import StaffIdentity, get_current_identity
from clinicai.core.database import get_db_pool
from clinicai.services.queue_order import (
    QueueEntry,
    b3_ready_appt_ids,
    order_queue,
)

router = APIRouter()

# Day boundaries are VN-local (Asia/Ho_Chi_Minh) regardless of server timezone.
_APPT_SQL = """
SELECT a.id::text            AS appointment_id,
       a.doctor_id::text     AS doctor_id,
       a.slot_start,
       a.status,
       a.queue_number,
       a.booking_channel,
       p.full_name           AS patient_name,
       p.patient_code        AS patient_code,
       s.full_name           AS doctor_name,
       st.name               AS service_name,
       v.checked_in_at,
       v.status              AS visit_status
FROM appointment a
JOIN patient p        ON p.clinic_patient_id = a.clinic_patient_id
LEFT JOIN staff s        ON s.id = a.doctor_id
LEFT JOIN service_type st ON st.id = a.service_type_id
LEFT JOIN LATERAL (
    SELECT checked_in_at, status
    FROM visit
    WHERE appointment_id = a.id
    ORDER BY checked_in_at DESC NULLS LAST
    LIMIT 1
) v ON true
WHERE a.slot_start >= ($1::date)::timestamp AT TIME ZONE 'Asia/Ho_Chi_Minh'
  AND a.slot_start <  (($1::date) + 1)::timestamp AT TIME ZONE 'Asia/Ho_Chi_Minh'
  AND a.status = 'CHECKED_IN'
  AND a.clinic_id = $2::uuid
"""

_LAB_SQL = """
SELECT appointment_id::text AS appointment_id, result_value, external_ref
FROM lab_result
WHERE appointment_id::text = ANY($1::text[])
  AND clinic_id = $2::uuid
"""


@router.get("/queue")
async def get_queue(
    date: date_cls | None = Query(default=None),
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, object]:
    """Today's CHECKED_IN patients for the caller's clinic, in calling order.

    This used to be reachable with the shared API key alone and returned patient
    names and codes for every clinic. It now requires a staff token and is
    scoped to that member's clinic.
    """
    day = date or date_cls.today()
    appt_rows = await pool.fetch(_APPT_SQL, day, identity.clinic_id)
    appt_ids = [r["appointment_id"] for r in appt_rows]

    labs = await pool.fetch(_LAB_SQL, appt_ids, identity.clinic_id) if appt_ids else []
    b3 = b3_ready_appt_ids([dict(lab) for lab in labs])
    by_id = {r["appointment_id"]: r for r in appt_rows}

    entries = [
        QueueEntry(
            appointment_id=r["appointment_id"],
            doctor_id=r["doctor_id"],
            queue_number=r["queue_number"],
            slot_start=r["slot_start"],
            checked_in_at=r["checked_in_at"],
            booking_channel=r["booking_channel"],
            b3_ready=r["appointment_id"] in b3,
            visit_status=r["visit_status"],
        )
        for r in appt_rows
    ]

    rows: list[dict[str, object]] = []
    for e in order_queue(entries):
        r = by_id[e.appointment_id]
        rows.append(
            {
                "id": e.appointment_id,
                "slot_start": e.slot_start.isoformat(),
                "status": r["status"],
                "queue_number": e.queue_number,
                "booking_channel": e.booking_channel,
                "patient": {
                    "full_name": r["patient_name"],
                    "patient_code": r["patient_code"],
                },
                "doctor": {"full_name": r["doctor_name"]},
                "service": {"name": r["service_name"]},
                "checked_in_at": (
                    e.checked_in_at.isoformat() if e.checked_in_at else None
                ),
                "visit_status": e.visit_status,
                "b3_ready": e.b3_ready,
            }
        )

    return {"date": day.isoformat(), "rows": rows}
