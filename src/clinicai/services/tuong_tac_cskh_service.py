"""Sổ tương tác CSKH — ghi lại từng lần chạm tới khách, và đọc lại nó.

VÌ SAO CÓ FILE NÀY. Nút "📞 Gọi nhắc hẹn" trên màn Quản lý khách hàng là một
thẻ `<a href="tel:…">`: nó quay số rồi thôi. Gọi xong không ai biết đã gọi, gọi
lần hai không ai biết là lần hai, và ba cột "Tương tác gần nhất / Bước tiếp
theo / Hạn xử lý" hiện "—" cho mọi khách.

Sổ này CHỈ THÊM. Không có hàm sửa, không có hàm xoá: một cuộc gọi đã xảy ra thì
đã xảy ra, và bản ghi sai được sửa bằng cách ghi thêm một dòng nói rõ, không
phải bằng cách viết lại quá khứ.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import asyncpg
import structlog

from clinicai.api.exceptions import NotFoundError, ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.core.clock import CLINIC_TZ as GIO_VN

logger = structlog.get_logger()

#: Loại việc — khớp CHECK trong 20260809000003.
LOAI_HOP_LE = frozenset(
    {
        "XAC_NHAN_LICH",
        "NHAC_HEN",
        "CHECK_XN",
        "TRA_KQ",
        "HOI_LY_DO_HUY",
        "HOI_THAM",
        "KHAC",
    }
)
#: Loại việc luôn nói về MỘT lịch hẹn cụ thể.
CAN_LICH_HEN = frozenset({"XAC_NHAN_LICH", "NHAC_HEN", "HOI_LY_DO_HUY"})
KENH_HOP_LE = frozenset({"GOI", "ZALO", "SMS", "TRUC_TIEP", "KHONG_LIEN_HE"})
#: KNM = CHUA_NGHE_MAY, KLLD = KHONG_LIEN_LAC_DUOC, Hẹn GLS = HEN_GOI_LAI
#: (Quang giải nghĩa 08/08/2026). Cả ba sinh ra việc "cần gọi lại".
KET_QUA_HOP_LE = frozenset(
    {
        "DA_LIEN_HE",
        "CHUA_NGHE_MAY",
        "KHONG_LIEN_LAC_DUOC",
        "HEN_GOI_LAI",
        "CAN_BAC_SI",
        "TU_CHOI",
        "BO_QUA",
    }
)


class TuongTacCskhService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def ghi(
        self,
        *,
        identity: StaffIdentity,
        clinic_patient_id: str,
        loai: str,
        kenh: str,
        ket_qua: str,
        appointment_id: str | None = None,
        khach_xac_nhan: bool | None = None,
        noi_dung: str | None = None,
    ) -> dict[str, Any]:
        """Ghi một lần chạm tới khách. Trả về id dòng vừa ghi."""
        if loai not in LOAI_HOP_LE:
            raise ValidationError(f"Loại tương tác không hợp lệ: {loai!r}.")
        if kenh not in KENH_HOP_LE:
            raise ValidationError(f"Kênh không hợp lệ: {kenh!r}.")
        if ket_qua not in KET_QUA_HOP_LE:
            raise ValidationError(f"Kết quả không hợp lệ: {ket_qua!r}.")
        # Nói ra ở đây bằng tiếng Việt thay vì để CHECK của Postgres nổ thành
        # một lỗi 500 mà người dùng không đọc được.
        if (ket_qua == "BO_QUA") != (kenh == "KHONG_LIEN_HE"):
            raise ValidationError(
                "'Bỏ qua' phải đi cùng 'không liên hệ' — và ngược lại."
            )
        if khach_xac_nhan is not None and loai not in ("XAC_NHAN_LICH", "NHAC_HEN"):
            raise ValidationError(
                "Chỉ việc xác nhận lịch / nhắc hẹn mới ghi được 'khách xác nhận'."
            )
        if loai in CAN_LICH_HEN and not appointment_id:
            raise ValidationError("Việc này phải gắn với một lịch hẹn cụ thể.")

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                # Bệnh nhân phải thuộc phòng khám đang đăng nhập. Không kiểm thì
                # một id đoán được là một dòng chăm sóc gắn vào khách của phòng
                # khám khác — và RLS chỉ giấu nó đi, không ngăn nó ra đời.
                ok = await conn.fetchval(
                    "SELECT 1 FROM public.patient "
                    " WHERE clinic_patient_id = $1::uuid AND clinic_id = $2::uuid",
                    clinic_patient_id,
                    identity.clinic_id,
                )
                if not ok:
                    raise NotFoundError("Không tìm thấy khách hàng này.")
                if appointment_id:
                    thuoc_ve = await conn.fetchval(
                        "SELECT 1 FROM public.appointment "
                        " WHERE id = $1::uuid AND clinic_id = $2::uuid "
                        "   AND clinic_patient_id = $3::uuid",
                        appointment_id,
                        identity.clinic_id,
                        clinic_patient_id,
                    )
                    if not thuoc_ve:
                        raise ValidationError("Lịch hẹn không phải của khách này.")

                row_id = await conn.fetchval(
                    """
                    INSERT INTO public.tuong_tac_cskh
                        (clinic_id, clinic_patient_id, appointment_id, loai, kenh,
                         ket_qua, khach_xac_nhan, noi_dung, nhan_vien_staff_id)
                    VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $5, $6, $7, $8, $9::uuid)
                    RETURNING id::text
                    """,
                    identity.clinic_id,
                    clinic_patient_id,
                    appointment_id,
                    loai,
                    kenh,
                    ket_qua,
                    khach_xac_nhan,
                    (noi_dung or "").strip() or None,
                    identity.staff_id,
                )
                await conn.execute(
                    """
                    INSERT INTO public.event_log
                        (clinic_id, event_type, aggregate_type, aggregate_id,
                         payload, source, occurred_at)
                    VALUES ($1::uuid, 'cskh.tuong_tac', 'patient', $2::uuid,
                            jsonb_build_object('loai', $3::text, 'kenh', $4::text,
                                               'ket_qua', $5::text,
                                               'by_staff_id', $6::text),
                            'cskh.customers', now())
                    """,
                    identity.clinic_id,
                    clinic_patient_id,
                    loai,
                    kenh,
                    ket_qua,
                    identity.staff_id,
                )

        logger.info(
            "cskh_tuong_tac_ghi",
            loai=loai,
            kenh=kenh,
            ket_qua=ket_qua,
            by_staff_id=identity.staff_id,
        )
        return {"ok": True, "id": row_id}

    async def lich_su(
        self, *, identity: StaffIdentity, clinic_patient_id: str, gioi_han: int = 50
    ) -> list[dict[str, Any]]:
        """Dòng thời gian của một khách, mới nhất trước.

        Gộp cả `nhac_tai_kham` đã gọi xong: hai bảng, một dòng thời gian. CSKH
        không cần biết cuộc gọi nào được lưu ở bảng nào — họ cần biết khách này
        đã được gọi mấy lần và lần cuối nói gì.
        """
        rows = await self._pool.fetch(
            """
            SELECT t.xay_ra_luc, t.loai, t.kenh, t.ket_qua, t.khach_xac_nhan,
                   t.noi_dung, s.full_name AS nhan_vien, 'tuong_tac' AS nguon
              FROM public.tuong_tac_cskh t
              LEFT JOIN public.staff s ON s.id = t.nhan_vien_staff_id
             WHERE t.clinic_id = $1::uuid AND t.clinic_patient_id = $2::uuid

            UNION ALL

            SELECT n.goi_luc AS xay_ra_luc,
                   CASE n.luot_goi WHEN 1 THEN 'MOI_TAI_KHAM'
                                   ELSE 'NHAC_DI_KHAM' END AS loai,
                   'GOI' AS kenh, n.ket_qua, NULL::boolean AS khach_xac_nhan,
                   n.ghi_chu AS noi_dung, s2.full_name AS nhan_vien,
                   'nhac_tai_kham' AS nguon
              FROM public.nhac_tai_kham n
              LEFT JOIN public.staff s2 ON s2.id = n.nguoi_goi_staff_id
             WHERE n.clinic_id = $1::uuid AND n.clinic_patient_id = $2::uuid
               AND n.goi_luc IS NOT NULL

             ORDER BY xay_ra_luc DESC
             LIMIT $3
            """,
            identity.clinic_id,
            clinic_patient_id,
            gioi_han,
        )
        return [dict(r) for r in rows]


class HenGoiLaiService:
    """Việc CSKH tự hẹn cho mình: "gọi lại ngày…".

    Chỗ đựng những việc hệ thống CHƯA suy được — gọi hỏi thăm sau thủ thuật,
    chúc mừng đầy tháng sau sinh.

    VÌ SAO GÕ TAY. Đo trên bản thật: không cột nào chứa ngày sinh con thật
    (`edd_date` là ngày DỰ sinh, lệch hai tuần là gọi chúc mừng vào tuần thứ
    hai hoặc tuần thứ sáu), và "thủ thuật" chưa phải một khái niệm — các
    service_type thủ thuật đang is_active = false sau 20260807000007.

    Một nút để người gõ thì có việc THẬT. Một tab tự sinh từ ngày dự sinh thì
    có việc SAI, và không ai biết nó sai cho tới lúc gọi nhầm.
    """

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def tao(
        self,
        *,
        identity: StaffIdentity,
        clinic_patient_id: str,
        ngay_goi: date,
        ly_do: str,
    ) -> dict[str, Any]:
        ly_do = (ly_do or "").strip()
        if not ly_do:
            # Một việc không có lý do là một việc mà tuần sau không ai biết vì
            # sao nó ở đó, và người trực sẽ đóng nó cho gọn màn hình.
            raise ValidationError("Ghi rõ gọi lại để làm gì.")
        hom_nay = datetime.now(GIO_VN).date()
        if ngay_goi < hom_nay:
            raise ValidationError("Ngày gọi lại không thể ở quá khứ.")

        async with self._pool.acquire() as conn:
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
                INSERT INTO public.hen_goi_lai
                    (clinic_id, clinic_patient_id, ngay_goi, ly_do, tao_boi_staff_id)
                VALUES ($1::uuid, $2::uuid, $3, $4, $5::uuid)
                RETURNING id::text
                """,
                identity.clinic_id,
                clinic_patient_id,
                ngay_goi,
                ly_do,
                identity.staff_id,
            )
        logger.info("cskh_hen_goi_lai", ngay=str(ngay_goi), by=identity.staff_id)
        return {"ok": True, "id": row_id}

    async def dong(self, *, identity: StaffIdentity, hen_id: str) -> dict[str, Any]:
        """Đóng việc. Ai đóng và lúc nào đi cùng nhau — CHECK ở DB giữ điều đó."""
        row = await self._pool.fetchrow(
            "UPDATE public.hen_goi_lai "
            "   SET dong_luc = now(), dong_boi_staff_id = $1::uuid "
            " WHERE id = $2::uuid AND clinic_id = $3::uuid AND dong_luc IS NULL "
            "RETURNING id::text",
            identity.staff_id,
            hen_id,
            identity.clinic_id,
        )
        if row is None:
            raise NotFoundError("Không tìm thấy việc này, hoặc nó đã đóng rồi.")
        return {"ok": True}
