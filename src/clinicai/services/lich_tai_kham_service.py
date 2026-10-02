"""Bác sĩ đặt LỊCH HẸN THẬT từ ô "Ngày tái khám" của phiếu (Tuyền 02/10/2026).

Trước đây ô ngày chỉ sinh việc gọi cho CSKH (`hen_tai_kham_service`) — không
có giờ nên không lên lịch hẹn. Nay dưới ô ngày có khung chọn bác sĩ + giờ của
ĐÚNG ngày ấy (cùng nguồn còn chỗ với màn Đặt lịch). Ngày chưa có lịch trực thì
đặt vào hàng "Chưa phân bác sĩ" — lịch rơi vào màn Chờ xếp bác sĩ, CSKH/quản lý
phân khi có lịch trực thật.

* Việc gọi của CSKH GIỮ NGUYÊN (Tuyền: "đang đúng chuẩn rồi"): lịch đặt từ phiếu
  mang `hen_tu_visit_id`, trigger và `dong_bo` không đóng việc "đã có lịch".
* Một lượt = MỘT lịch tái khám còn sống (chỉ mục duy nhất, mig 20261003720000).
  Đổi giờ = huỷ trên phiếu rồi đặt lại — mọi bước hoàn tác được.
* Mọi luật đặt lịch (sức chứa, trùng giờ, ca trực, ngoài giờ) đi qua ĐÚNG
  `BookingService.create` — không có đường ghi thứ hai.
* Quyền: người ghi được phiếu của lượt (cùng cổng `kiem_quyen_core`). Khách,
  dịch vụ, lịch trước đọc từ LƯỢT ở máy chủ — trình duyệt không gửi.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import asyncpg

from clinicai.api.exceptions import ConflictError, NotFoundError, ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.services.booking_service import BookingService, resolve_action
from clinicai.services.hen_tai_kham_service import LICH_SONG, doc_lich_tu_luot
from clinicai.services.phieu_kham_service import kiem_quyen_core

#: Ghi chú trên lịch — CSKH / lễ tân nhìn là biết lịch do bác sĩ hẹn.
GHI_CHU_LICH = "Bác sĩ hẹn tái khám từ phiếu khám"
#: Lý do huỷ (mã KHAC kèm chữ) khi bác sĩ huỷ để đặt lại.
LY_DO_HUY = "Bác sĩ đổi hẹn tái khám trên phiếu khám"


async def _luot(
    conn: asyncpg.Connection, clinic_id: str, visit_id: str
) -> asyncpg.Record:
    v = await conn.fetchrow(
        """
        SELECT v.clinic_patient_id::text AS khach,
               v.appointment_id::text AS lich_truoc,
               coalesce(v.service_type_id, a.service_type_id)::text AS dich_vu_id,
               st.name AS dich_vu
          FROM visit v
          LEFT JOIN appointment a
            ON a.id = v.appointment_id AND a.clinic_id = v.clinic_id
          LEFT JOIN service_type st
            ON st.id = coalesce(v.service_type_id, a.service_type_id)
         WHERE v.clinic_id = $1::uuid AND v.visit_id = $2::uuid
        """,
        clinic_id,
        visit_id,
    )
    if v is None:
        raise NotFoundError("Không tìm thấy lượt khám.")
    return v


class LichTaiKhamService:
    """Đọc / đặt / huỷ lịch tái khám từ phiếu của một lượt."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def doc(self, *, visit_id: str, identity: StaffIdentity) -> dict[str, Any]:
        async with self._pool.acquire() as conn:
            await kiem_quyen_core(conn, identity, "doc_phieu")
            v = await _luot(conn, identity.clinic_id, visit_id)
            return {
                "lich": await doc_lich_tu_luot(conn, identity.clinic_id, visit_id),
                "dich_vu": v["dich_vu"],
            }

    async def dat(
        self,
        *,
        visit_id: str,
        identity: StaffIdentity,
        slot_start: datetime,
        slot_end: datetime,
        doctor_id: str | None,
    ) -> dict[str, Any]:
        async with self._pool.acquire() as conn:
            await kiem_quyen_core(conn, identity, "ghi_phieu")
            v = await _luot(conn, identity.clinic_id, visit_id)
            co = await doc_lich_tu_luot(conn, identity.clinic_id, visit_id)
        if co is not None:
            raise ConflictError(
                f"Lượt này đã có lịch tái khám {co['gio']} ngày {co['ngay']} — "
                "huỷ lịch đó trên phiếu rồi đặt lại."
            )
        if not v["dich_vu_id"]:
            raise ValidationError("Lượt khám chưa có loại khám để đặt lịch tái khám.")
        try:
            ket = await BookingService(self._pool).create(
                clinic_patient_id=v["khach"],
                service_type_id=v["dich_vu_id"],
                location_id=None,
                slot_start=slot_start,
                slot_end=slot_end,
                identity=identity,
                doctor_id=doctor_id,
                patient_kind="RETURN",
                notes=GHI_CHU_LICH,
                lich_truoc_id=v["lich_truoc"],
                hen_tu_visit_id=visit_id,
            )
        except asyncpg.UniqueViolationError as exc:
            # Hai cú bấm / hai tab cùng đặt — chỉ mục duy nhất giữ một.
            raise ConflictError(
                "Lượt này vừa được đặt lịch tái khám — tải lại để xem."
            ) from exc
        async with self._pool.acquire() as conn:
            lich = await doc_lich_tu_luot(conn, identity.clinic_id, visit_id)
        return {**ket, "lich": lich}

    async def huy(
        self, *, visit_id: str, appointment_id: str, identity: StaffIdentity
    ) -> dict[str, Any]:
        """Huỷ lịch CHÍNH phiếu này đã đặt (để đặt lại). Không đụng lịch khác."""
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                await kiem_quyen_core(conn, identity, "ghi_phieu")
                status = await conn.fetchval(
                    "SELECT status FROM appointment"
                    " WHERE id = $1::uuid AND clinic_id = $2::uuid"
                    "   AND hen_tu_visit_id = $3::uuid FOR UPDATE",
                    appointment_id,
                    identity.clinic_id,
                    visit_id,
                )
                if status is None:
                    raise NotFoundError("Không tìm thấy lịch tái khám của lượt này.")
                if status == "CHECKED_IN":
                    raise ConflictError(
                        "Khách đã tới theo lịch này — không huỷ ở phiếu."
                    )
                # Cùng một đường luật huỷ với màn Đặt lịch (nhật ký, sự kiện,
                # thả chỗ). Cổng quyền đã gác ở trên: người ghi phiếu của lượt
                # huỷ lịch chính phiếu ấy đặt.
                kq = await BookingService(self._pool)._hanh_dong_trong_gd(
                    conn,
                    appointment_id=appointment_id,
                    action="cancel",
                    transition=resolve_action("cancel"),
                    identity=identity,
                    cancellation_reason=LY_DO_HUY,
                    ly_do_huy_ma="KHAC",
                    quyen_da_kiem=True,
                )
        return {"status": kq.new_status, "lich": None}


__all__ = [
    "GHI_CHU_LICH",
    "LICH_SONG",
    "LY_DO_HUY",
    "LichTaiKhamService",
    "doc_lich_tu_luot",
]
