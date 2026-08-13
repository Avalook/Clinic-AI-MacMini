"""Luật "dịch vụ X + khách mới → bắt buộc bác sĩ Y".

Đọc/ghi bảng `luat_bac_si_bat_buoc`. Thi hành thì nằm ở `booking_service` —
đúng lúc CSKH chọn bác sĩ, không phải lúc chuyển phòng.

VÌ SAO LÀ MỘT SERVICE RIÊNG. `booking_override_service` nói về SỐ CHỖ mỗi khung
giờ; luật này nói về AI ĐƯỢC KHÁM. Hai câu hỏi khác nhau, hai bảng khác nhau,
và gộp chúng vào một file nghĩa là mỗi lần sửa cái này phải đọc lại cái kia.
"""

from __future__ import annotations

from typing import Any

import asyncpg
import structlog

from clinicai.api.exceptions import ConflictError, NotFoundError, ValidationError
from clinicai.api.identity import StaffIdentity

logger = structlog.get_logger()

#: Ba cách tính "khách mới", khớp CHECK trong 20260808000003.
CACH_TINH_HOP_LE = frozenset({"CHUA_TUNG", "DOT_MOI", "QUA_N_THANG"})


class LuatBacSiService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def danh_sach(self, *, identity: StaffIdentity) -> list[dict[str, Any]]:
        """Mọi luật của phòng khám, kèm tên dịch vụ và tên bác sĩ.

        Trả cả luật ĐANG TẮT: một luật tắt vẫn là một quyết định, và giấu nó đi
        thì người sau sẽ tạo lại luật ấy rồi ngạc nhiên vì trùng.
        """
        rows = await self._pool.fetch(
            """
            SELECT l.id::text,
                   l.service_type_id::text,
                   st.name  AS ten_dich_vu,
                   st.code  AS ma_dich_vu,
                   l.required_staff_id::text,
                   s.full_name AS ten_bac_si,
                   l.cach_tinh,
                   l.so_thang,
                   l.chan_han,
                   l.is_active,
                   l.ghi_chu
              FROM public.luat_bac_si_bat_buoc l
              JOIN public.service_type st ON st.id = l.service_type_id
              JOIN public.staff s         ON s.id = l.required_staff_id
             WHERE l.clinic_id = $1::uuid
             ORDER BY st.name
            """,
            identity.clinic_id,
        )
        return [dict(r) for r in rows]

    async def luu(
        self,
        *,
        identity: StaffIdentity,
        service_type_id: str,
        required_staff_id: str,
        cach_tinh: str = "DOT_MOI",
        so_thang: int | None = None,
        chan_han: bool = True,
        is_active: bool = True,
        ghi_chu: str | None = None,
    ) -> dict[str, Any]:
        """Đặt (hoặc sửa) luật của MỘT dịch vụ. Mỗi dịch vụ chỉ một luật."""
        if cach_tinh not in CACH_TINH_HOP_LE:
            raise ValidationError(f"Cách tính không hợp lệ: {cach_tinh!r}.")
        if cach_tinh == "QUA_N_THANG":
            if so_thang is None or not (1 <= so_thang <= 120):
                raise ValidationError(
                    "Chọn 'quá N tháng' thì phải nhập số tháng từ 1 đến 120."
                )
        else:
            # Số tháng của một cách tính không dùng tới nó là dữ liệu sẽ gây
            # hiểu nhầm khi ai đó đọc bảng: đọc thấy 12 mà luật lại không xét
            # thời gian.
            so_thang = None

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                dv = await conn.fetchrow(
                    "SELECT id, name FROM public.service_type "
                    " WHERE id = $1::uuid AND clinic_id = $2::uuid",
                    service_type_id,
                    identity.clinic_id,
                )
                if dv is None:
                    raise NotFoundError("Không tìm thấy dịch vụ này.")

                # Bác sĩ phải thuộc phòng khám VÀ đang làm việc. Một luật trỏ
                # vào người đã nghỉ sẽ chặn mọi khách mới của dịch vụ đó mà
                # không ai chuyển sang được ai.
                bs = await conn.fetchrow(
                    """
                    SELECT s.id, s.full_name
                      FROM public.staff s
                      JOIN public.clinic_membership m
                        ON m.staff_id = s.id AND m.is_active
                     WHERE s.id = $1::uuid
                       AND m.clinic_id = $2::uuid
                       AND s.is_active
                       AND s.primary_department IN ('DOCTOR', 'ULTRASOUND_DOCTOR')
                    """,
                    required_staff_id,
                    identity.clinic_id,
                )
                if bs is None:
                    raise ValidationError(
                        "Người được chọn không phải bác sĩ đang làm việc "
                        "ở phòng khám này."
                    )

                row = await conn.fetchrow(
                    """
                    INSERT INTO public.luat_bac_si_bat_buoc
                        (clinic_id, service_type_id, required_staff_id,
                         cach_tinh, so_thang, chan_han, is_active, ghi_chu)
                    VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $5, $6, $7, $8)
                    ON CONFLICT (clinic_id, service_type_id) DO UPDATE
                        SET required_staff_id = EXCLUDED.required_staff_id,
                            cach_tinh         = EXCLUDED.cach_tinh,
                            so_thang          = EXCLUDED.so_thang,
                            chan_han          = EXCLUDED.chan_han,
                            is_active         = EXCLUDED.is_active,
                            ghi_chu           = EXCLUDED.ghi_chu,
                            updated_at        = now()
                    RETURNING id::text
                    """,
                    identity.clinic_id,
                    service_type_id,
                    required_staff_id,
                    cach_tinh,
                    so_thang,
                    chan_han,
                    is_active,
                    (ghi_chu or "").strip() or None,
                )
                await conn.execute(
                    """
                    INSERT INTO public.event_log
                        (clinic_id, event_type, aggregate_type, aggregate_id,
                         payload, source, occurred_at)
                    VALUES ($1::uuid, 'booking.doctor_rule_saved',
                            'luat_bac_si_bat_buoc', $2::uuid,
                            jsonb_build_object(
                              'dich_vu', $3::text, 'bac_si', $4::text,
                              'cach_tinh', $5::text, 'chan_han', $6::boolean,
                              'is_active', $7::boolean, 'by_staff_id', $8::text),
                            'config.booking_rule', now())
                    """,
                    identity.clinic_id,
                    row["id"],
                    dv["name"],
                    bs["full_name"],
                    cach_tinh,
                    chan_han,
                    is_active,
                    identity.staff_id,
                )

        logger.info(
            "doctor_rule_saved",
            service=dv["name"],
            doctor=bs["full_name"],
            cach_tinh=cach_tinh,
            by_staff_id=identity.staff_id,
        )
        return {"ok": True, "id": row["id"]}

    async def xoa(self, *, identity: StaffIdentity, luat_id: str) -> dict[str, Any]:
        """Gỡ hẳn một luật.

        Xoá được, không phải chỉ tắt: một luật khai nhầm dịch vụ thì để lại chỉ
        làm rối bảng. Muốn tạm dừng thì dùng `is_active`.
        """
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "DELETE FROM public.luat_bac_si_bat_buoc "
                " WHERE id = $1::uuid AND clinic_id = $2::uuid "
                "RETURNING service_type_id::text",
                luat_id,
                identity.clinic_id,
            )
        if row is None:
            raise NotFoundError("Không tìm thấy luật này.")
        return {"ok": True}

    async def xem_thu(
        self,
        *,
        identity: StaffIdentity,
        service_type_id: str,
        cach_tinh: str,
        so_thang: int | None,
    ) -> dict[str, Any]:
        """Với cách tính này thì bao nhiêu khách hiện có bị coi là "mới"?

        Ba cách tính cho ba con số khác nhau trên cùng một tập bệnh nhân, và
        không có đáp án đúng phổ quát — nên quản lý cần THẤY hậu quả trước khi
        lưu, thay vì lưu rồi chờ khách phàn nàn.
        """
        if cach_tinh not in CACH_TINH_HOP_LE:
            raise ValidationError(f"Cách tính không hợp lệ: {cach_tinh!r}.")
        row = await self._pool.fetchrow(
            """
            SELECT count(*) FILTER (
                     WHERE public.la_khach_moi_cua_dich_vu(
                             $1::uuid, p.clinic_patient_id, $2::uuid, $3, $4)
                   ) AS khach_moi,
                   count(*) AS tong
              FROM public.patient p
             WHERE p.clinic_id = $1::uuid
            """,
            identity.clinic_id,
            service_type_id,
            cach_tinh,
            so_thang,
        )
        if row is None:
            raise ConflictError("Không đếm được.")
        return {"khach_moi": row["khach_moi"], "tong": row["tong"]}
