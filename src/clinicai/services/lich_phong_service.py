"""Lịch của phòng (Tuyền 27/09/2026 tối: "cấu trúc phòng liên quan đến lịch làm
việc, bản chất là 1 — gắn vào phòng nào thì làm việc ở phòng ấy").

Nhân sự của một phòng KHÔNG có bảng riêng: phòng → các vị trí làm việc
(`vi_tri_lam_viec.room_id`) → lịch (`work_roster.station` = mã vị trí). Màn Cấu
trúc phòng khám đọc lịch tuần của từng phòng ở đây; ghi thì đi thẳng các lệnh
lịch / vị trí sẵn có (`POST /roster/shifts`, `DELETE /roster/shifts/{id}`,
`/day-noi/vi-tri`) — một nguồn duy nhất, cùng dữ liệu với màn Lịch làm việc.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import asyncpg

from clinicai.api.identity import StaffIdentity
from clinicai.core.clock import now_vn
from clinicai.services.config_service import week_start_of


def doc_tuan(v: Any) -> date:
    """`YYYY-MM-DD` bất kỳ trong tuần → thứ Hai của tuần ấy. Rác / rỗng → tuần
    này (không ném — luật ngày giờ từ người dùng)."""
    try:
        d = date.fromisoformat(str(v).strip()[:10]) if v else None
    except ValueError:
        d = None
    return week_start_of(d or now_vn().date())


_VI_TRI_SQL = """
SELECT id::text AS id, code, ten, ten_ngan, nhom_nghe, room_id::text AS room_id
  FROM public.vi_tri_lam_viec
 WHERE clinic_id = $1::uuid AND is_active AND room_id IS NOT NULL
 ORDER BY sort, ten
"""

_CA_SQL = """
SELECT w.id::text AS id, w.station, w.work_date, w.shift,
       w.staff_id::text AS staff_id, w.staff_name, w.status
  FROM public.work_roster w
 WHERE w.clinic_id = $1::uuid AND w.work_date BETWEEN $2 AND $3
   AND w.status <> 'REJECTED'
 ORDER BY w.work_date, w.sort, w.staff_name
"""


class LichPhongService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def tuan(self, *, identity: StaffIdentity, tuan: Any) -> dict[str, Any]:
        dau = doc_tuan(tuan)
        cuoi = dau + timedelta(days=6)
        async with self._pool.acquire() as conn:
            vi_tri = await conn.fetch(_VI_TRI_SQL, identity.clinic_id)
            ca = await conn.fetch(_CA_SQL, identity.clinic_id, dau, cuoi)
        theo_ma: dict[str, list[dict[str, Any]]] = {}
        for c in ca:
            theo_ma.setdefault(c["station"], []).append(
                {
                    "id": c["id"],
                    "ngay": c["work_date"].isoformat(),
                    "ca": c["shift"],
                    "staff_id": c["staff_id"],
                    "ten": c["staff_name"],
                    "duyet": c["status"] == "APPROVED",
                }
            )
        phong: dict[str, list[dict[str, Any]]] = {}
        for v in vi_tri:
            phong.setdefault(v["room_id"], []).append(
                {
                    "id": v["id"],
                    "code": v["code"],
                    "ten": v["ten_ngan"] or v["ten"],
                    "nhom_nghe": v["nhom_nghe"],
                    "ca": theo_ma.get(v["code"], []),
                }
            )
        return {
            "tuan": dau.isoformat(),
            "ngay": [(dau + timedelta(days=i)).isoformat() for i in range(7)],
            "phong": phong,
        }
