"""Khối BÁN VẬT TƯ nghe chỉ định đổi trạng thái (31/10/2026).

Đầu dò đi theo chỉ định: chỉ định bắt đầu làm → trừ dù chưa thu; xếp hay đổi phòng
→ trừ đúng phòng ấy (quầy thu trước, khối Hành trình xếp phòng sau); bỏ / không làm
→ số về; khôi phục → trừ lại.

Không sửa các nơi phát: mỗi trạng thái có nhiều đường ghi, bên nhận chỉ đọc trạng
thái HIỆN TẠI rồi đồng bộ, nên sự kiện tới trễ hay giao hai lần vẫn ra một kết quả.
"""

from __future__ import annotations

import asyncpg

from clinicai.events.catalogue import VAT_TU_BAN
from clinicai.events.worker import SuKienDaNhan, dang_ky
from clinicai.services.vat_tu_ban_service import NguoiGhi, dong_bo_ban_vat_tu

_LY_DO = {
    "service_order.cancelled": "Bỏ chỉ định",
    "service_order.restored": "Khôi phục chỉ định",
    "service.not_performed": "Dịch vụ không làm",
    "service.routed": "Chỉ định đổi phòng",
    "service.room_transferred": "Chỉ định đổi phòng",
    "service.start_cancelled": "Huỷ bắt đầu dịch vụ",
}


async def dong_bo_theo_chi_dinh(
    conn: asyncpg.Connection, su_kien: SuKienDaNhan
) -> None:
    if su_kien.la_phat_lai:
        return
    visit_id = su_kien.payload.get("visit_id")
    if not visit_id:
        return
    # Cùng thứ tự khoá với lần thu: lượt trước, dòng bán sau.
    if not await conn.fetchval(
        "SELECT 1 FROM public.visit WHERE clinic_id = $1::uuid AND visit_id = $2::uuid"
        " FOR UPDATE",
        su_kien.clinic_id,
        str(visit_id),
    ):
        return
    goc = _LY_DO.get(su_kien.event_type)
    them = su_kien.payload.get("ly_do") if goc == "Bỏ chỉ định" else None
    await dong_bo_ban_vat_tu(
        conn,
        NguoiGhi(su_kien.clinic_id, "", su_kien.actor_staff_id or ""),
        str(visit_id),
        ly_do=f"{goc}: {them}" if them else goc,
    )


dang_ky(VAT_TU_BAN, dong_bo_theo_chi_dinh)
