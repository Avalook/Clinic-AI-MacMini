"""Theo dõi sau thủ thuật — bác sĩ quyết, CSKH chỉ nhìn (Tuyền chốt 16/09/2026).

"Đã làm thủ thuật" = việc DICHVU-THUTHUAT của lượt đã COMPLETED (bước dịch vụ
chỉ bác sĩ đóng). "Theo dõi sau" = cột `visit.theo_doi_thu_thuat`
(20260916000001): CAN sau N ngày, hoặc KHONG_CAN.

Hạn gọi = lúc làm xong thủ thuật + N ngày. Chưa làm xong thủ thuật thì chưa có
hạn — không bịa mốc từ lúc bác sĩ bấm chọn.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import asyncpg

from clinicai.api.exceptions import NotFoundError, ValidationError
from clinicai.api.identity import PHYSICIAN_ROLES, StaffIdentity
from clinicai.core.exceptions import SafetyGateError
from clinicai.services.audit import record_event

NODE_THU_THUAT = "DICHVU-THUTHUAT"
LUA_CHON = ("CAN", "KHONG_CAN")

_DOC_SQL = """
SELECT v.visit_id::text AS visit_id,
       v.attending_doctor_id::text AS bac_si_phu_trach,
       v.theo_doi_thu_thuat, v.theo_doi_sau_ngay, v.theo_doi_luc,
       s.full_name AS theo_doi_boi,
       tt.co_thu_thuat, tt.xong_luc, tt.nguoi_lam
  FROM public.visit v
  LEFT JOIN public.staff s ON s.id = v.theo_doi_boi
  LEFT JOIN LATERAL (
      SELECT count(*) > 0 AS co_thu_thuat,
             max(w.finished_at) FILTER (WHERE w.status = 'COMPLETED') AS xong_luc,
             array_agg(w.assigned_to::text) FILTER (WHERE w.assigned_to IS NOT NULL)
                 AS nguoi_lam
        FROM public.work_item w
       WHERE w.clinic_id = v.clinic_id AND w.visit_id = v.visit_id
         AND w.node_code = $3 AND w.status <> 'CANCELLED'
  ) tt ON TRUE
 WHERE v.clinic_id = $1::uuid AND v.visit_id = $2::uuid
"""


def han_goi(
    xong_luc: datetime | None, theo_doi: str | None, sau_ngay: int | None
) -> datetime | None:
    """Hạn gọi hỏi thăm. Chỉ có khi bác sĩ chọn CAN VÀ thủ thuật đã làm xong."""
    if theo_doi != "CAN" or xong_luc is None or not sau_ngay:
        return None
    return xong_luc + timedelta(days=sau_ngay)


def _dong(r: asyncpg.Record) -> dict[str, Any]:
    han = han_goi(r["xong_luc"], r["theo_doi_thu_thuat"], r["theo_doi_sau_ngay"])
    return {
        "visit_id": r["visit_id"],
        "co_thu_thuat": bool(r["co_thu_thuat"]),
        "thu_thuat_xong_luc": r["xong_luc"].isoformat() if r["xong_luc"] else None,
        "theo_doi": r["theo_doi_thu_thuat"],
        "sau_ngay": r["theo_doi_sau_ngay"],
        "han_goi": han.isoformat() if han else None,
        "quyet_boi": r["theo_doi_boi"],
        "quyet_luc": r["theo_doi_luc"].isoformat() if r["theo_doi_luc"] else None,
    }


class TheoDoiThuThuatService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def doc(self, *, identity: StaffIdentity, visit_id: str) -> dict[str, Any]:
        r = await self._pool.fetchrow(
            _DOC_SQL, identity.clinic_id, visit_id, NODE_THU_THUAT
        )
        if r is None:
            raise NotFoundError("Không tìm thấy lượt khám này.")
        return _dong(r)

    async def dat(
        self,
        *,
        identity: StaffIdentity,
        visit_id: str,
        theo_doi: str,
        sau_ngay: int | None,
    ) -> dict[str, Any]:
        if identity.role not in PHYSICIAN_ROLES:
            raise SafetyGateError("Chỉ bác sĩ quyết theo dõi sau thủ thuật.")
        if theo_doi not in LUA_CHON:
            raise ValidationError("Chọn: cần theo dõi hoặc không cần.")
        if theo_doi == "CAN":
            if sau_ngay is None or not 1 <= sau_ngay <= 365:
                raise ValidationError("Theo dõi sau bao nhiêu ngày (1–365)?")
        else:
            sau_ngay = None

        async with self._pool.acquire() as conn, conn.transaction():
            # Khoá dòng lượt khám riêng: câu đọc có LEFT JOIN + gộp nên không
            # gắn FOR UPDATE thẳng được.
            await conn.execute(
                "SELECT 1 FROM public.visit"
                " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid FOR UPDATE",
                identity.clinic_id,
                visit_id,
            )
            r = await conn.fetchrow(
                _DOC_SQL, identity.clinic_id, visit_id, NODE_THU_THUAT
            )
            if r is None:
                raise NotFoundError("Không tìm thấy lượt khám này.")
            if not r["co_thu_thuat"]:
                raise ValidationError("Lượt khám này không có chỉ định thủ thuật.")
            nguoi = {r["bac_si_phu_trach"], *(r["nguoi_lam"] or [])}
            if identity.staff_id not in nguoi:
                raise SafetyGateError(
                    "Chỉ bác sĩ phụ trách hoặc bác sĩ làm thủ thuật quyết việc này."
                )
            await conn.execute(
                """
                UPDATE public.visit
                   SET theo_doi_thu_thuat = $3, theo_doi_sau_ngay = $4,
                       theo_doi_boi = $5::uuid, theo_doi_luc = now(),
                       updated_at = now()
                 WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
                """,
                identity.clinic_id,
                visit_id,
                theo_doi,
                sau_ngay,
                identity.staff_id,
            )
            await record_event(
                conn,
                event_type="visit.theo_doi_thu_thuat",
                aggregate_type="visit",
                aggregate_id=visit_id,
                identity=identity,
                origin="api:theo-doi-thu-thuat",
                payload={
                    "theo_doi": theo_doi,
                    "sau_ngay": sau_ngay,
                    "truoc": r["theo_doi_thu_thuat"],
                },
            )
            moi = await conn.fetchrow(
                _DOC_SQL, identity.clinic_id, visit_id, NODE_THU_THUAT
            )
        assert moi is not None
        return _dong(moi)
