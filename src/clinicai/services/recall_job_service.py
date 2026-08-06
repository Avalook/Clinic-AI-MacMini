"""Việc gọi nhắc tái khám — hai lượt, có người phụ trách và có hạn.

VÌ SAO FILE NÀY ĐƯỢC VIẾT.

`RecallService` bên cạnh trả về một PHÉP CHIẾU: mỗi lần CSKH mở trang, nó tính
lại từ đầu xem ai đến hạn tái khám. Không có dòng nào trong database, nên:
không ai mở trang thì không ai biết có người cần gọi; không giao được cho một
người cụ thể; trưởng ca không đối soát được cuối ngày; và "ai đã gọi lượt một,
ai còn thiếu lượt hai" là câu không trả lời được.

File này biến nó thành VIỆC: `nhac_tai_kham`, mỗi dòng một cuộc gọi phải làm.

HAI LƯỢT LÀ HAI VIỆC KHÁC NHAU.

    Lượt 1 — bác sĩ dặn quay lại ngày X, khách CHƯA đặt lịch.
             Gọi trước 5–7 ngày, để MỜI ĐẶT LỊCH.
    Lượt 2 — khách ĐÃ có lịch hẹn hôm nay.
             Gọi buổi sáng, để NHẮC ĐI KHÁM.

Nhóm thứ hai là nhóm hiện không màn nào hiện: danh sách nhắc tái khám loại bỏ
người đã có lịch, còn màn nhiệm vụ CSKH lại bắt đầu từ NGÀY MAI.

AI CHẠY BỘ SINH VIỆC.

Dự án chưa có bộ hẹn giờ nào (đã tìm: không apscheduler, không croniter, không
repeat_every). Nên đường chắc chắn nhất hôm nay là sinh ngay lúc CSKH mở màn —
`danh_sach()` gọi `sinh()` trước khi đọc. Hàm sinh việc idempotent, nên cắm
thêm cron vào ngày mai không phải đổi gì, và chạy cả hai đường cùng lúc cũng
không đẻ thêm việc.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import asyncpg
import structlog

from clinicai.api.exceptions import NotFoundError, ValidationError
from clinicai.api.identity import StaffIdentity

# `clinic_today` sống ở cskh_service — cùng một "ngày làm việc" mà toàn bộ nhật
# ký CSKH đóng dấu, nên dùng lại chứ không tự tính giờ Việt Nam lần nữa.
from clinicai.services.cskh_service import clinic_today

logger = structlog.get_logger()

#: Bốn kết quả, cùng bộ từ với `cskh_log.ket_qua` (20260807000002).
KET_QUA_HOP_LE = frozenset({"DA_LIEN_HE", "CHUA_NGHE_MAY", "CAN_BAC_SI", "TU_CHOI"})

#: "Gọi trước 5–7 ngày" — cận trên của cửa sổ, dùng để tô màu ở giao diện.
#: Việc vẫn được sinh sớm hơn và ở lại tới khi có người đóng; xem migration.
CUA_SO_NGAY = 7


class RecallJobService:
    """Sinh, liệt kê và đóng việc gọi nhắc tái khám."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def sinh(
        self, *, identity: StaffIdentity, ngay: date | None = None
    ) -> dict[str, int]:
        """Sinh việc cho một ngày. Chạy lại bao nhiêu lần cũng như một."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT luot1_moi, luot2_moi "
                "FROM public.sinh_viec_nhac_tai_kham($1::uuid, $2::date)",
                identity.clinic_id,
                ngay,
            )
        moi = {
            "luot1_moi": int(row["luot1_moi"]) if row else 0,
            "luot2_moi": int(row["luot2_moi"]) if row else 0,
        }
        if moi["luot1_moi"] or moi["luot2_moi"]:
            logger.info("recall_jobs_generated", clinic_id=identity.clinic_id, **moi)
        return moi

    async def danh_sach(
        self, *, identity: StaffIdentity, sinh_truoc: bool = True
    ) -> dict[str, Any]:
        """Việc còn phải gọi, tách theo lượt.

        `sinh_truoc` mặc định bật: mở màn hình là sinh việc của hôm nay. Đó là
        thứ duy nhất chắc chắn chạy khi chưa có cron — và vì hàm sinh là
        idempotent, bật nó ở đây không tạo ra bản sao nào.
        """
        if sinh_truoc:
            await self.sinh(identity=identity)

        hom_nay = date.fromisoformat(clinic_today())
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT n.id::text,
                       n.luot_goi,
                       n.ngay_hen,
                       n.han_goi,
                       n.trang_thai,
                       n.ket_qua,
                       n.ghi_chu,
                       n.goi_luc,
                       p.full_name,
                       p.phone_primary,
                       p.patient_code,
                       s.full_name AS nguoi_goi,
                       (n.han_goi < $2::date) AS qua_han,
                       a.slot_start
                  FROM public.nhac_tai_kham n
                  JOIN public.patient p
                    ON p.clinic_patient_id = n.clinic_patient_id
                  LEFT JOIN public.staff s ON s.id = n.nguoi_goi_staff_id
                  LEFT JOIN public.appointment a ON a.id = n.appointment_id
                 WHERE n.clinic_id = $1::uuid
                   AND n.trang_thai = 'CHO_GOI'
                 ORDER BY n.luot_goi, n.han_goi, p.full_name
                 LIMIT 500
                """,
                identity.clinic_id,
                hom_nay,
            )

        viec = [dict(r) for r in rows]
        return {
            "ngay": hom_nay.isoformat(),
            "cua_so_ngay": CUA_SO_NGAY,
            "luot1": [v for v in viec if v["luot_goi"] == 1],
            "luot2": [v for v in viec if v["luot_goi"] == 2],
        }

    async def ghi_ket_qua(
        self,
        *,
        identity: StaffIdentity,
        viec_id: str,
        ket_qua: str,
        ghi_chu: str | None = None,
    ) -> dict[str, Any]:
        """Đã gọi xong. Kết quả BẮT BUỘC — kể cả khi không ai bắt máy.

        "Chuông đổ không ai bắt" cũng là một việc đã làm, và nó phải khác
        "đã nói chuyện được". Không phân biệt được thì hôm sau người khác mở
        lên thấy 'đã gọi' rồi bỏ qua một người chưa ai nói chuyện với.
        """
        if ket_qua not in KET_QUA_HOP_LE:
            raise ValidationError(
                f"Kết quả cuộc gọi không hợp lệ: {ket_qua!r}. "
                f"Chọn một trong: {', '.join(sorted(KET_QUA_HOP_LE))}."
            )
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                UPDATE public.nhac_tai_kham
                   SET trang_thai = 'DA_GOI',
                       ket_qua = $3,
                       ghi_chu = $4,
                       nguoi_goi_staff_id = $5::uuid,
                       goi_luc = now(),
                       dong_luc = now(),
                       updated_at = now()
                 WHERE id = $1::uuid AND clinic_id = $2::uuid
                   AND trang_thai = 'CHO_GOI'
                RETURNING id::text, luot_goi, clinic_patient_id::text
                """,
                viec_id,
                identity.clinic_id,
                ket_qua,
                (ghi_chu or "").strip() or None,
                identity.staff_id,
            )
            if row is None:
                # Hai người cùng bấm, hoặc bấm lại sau khi mạng lag. Nói rõ là
                # KHÔNG có gì đổi, đừng trả "ok" trống khiến người dùng tưởng
                # vừa ghi được.
                con = await conn.fetchval(
                    "SELECT trang_thai FROM public.nhac_tai_kham "
                    "WHERE id = $1::uuid AND clinic_id = $2::uuid",
                    viec_id,
                    identity.clinic_id,
                )
                if con is None:
                    raise NotFoundError("Không tìm thấy việc gọi này.")
                return {"ok": True, "da_ghi_tu_truoc": True, "trang_thai": con}

            # Nhật ký CSKH vẫn ghi như trước — màn hồ sơ bệnh nhân đọc từ đó.
            # `luot_goi` đi kèm để về sau đối soát được "ai thiếu lượt hai".
            await conn.execute(
                """
                INSERT INTO public.cskh_log
                    (clinic_id, clinic_patient_id, work_date, cskh_status,
                     cskh_followup, last_cskh_date, cskh_by, note,
                     ket_qua, luot_goi)
                VALUES ($1::uuid, $2::uuid, $3::date, 'Đã gọi nhắc tái khám',
                        'Nhắc gọi tái khám', $3::date, $4, $5, $6, $7)
                """,
                identity.clinic_id,
                row["clinic_patient_id"],
                date.fromisoformat(clinic_today()),
                f"{identity.full_name} · {identity.role.value}",
                (ghi_chu or "").strip() or None,
                ket_qua,
                row["luot_goi"],
            )

        logger.info(
            "recall_call_logged",
            viec_id=viec_id,
            luot_goi=row["luot_goi"],
            ket_qua=ket_qua,
            by_staff_id=identity.staff_id,
        )
        return {"ok": True, "id": row["id"], "luot_goi": row["luot_goi"]}

    async def bo_qua(
        self, *, identity: StaffIdentity, viec_id: str, ly_do: str
    ) -> dict[str, Any]:
        """Không cần gọi nữa (khách đã tự đặt lịch, đã tới khám, đã báo huỷ)."""
        ly = (ly_do or "").strip()
        if not ly:
            raise ValidationError("Bỏ qua một việc gọi thì phải ghi vì sao.")
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                UPDATE public.nhac_tai_kham
                   SET trang_thai = 'KHONG_CAN',
                       ghi_chu = $3,
                       dong_luc = now(),
                       updated_at = now()
                 WHERE id = $1::uuid AND clinic_id = $2::uuid
                   AND trang_thai = 'CHO_GOI'
                RETURNING id::text
                """,
                viec_id,
                identity.clinic_id,
                ly,
            )
        if row is None:
            raise NotFoundError("Không tìm thấy việc gọi đang chờ với mã này.")
        return {"ok": True, "id": row["id"]}
