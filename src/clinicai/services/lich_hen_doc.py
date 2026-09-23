"""Các màn ĐỌC lịch hẹn mà route giao diện từng tự đọc bằng Supabase (24/09/2026).

`/api/appointments` (GET theo ngày / lịch sắp tới của một khách) và
`/api/appointments/service-history` từng gọi thẳng bảng `appointment` /
`care_episode` từ Next.js. Luật "frontend chỉ là giao diện" (SO-LUAT Phần 3):
đọc gì, lọc thế nào, phòng khám nào — ở đây, một chỗ, lọc đúng phòng khám của
người gọi (trước đây nhờ RLS của phiên trình duyệt).

Ngày nhận từ người dùng: rác thì trả RỖNG, không ném (CLAUDE.md — ba lần 500).
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any

import asyncpg

from clinicai.api.identity import StaffIdentity
from clinicai.core.clock import CLINIC_TZ
from clinicai.core.tran import canh_bao_neu_day

#: Trạng thái không còn là "lịch sắp tới" của khách.
_LICH_CHET = ("CANCELLED", "NO_SHOW", "DOCTOR_DECLINED")


def doc_ngay(chuoi: str | None) -> date | None:
    """YYYY-MM-DD → ngày; rác / rỗng → None (không ném)."""
    try:
        return date.fromisoformat((chuoi or "").strip())
    except ValueError:
        return None


def _iso(v: Any) -> Any:
    return v.isoformat() if isinstance(v, datetime) else v


async def lich_trong_ngay(
    pool: asyncpg.Pool,
    *,
    identity: StaffIdentity,
    ngay: str | None,
    doctor_id: str | None = None,
) -> list[dict[str, Any]]:
    """Lịch hẹn một ngày (giờ Việt Nam) — lưới đặt lịch / đổi lịch."""
    d = doc_ngay(ngay)
    if d is None:
        return []
    dau = datetime.combine(d, time.min, tzinfo=CLINIC_TZ)
    cuoi = dau + timedelta(days=1)
    rows = await pool.fetch(
        """
        SELECT id::text, slot_start, queue_number, status,
               doctor_id::text, booking_channel
          FROM appointment
         WHERE clinic_id = $1::uuid
           AND slot_start >= $2 AND slot_start < $3
           AND status NOT IN ('CANCELLED', 'NO_SHOW')
           AND ($4::uuid IS NULL OR doctor_id = $4::uuid)
         ORDER BY slot_start
         LIMIT 500
        """,
        identity.clinic_id,
        dau,
        cuoi,
        doctor_id or None,
    )
    canh_bao_neu_day(
        "lich_hen.trong_ngay", len(rows), 500, clinic_id=identity.clinic_id
    )
    return [{k: _iso(v) for k, v in dict(r).items()} for r in rows]


async def lich_sap_toi(
    pool: asyncpg.Pool, *, identity: StaffIdentity, clinic_patient_id: str
) -> list[dict[str, Any]]:
    """Lịch còn sống từ bây giờ trở đi của một khách (tối đa 20)."""
    rows = await pool.fetch(
        """
        SELECT id::text, slot_start, status, doctor_id::text,
               service_type_id::text
          FROM appointment
         WHERE clinic_id = $1::uuid AND clinic_patient_id = $2::uuid
           AND slot_start >= now()
           AND status <> ALL($3::text[])
         ORDER BY slot_start
         LIMIT 20
        """,
        identity.clinic_id,
        clinic_patient_id,
        list(_LICH_CHET),
    )
    canh_bao_neu_day("lich_hen.sap_toi", len(rows), 20, clinic_id=identity.clinic_id)
    return [{k: _iso(v) for k, v in dict(r).items()} for r in rows]


async def lich_su_dich_vu(
    pool: asyncpg.Pool,
    *,
    identity: StaffIdentity,
    clinic_patient_id: str,
    service_type_id: str,
) -> dict[str, Any]:
    """Khách đã đặt DỊCH VỤ này bao nhiêu lần + đợt khám còn sống (gợi ý NEW/RETURN)."""
    so_lan = await pool.fetchval(
        """
        SELECT count(*) FROM appointment
         WHERE clinic_id = $1::uuid AND clinic_patient_id = $2::uuid
           AND service_type_id = $3::uuid
           AND status NOT IN ('CANCELLED', 'NO_SHOW')
        """,
        identity.clinic_id,
        clinic_patient_id,
        service_type_id,
    )
    dot = await pool.fetchrow(
        """
        SELECT id::text, status, opened_at, last_visit_at
          FROM care_episode
         WHERE clinic_id = $1::uuid AND clinic_patient_id = $2::uuid
           AND service_type_id = $3::uuid AND status <> 'CLOSED'
         LIMIT 1
        """,
        identity.clinic_id,
        clinic_patient_id,
        service_type_id,
    )
    return {
        "serviceVisitCount": int(so_lan or 0),
        "liveEpisode": {k: _iso(v) for k, v in dict(dot).items()} if dot else None,
    }


__all__ = ["doc_ngay", "lich_su_dich_vu", "lich_sap_toi", "lich_trong_ngay"]
