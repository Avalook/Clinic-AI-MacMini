"""TỰ NHẮC VIỆC — một người tự hẹn nhắc chính mình (nhóm 5, Tuyền chốt 23/09/2026).

"Nhắc tái khám: theo hẹn của bác sĩ, HOẶC tự tạo việc cho chính mình để tự
nhắc." Ghi một dòng + một cái hẹn giờ trong CÙNG giao dịch; tới giờ, bên xử lý hẹn
(`events/consumers/nhac_viec.py`) kiểm lại (đã xong thì thôi) rồi réo chuông đích
danh người ấy.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import asyncpg

from clinicai.api.exceptions import NotFoundError, ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.core.clock import CLINIC_TZ
from clinicai.core.tran import canh_bao_neu_day
from clinicai.events.hen_gio import hen, huy_hen

HEN_NHAC = "nhac_viec.ca_nhan"
_XA_NHAT = timedelta(days=400)


def doc_nhac_luc(raw: Any) -> datetime | None:
    """Giờ nhắc người dùng gửi (ISO; không múi giờ = giờ Việt Nam). Rác → None,
    KHÔNG ném (CLAUDE.md: ba lần 500 vì hàm ngày/giờ ném)."""
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        v = datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if v.tzinfo is None:
        v = v.replace(tzinfo=CLINIC_TZ)
    return v


class NhacViecService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def tao(
        self,
        *,
        identity: StaffIdentity,
        noi_dung: Any,
        nhac_luc: Any,
        clinic_patient_id: str | None = None,
        visit_id: str | None = None,
    ) -> dict[str, Any]:
        nd = noi_dung.strip() if isinstance(noi_dung, str) else ""
        if not 1 <= len(nd) <= 500:
            raise ValidationError("Nội dung nhắc từ 1 đến 500 ký tự.")
        luc = doc_nhac_luc(nhac_luc)
        if luc is None:
            raise ValidationError("Giờ nhắc không hợp lệ.")
        bay_gio = datetime.now(CLINIC_TZ)
        if luc > bay_gio + _XA_NHAT:
            raise ValidationError("Chỉ hẹn nhắc trong vòng 400 ngày.")
        async with self._pool.acquire() as conn, conn.transaction():
            ma = await conn.fetchval(
                """
                INSERT INTO nhac_viec_ca_nhan
                    (clinic_id, staff_id, clinic_patient_id, visit_id, noi_dung,
                     nhac_luc)
                VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, $5, $6)
                RETURNING id::text
                """,
                identity.clinic_id,
                identity.staff_id,
                clinic_patient_id,
                visit_id,
                nd,
                luc,
            )
            await hen(
                conn,
                clinic_id=identity.clinic_id,
                loai=HEN_NHAC,
                sau=max(luc - bay_gio, timedelta(0)),
                ve_cai_gi=str(ma),
            )
        return {"ok": True, "id": ma, "nhac_luc": luc.isoformat()}

    async def cua_toi(
        self, *, identity: StaffIdentity, clinic_patient_id: str | None = None
    ) -> list[dict[str, Any]]:
        rows = await self._pool.fetch(
            """
            SELECT id::text, noi_dung, nhac_luc, xong_luc,
                   clinic_patient_id::text AS clinic_patient_id
              FROM nhac_viec_ca_nhan
             WHERE clinic_id = $1::uuid AND staff_id = $2::uuid
               AND ($3::uuid IS NULL OR clinic_patient_id = $3::uuid)
               AND (xong_luc IS NULL OR xong_luc > now() - interval '7 days')
             ORDER BY xong_luc NULLS FIRST, nhac_luc
             LIMIT 100
            """,
            identity.clinic_id,
            identity.staff_id,
            clinic_patient_id,
        )
        canh_bao_neu_day("nhac_viec_ca_nhan.cua_toi", len(rows), 100)
        return [
            {
                "id": r["id"],
                "noi_dung": r["noi_dung"],
                "nhac_luc": r["nhac_luc"].isoformat(),
                "xong": r["xong_luc"] is not None,
                "clinic_patient_id": r["clinic_patient_id"],
            }
            for r in rows
        ]

    async def xong(self, *, identity: StaffIdentity, nhac_id: str) -> dict[str, Any]:
        async with self._pool.acquire() as conn, conn.transaction():
            row = await conn.fetchval(
                "UPDATE nhac_viec_ca_nhan SET xong_luc = coalesce(xong_luc, now())"
                " WHERE clinic_id = $1::uuid AND id = $2::uuid AND staff_id = $3::uuid"
                " RETURNING id::text",
                identity.clinic_id,
                nhac_id,
                identity.staff_id,
            )
            if row is None:
                raise NotFoundError("Không tìm thấy việc nhắc này của bạn.")
            await huy_hen(
                conn, clinic_id=identity.clinic_id, loai=HEN_NHAC, ve_cai_gi=nhac_id
            )
        return {"ok": True}


__all__ = ["HEN_NHAC", "NhacViecService", "doc_nhac_luc"]
