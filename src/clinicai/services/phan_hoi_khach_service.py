"""Phản hồi / khiếu nại của khách — ghi nhận và vòng đời xử lý (DoD CSKH mục 3).

VÌ SAO KHÔNG NẰM TRONG SỔ TƯƠNG TÁC. Sổ tương tác là dòng chảy một chiều của
các lần chạm — ghi rồi thôi. Một khiếu nại là một VIỆC MỞ: nó có trạng thái, có
người xử lý, và ba tuần sau vẫn phải tìm lại được theo "cái nào chưa xong".
Nhồi hai thứ vào một bảng thì hoặc mọi cuộc gọi phải mang một trạng thái vô
nghĩa, hoặc khiếu nại không đóng được.
"""

from __future__ import annotations

from typing import Any

import asyncpg
import structlog

from clinicai.api.exceptions import NotFoundError, ValidationError
from clinicai.api.identity import StaffIdentity

logger = structlog.get_logger()

#: Khớp CHECK trong 20260809000007. KHEN cũng đáng ghi: nó nói khâu nào đang đúng.
LOAI_HOP_LE = frozenset({"KHEN", "GOP_Y", "KHIEU_NAI"})


class PhanHoiKhachService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def ghi(
        self,
        *,
        identity: StaffIdentity,
        clinic_patient_id: str,
        loai: str,
        noi_dung: str,
    ) -> dict[str, Any]:
        """Ghi một phản hồi mới. Người tiếp nhận lấy từ phiên, không từ client."""
        if loai not in LOAI_HOP_LE:
            raise ValidationError(f"Loại phản hồi không hợp lệ: {loai!r}.")
        noi_dung = (noi_dung or "").strip()
        if not noi_dung:
            raise ValidationError("Ghi rõ khách nói gì.")

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                ok = await conn.fetchval(
                    "SELECT 1 FROM public.patient "
                    " WHERE clinic_patient_id = $1::uuid AND clinic_id = $2::uuid",
                    clinic_patient_id,
                    identity.clinic_id,
                )
                if not ok:
                    raise NotFoundError("Không tìm thấy khách hàng này.")
                row_id = await conn.fetchval(
                    """
                    INSERT INTO public.phan_hoi_khach
                        (clinic_id, clinic_patient_id, loai, noi_dung,
                         nguoi_tiep_nhan_staff_id)
                    VALUES ($1::uuid, $2::uuid, $3, $4, $5::uuid)
                    RETURNING id::text
                    """,
                    identity.clinic_id,
                    clinic_patient_id,
                    loai,
                    noi_dung,
                    identity.staff_id,
                )
                await conn.execute(
                    """
                    INSERT INTO public.event_log
                        (clinic_id, event_type, aggregate_type, aggregate_id,
                         payload, source, occurred_at)
                    VALUES ($1::uuid, 'cskh.phan_hoi_ghi', 'phan_hoi_khach',
                            $2::uuid,
                            jsonb_build_object('loai', $3::text,
                                               'by_staff_id', $4::text),
                            'cskh.customers', now())
                    """,
                    identity.clinic_id,
                    row_id,
                    loai,
                    identity.staff_id,
                )
        logger.info("phan_hoi_ghi", loai=loai, by_staff_id=identity.staff_id)
        return {"ok": True, "id": row_id}

    async def cap_nhat(
        self,
        *,
        identity: StaffIdentity,
        phan_hoi_id: str,
        trang_thai: str,
        huong_xu_ly: str | None = None,
    ) -> dict[str, Any]:
        """Chuyển trạng thái xử lý. Đóng thì phải nói đã xử lý ra sao."""
        if trang_thai not in ("MOI", "DANG_XU_LY", "DA_XU_LY"):
            raise ValidationError(f"Trạng thái không hợp lệ: {trang_thai!r}.")
        huong = (huong_xu_ly or "").strip() or None
        if trang_thai == "DA_XU_LY" and not huong:
            # "Đã xử lý" mà không nói xử lý ra sao thì ba tuần sau khách gọi
            # lại và không ai biết lần trước đã hứa gì.
            raise ValidationError("Đóng phản hồi thì phải ghi đã xử lý thế nào.")

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    """
                    UPDATE public.phan_hoi_khach
                       SET trang_thai = $1,
                           huong_xu_ly = coalesce($2, huong_xu_ly),
                           xu_ly_boi_staff_id = CASE WHEN $1 = 'DA_XU_LY'
                               THEN $3::uuid ELSE xu_ly_boi_staff_id END,
                           xu_ly_luc = CASE WHEN $1 = 'DA_XU_LY'
                               THEN now() ELSE xu_ly_luc END
                     WHERE id = $4::uuid AND clinic_id = $5::uuid
                    RETURNING id::text
                    """,
                    trang_thai,
                    huong,
                    identity.staff_id,
                    phan_hoi_id,
                    identity.clinic_id,
                )
                if row is None:
                    raise NotFoundError("Không tìm thấy phản hồi này.")
                await conn.execute(
                    """
                    INSERT INTO public.event_log
                        (clinic_id, event_type, aggregate_type, aggregate_id,
                         payload, source, occurred_at)
                    VALUES ($1::uuid, 'cskh.phan_hoi_xu_ly', 'phan_hoi_khach',
                            $2::uuid,
                            jsonb_build_object('trang_thai', $3::text,
                                               'by_staff_id', $4::text),
                            'cskh.customers', now())
                    """,
                    identity.clinic_id,
                    phan_hoi_id,
                    trang_thai,
                    identity.staff_id,
                )
        return {"ok": True}
