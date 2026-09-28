"""Chọn DỊCH VỤ KHÁM theo mã KiotViet cho một lượt (Tuyền 28/09/2026).

"Tiền phát sinh khi bác sĩ khám cho họ là khám cái gì … thêm khu vực tick dưới
dòng Bác sĩ tư vấn ghi để chọn loại dịch vụ chính xác của dịch vụ khám, lúc đó
tiền mới tính, mình không còn bịa giá nữa."

* Danh sách chọn được = `loai_kham_phi` của loại khám của lượt (migration
  20260928000100, nguồn file KiotViet).
* Tick lưu ở `luot_phi_kham`; tiền khám = các dòng còn sống
  (`bill_service.dong_kham_theo_chon`).
* Ai tick: người khám (Bàn khám / tư vấn / ghi bệnh án) hoặc quầy thu — hỏi
  QUYỀN, không hỏi vai. Tiền khám của lượt đã thu (còn hiệu lực) thì khoá: đổi
  lựa chọn phải huỷ phiếu trước.
* Loại khám ĐI THẲNG PHÒNG (Sàn chậu, Thủ thuật) không có tiền khám — danh sách
  ấy là dịch vụ để quầy THÊM chỉ định, không tick ở đây.
"""

from __future__ import annotations

from typing import Any

import asyncpg

from clinicai.api.exceptions import ConflictError, ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.core.exceptions import SafetyGateError
from clinicai.permissions.can import can
from clinicai.services.audit import record_event
from clinicai.services.bill_service import _DA_PHU
from clinicai.services.lenh_kham_core import khoa_luot
from clinicai.services.lenh_kham_core import ma_uuid as _uuid

#: Có MỘT trong các quyền này thì tick được: người khám, người ghi bệnh án,
#: người tư vấn, quầy thu tiền dịch vụ.
QUYEN_TICK = (
    "clinical.consult.perform",
    "clinical.record.write",
    "clinical.intake.perform",
    "payment.service.collect",
)

_LOAI_KHAM_SQL = """
SELECT st.id::text AS st_id, st.name, coalesce(st.di_thang_phong, false) AS di_thang
  FROM public.visit vi
  LEFT JOIN public.appointment a
    ON a.id = vi.appointment_id AND a.clinic_id = vi.clinic_id
  JOIN public.service_type st
    ON st.id = coalesce(vi.service_type_id, a.service_type_id)
 WHERE vi.clinic_id = $1::uuid AND vi.visit_id = $2::uuid
"""

_LUA_CHON_SQL = """
SELECT sp.id::text AS id, sp.ma_kiotviet, sp.name, sp.unit_price
  FROM public.loai_kham_phi l
  JOIN public.service_price sp
    ON sp.id = l.service_price_id AND sp.clinic_id = l.clinic_id AND sp.active
 WHERE l.clinic_id = $1::uuid AND l.service_type_id = $2::uuid
 ORDER BY l.thu_tu, sp.name
"""


async def _co_quyen_tick(conn: asyncpg.Connection, identity: StaffIdentity) -> bool:
    for q in QUYEN_TICK:
        if await can(conn, identity, q):
            return True
    return False


async def _doc(
    conn: asyncpg.Connection, clinic_id: str, visit_id: str
) -> dict[str, Any]:
    loai = await conn.fetchrow(_LOAI_KHAM_SQL, clinic_id, visit_id)
    lua_chon = await conn.fetch(_LUA_CHON_SQL, clinic_id, loai["st_id"]) if loai else []
    da_chon = [
        r["id"]
        for r in await conn.fetch(
            "SELECT service_price_id::text AS id FROM public.luot_phi_kham"
            " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid AND bo_luc IS NULL"
            " ORDER BY chon_luc, id",
            clinic_id,
            visit_id,
        )
    ]
    da_thu = bool(
        await conn.fetchval(
            "SELECT " + _DA_PHU.format(loai="'exam'", nguon="$2"),
            clinic_id,
            f"exam-{visit_id}",
        )
    )
    return {
        "loai_kham": loai["name"] if loai else None,
        "di_thang_phong": bool(loai["di_thang"]) if loai else False,
        "lua_chon": [
            {
                "id": r["id"],
                "ma_kiotviet": r["ma_kiotviet"],
                "ten": r["name"],
                "gia": int(r["unit_price"]) if r["unit_price"] is not None else None,
            }
            for r in lua_chon
        ],
        "da_chon": da_chon,
        # Tiền khám đã thu → khoá (đổi phải huỷ phiếu trước).
        "khoa": da_thu,
    }


class PhiKhamService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def doc(self, *, visit_id: str, identity: StaffIdentity) -> dict[str, Any]:
        vid = _uuid(visit_id, "Mã lượt khám không hợp lệ.")
        async with self._pool.acquire() as conn:
            kq = await _doc(conn, identity.clinic_id, vid)
            kq["duoc_tick"] = await _co_quyen_tick(conn, identity) and not kq["khoa"]
            return kq

    async def chon(
        self, *, visit_id: str, ids: list[str], identity: StaffIdentity
    ) -> dict[str, Any]:
        """Đặt TẬP dịch vụ khám của lượt = `ids` (bỏ tick = đóng dấu, không xoá)."""
        vid = _uuid(visit_id, "Mã lượt khám không hợp lệ.")
        muon = list(dict.fromkeys(str(i) for i in ids))
        cid = identity.clinic_id
        async with self._pool.acquire() as conn, conn.transaction():
            if not await _co_quyen_tick(conn, identity):
                raise SafetyGateError("Bạn chưa được cấp quyền chọn dịch vụ khám.")
            await khoa_luot(conn, cid, vid, cho_phep_da_ky=True)
            hien = await _doc(conn, cid, vid)
            if hien["di_thang_phong"]:
                raise ValidationError(
                    "Loại khám đi thẳng phòng không có tiền khám — thêm dịch vụ ở quầy."
                )
            if hien["khoa"]:
                raise ConflictError(
                    "Tiền khám của lượt này đã thu — huỷ phiếu thu trước khi đổi "
                    "dịch vụ khám."
                )
            hop_le = {x["id"] for x in hien["lua_chon"]}
            la = [i for i in muon if i not in hop_le]
            if la:
                raise ValidationError(
                    "Có dịch vụ không thuộc danh sách khám của loại khám này."
                )
            cu = set(hien["da_chon"])
            bo = sorted(cu - set(muon))
            them = [i for i in muon if i not in cu]
            if bo:
                await conn.execute(
                    "UPDATE public.luot_phi_kham SET bo_luc = now(), bo_boi = $4::uuid"
                    " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid"
                    " AND service_price_id = ANY($3::uuid[]) AND bo_luc IS NULL",
                    cid,
                    vid,
                    bo,
                    identity.staff_id,
                )
            for i in them:
                await conn.execute(
                    "INSERT INTO public.luot_phi_kham"
                    " (clinic_id, visit_id, service_price_id, chon_boi)"
                    " VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid)",
                    cid,
                    vid,
                    i,
                    identity.staff_id,
                )
            if bo or them:
                await record_event(
                    conn,
                    event_type="visit.exam_fee_selected",
                    aggregate_type="visit",
                    aggregate_id=vid,
                    identity=identity,
                    origin="api:phi-kham",
                    payload={"them": them, "bo": bo},
                    correlation_id=vid,
                )
            kq = await _doc(conn, cid, vid)
        kq["duoc_tick"] = True
        return kq


__all__ = ["QUYEN_TICK", "PhiKhamService"]
