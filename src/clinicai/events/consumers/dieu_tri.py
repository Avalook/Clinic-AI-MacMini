"""Lịch ĐIỀU TRỊ vào hàng → chỉ định sẵn đúng dịch vụ đã đặt (Tuyền 07/10/2026, T1).

    visit.routed (khối Hành trình đã mở phiên khám / hàng chờ của lượt)
        → lượt có loại khám nhóm ĐIỀU TRỊ mà chưa có chỉ định dịch vụ ấy
          → một `service_order` bình thường gắn phiên khám của lượt.

Bên nghe MỚI — không sửa nơi phát (`hanh_trinh`). Nghe `visit.routed` thay vì
`visit.checked_in` vì chỉ định phải gắn một phiên khám, mà phiên do Hành trình
mở khi xếp hàng. Không xếp phòng, không thu phí khám: khách hiện ở hàng bác sĩ
chính (tuỳ chọn) và ở danh sách "Sắp đến" của phòng làm được.
Chạy lại / tới hai lần vẫn một chỉ định (`sinh_chi_dinh_dieu_tri` khoá lượt).
"""

from __future__ import annotations

import asyncpg

from clinicai.events.catalogue import DIEU_TRI_SINH_CHI_DINH
from clinicai.events.worker import SuKienDaNhan, dang_ky
from clinicai.services.ho_so_dich_vu import sinh_chi_dinh_dieu_tri


async def sinh_chi_dinh(conn: asyncpg.Connection, su_kien: SuKienDaNhan) -> None:
    if su_kien.la_phat_lai:
        return
    visit_id = su_kien.payload.get("visit_id")
    if not visit_id:
        return
    await sinh_chi_dinh_dieu_tri(
        conn,
        clinic_id=su_kien.clinic_id,
        visit_id=str(visit_id),
        nguoi_bam=su_kien.actor_staff_id,
        causation_id=su_kien.event_id,
    )


dang_ky(DIEU_TRI_SINH_CHI_DINH, sinh_chi_dinh)

__all__ = ["sinh_chi_dinh"]
