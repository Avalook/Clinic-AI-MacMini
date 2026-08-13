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
    VISIT_DA_RA_VE,
    b3_ready_appt_ids,
    explain_queue,
)
from clinicai.services.queue_rows import entry_from_row

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
       v.status              AS visit_status,
       cap.slot_minutes
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
-- Độ dài khung giờ ÁP DỤNG CHO CHÍNH LỊCH NÀY, để suy ra cửa sổ "đến đúng giờ".
--
-- Dùng resolve_effective_cap chứ không đọc thẳng clinic.settings: đây đúng là
-- hàm mà trigger enforce_slot_capacity dùng khi quyết định khung còn chỗ hay
-- không. Hai bên đọc chung một nguồn thì không thể lệch — bảng gọi số nói khung
-- 15 phút trong khi bộ nhận lịch nghĩ 30 phút là loại sai lầm không ai lần ra.
LEFT JOIN LATERAL public.resolve_effective_cap(
    a.clinic_id, a.doctor_id, a.slot_start
) cap ON true
WHERE a.slot_start >= ($1::date)::timestamp AT TIME ZONE 'Asia/Ho_Chi_Minh'
  AND a.slot_start <  (($1::date) + 1)::timestamp AT TIME ZONE 'Asia/Ho_Chi_Minh'
  AND a.status = 'CHECKED_IN'
  AND a.clinic_id = $2::uuid
  -- Người đã ra về thì rời hàng chờ, dù lịch hẹn vẫn ở CHECKED_IN.
  --
  -- Lịch hẹn CỐ Ý không đổi trạng thái khi khách về giữa chừng: họ CÓ đến, và
  -- đánh dấu COMPLETED sẽ là nói dối rằng bác sĩ đã khám xong. Nên chỗ lọc
  -- đúng là trạng thái LƯỢT KHÁM.
  AND coalesce(v.status, '') <> ALL ($3::text[])
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
    appt_rows = await pool.fetch(
        _APPT_SQL, day, identity.clinic_id, sorted(VISIT_DA_RA_VE)
    )
    appt_ids = [r["appointment_id"] for r in appt_rows]

    labs = await pool.fetch(_LAB_SQL, appt_ids, identity.clinic_id) if appt_ids else []
    b3 = b3_ready_appt_ids([dict(lab) for lab in labs])
    by_id = {r["appointment_id"]: r for r in appt_rows}

    # `/queue` chỉ nhìn MỘT ngày nên không cần gom nhóm — nhưng vẫn dựng
    # QueueEntry qua cùng một hàm với hai bảng kia, để ba bảng không thể hiểu
    # khác nhau về cùng một hàng dữ liệu.
    entries = [
        entry_from_row(
            {**dict(r), "b3_ready": r["appointment_id"] in b3},
            id_key="appointment_id",
        )
        for r in appt_rows
    ]

    rows: list[dict[str, object]] = []
    for d in explain_queue(entries):
        e = d.entry
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
                # Thứ tự VÀ lý do đi cùng nhau. Màn hình chỉ việc hiển thị —
                # không màn nào tự xếp lại, không màn nào tự đoán lý do.
                "call_order": d.call_order,
                "call_tier": d.call_tier,
                "call_reason": d.call_reason,
                "promoted": d.promoted,
                "promoted_over": d.promoted_over,
            }
        )

    return {"date": day.isoformat(), "rows": rows}
