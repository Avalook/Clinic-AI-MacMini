"""Nhân sự của từng phòng (Tuyền 27/09/2026 — màn Cấu trúc phòng khám).

"Người làm ở phòng X" = người có lego **Phòng dịch vụ** (`MAN["phong"]`) mà khối
chạy theo phòng (`khoi_theo_phong`) được cấp ở phạm vi ROOM = X. Phạm vi CLINIC
= làm được MỌI phòng. Không có bảng thứ hai: đọc thẳng `v_quyen_hieu_luc`, ghi
bằng `PermissionService.doi_lego` — cùng một cửa với màn Phân quyền.

Luật thuần (`phong_sau_khi_doi`) tách riêng để test không cần database.
"""

from __future__ import annotations

from typing import Any

import asyncpg

from clinicai.api.exceptions import ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.permissions.catalogue import MAN
from clinicai.services.permission_service import PermissionService

LEGO = "phong"


def _xep(d: dict[str, str]) -> list[dict[str, str]]:
    return [
        {"staff_id": k, "full_name": v}
        for k, v in sorted(d.items(), key=lambda x: x[1])
    ]


def khoi_phong() -> str:
    k = MAN[LEGO].khoi_theo_phong
    assert k, "lego Phòng dịch vụ phải có khoi_theo_phong"
    return k


def phong_sau_khi_doi(
    *, moi_phong: bool, dang_co: set[str], room_id: str, them: bool
) -> tuple[str, list[str]]:
    """Trả (việc, danh sách phòng mới). Việc: "giu" | "doi" | "tat".

    * Người đang làm MỌI phòng: thêm là thừa ("giu"); bớt một phòng thì bị chặn
      — thu hẹp "mọi phòng" phải làm ở màn Phân quyền, không lặng lẽ ở đây.
    * Bớt phòng cuối cùng = tắt lego (danh sách rỗng ở `doi_lego` nghĩa là
      MỌI phòng — gửi rỗng sẽ MỞ RỘNG quyền thay vì thu).
    """
    if moi_phong:
        if them:
            return "giu", []
        raise ValidationError(
            "Người này đang làm được MỌI phòng — thu hẹp ở màn Phân quyền."
        )
    moi = set(dang_co)
    if them:
        moi.add(room_id)
    else:
        moi.discard(room_id)
    if moi == dang_co:
        return "giu", sorted(moi)
    return ("doi", sorted(moi)) if moi else ("tat", [])


_SQL = """
SELECT q.staff_id::text AS staff_id, q.scope_type, q.scope_id::text AS scope_id,
       s.full_name
  FROM public.v_quyen_hieu_luc q
  JOIN public.staff s ON s.id = q.staff_id
 WHERE q.clinic_id = $1::uuid AND q.work_pack = $2
   AND coalesce(s.is_active, TRUE)
"""


class NhanSuPhongService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def _cap(self, clinic_id: str) -> list[asyncpg.Record]:
        async with self._pool.acquire() as conn:
            return list(await conn.fetch(_SQL, clinic_id, khoi_phong()))

    async def danh_sach(self, *, identity: StaffIdentity) -> dict[str, Any]:
        """`{phong: {room_id: [{staff_id, full_name}]}, moi_phong: [...]}`."""
        phong: dict[str, dict[str, str]] = {}
        moi: dict[str, str] = {}
        for r in await self._cap(identity.clinic_id):
            if r["scope_type"] == "ROOM" and r["scope_id"]:
                phong.setdefault(r["scope_id"], {})[r["staff_id"]] = r["full_name"]
            elif r["scope_type"] == "CLINIC":
                moi[r["staff_id"]] = r["full_name"]
        return {
            "phong": {rid: _xep(ds) for rid, ds in phong.items()},
            "moi_phong": _xep(moi),
        }

    async def doi(
        self, *, identity: StaffIdentity, staff_id: str, room_id: str, them: bool
    ) -> dict[str, Any]:
        cua_nguoi = [
            r for r in await self._cap(identity.clinic_id) if r["staff_id"] == staff_id
        ]
        moi_phong = any(r["scope_type"] == "CLINIC" for r in cua_nguoi)
        dang_co = {
            r["scope_id"]
            for r in cua_nguoi
            if r["scope_type"] == "ROOM" and r["scope_id"]
        }
        viec, ds = phong_sau_khi_doi(
            moi_phong=moi_phong, dang_co=dang_co, room_id=room_id, them=them
        )
        if viec == "giu":
            return {"ok": True, "doi": False}
        await PermissionService(self._pool).doi_lego(
            staff_id=staff_id,
            ma=LEGO,
            bat=viec == "doi",
            identity=identity,
            phong_ids=ds or None,
        )
        return {"ok": True, "doi": True, "phong_ids": ds}
