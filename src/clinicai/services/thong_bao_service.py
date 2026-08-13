"""Trưởng ca gọi một bộ phận, và bộ phận ấy nhận được.

VÌ SAO FILE NÀY ĐƯỢC VIẾT.

Màn cảnh báo của Trưởng ca đã nói được "phòng SA1 đang tắc, bốn người chờ, lâu
nhất 38 phút". Nó KHÔNG nói được với ai. Không nút gọi, không endpoint, không
bảng thông báo, không đường giao hàng — trưởng ca nhìn thấy rồi phải rời màn
hình, cầm điện thoại hoặc đi bộ sang.

BA TÍNH CHẤT PHẢI CÓ, KHÔNG THÌ CÁI CHUÔNG LẠI THÀNH ĐỒ TRANG TRÍ:

1.  Gọi hai lần không thành hai thông báo. Lúc sốt ruột người ta bấm nhiều lần;
    bên kia phải thấy một việc, không phải mười. Chống bằng khoá duy nhất từng
    phần ở database (`uq_thong_bao_dang_mo`), không phải bằng nút disabled ở
    trình duyệt — trình duyệt thì mở hai tab là hỏng.

2.  Có đường ĐÓNG. Thông báo mở mãi là thông báo người ta học cách bỏ qua. Bên
    nhận bấm "đã xử lý", và từ đó đo được thời gian phản hồi.

3.  Người gọi biết chuyện gì xảy ra. Bấm mà im lặng thì lần sau họ gọi bằng
    điện thoại — và tính năng này coi như không tồn tại.
"""

from __future__ import annotations

import json
from typing import Any

import asyncpg
import structlog

from clinicai.api.exceptions import NotFoundError, ValidationError
from clinicai.api.identity import ClinicRole, StaffIdentity

logger = structlog.get_logger()

#: Nguồn → (mã sự kiện ghi vào nhật ký, đường ghi). Khai tường minh để một chuỗi
#: gõ sai không lặng lẽ tạo ra một "nguồn" mới mà không màn nào biết cách hiển
#: thị — và để khoá chống trùng `uq_thong_bao_dang_mo` (clinic, nguon, nguon_id,
#: vai_nhan) tách bạch giữa các loại việc.
#:
#: LƯU Ý CHO BÀI KIỂM CHỐNG LỆCH: hai mã dưới đi vào `event_log` như THAM SỐ,
#: không phải chuỗi hằng cạnh câu INSERT, nên bộ quét ở
#: `test_audit_labels_drift.py` không thấy chúng. Nhãn tiếng Việt của chúng đã
#: thêm tay vào `audit_labels.EVENT_LABELS`; sửa bảng này thì sửa cả bên đó.
NGUON: dict[str, tuple[str, str]] = {
    "dispatch_alert": ("dispatch.alert_called", "api:dispatch"),
    # Quản lý vừa gán bác sĩ cho một lịch trước đó còn trống → CSKH gọi xác nhận.
    "bac_si_da_xep": ("thong_bao.bac_si_da_xep", "api:booking"),
    # Quản lý vừa áp lịch trực cả tuần → tuần ấy đã có người, những lịch đang
    # chờ trong tuần xếp được rồi.
    "tuan_lich_truc": ("thong_bao.tuan_lich_truc", "config.roster"),
    # CSKH tự hẹn "gọi lại lúc 17:00" → mẩu giấy dán màn hình cho chính vai CSKH.
    "hen_goi_lai": ("thong_bao.hen_goi_lai", "cskh.customers"),
}

#: Nguồn duy nhất trước 09/08/2026 — giữ tên cũ vì `dispatch.py` gọi theo nó.
NGUON_CANH_BAO = "dispatch_alert"

MUC_DO_HOP_LE = frozenset({"KHAN", "THUONG"})


class ThongBaoService:
    """Gọi bộ phận, liệt kê thông báo của tôi, đóng khi đã xử lý."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def goi(
        self,
        *,
        identity: StaffIdentity,
        vai_nhan: str,
        tieu_de: str,
        noi_dung: str,
        nguon_id: str | None = None,
        muc_do: str = "KHAN",
        duong_dan: str | None = None,
        nguon: str = NGUON_CANH_BAO,
    ) -> dict[str, Any]:
        """Gọi một bộ phận. Bấm lại khi chưa ai xử lý thì KHÔNG tạo thêm."""
        if muc_do not in MUC_DO_HOP_LE:
            raise ValidationError(f"Mức độ không hợp lệ: {muc_do!r}.")
        if nguon not in NGUON:
            raise ValidationError(f"Nguồn thông báo không hợp lệ: {nguon!r}.")
        ma_su_kien, duong_ghi = NGUON[nguon]
        try:
            vai = ClinicRole(vai_nhan)
        except ValueError:
            raise ValidationError(
                f"Không có vai {vai_nhan!r} trong phòng khám."
            ) from None
        if not (tieu_de or "").strip() or not (noi_dung or "").strip():
            raise ValidationError("Thông báo phải có tiêu đề và nội dung.")

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    """
                    INSERT INTO public.thong_bao
                        (clinic_id, vai_nhan, muc_do, tieu_de, noi_dung,
                         nguon, nguon_id, duong_dan, nguoi_goi_staff_id)
                    VALUES ($1::uuid, $2, $3, $4, $5, $6, $7, $8, $9::uuid)
                    ON CONFLICT (clinic_id, nguon, nguon_id, vai_nhan)
                        WHERE da_xu_ly_luc IS NULL
                          AND nguon_id IS NOT NULL
                          AND vai_nhan IS NOT NULL
                    DO NOTHING
                    RETURNING id::text, tao_luc
                    """,
                    identity.clinic_id,
                    vai.value,
                    muc_do,
                    tieu_de.strip(),
                    noi_dung.strip(),
                    nguon,
                    nguon_id,
                    duong_dan,
                    identity.staff_id,
                )
                if row is None:
                    # KHÔNG phải lỗi, nhưng cũng KHÔNG phải "đã gửi". Nói rõ,
                    # để trưởng ca biết bên kia đã có việc từ trước và chưa
                    # đụng tới — chứ không tưởng mình vừa gọi thêm một lần.
                    cu = await conn.fetchrow(
                        """
                        SELECT id::text, tao_luc FROM public.thong_bao
                         WHERE clinic_id = $1::uuid AND nguon = $2
                           AND nguon_id = $3 AND vai_nhan = $4
                           AND da_xu_ly_luc IS NULL
                        """,
                        identity.clinic_id,
                        nguon,
                        nguon_id,
                        vai.value,
                    )
                    return {
                        "ok": True,
                        "da_goi_tu_truoc": True,
                        "id": cu["id"] if cu else None,
                        "tao_luc": cu["tao_luc"] if cu else None,
                    }

                await conn.execute(
                    """
                    INSERT INTO public.event_log
                        (clinic_id, event_type, aggregate_type, aggregate_id,
                         payload, metadata, source, event_published)
                    VALUES ($1::uuid, $5, 'thong_bao',
                            $2::uuid, $3::jsonb, $4::jsonb, $6,
                            FALSE)
                    """,
                    identity.clinic_id,
                    row["id"],
                    json.dumps(
                        {
                            "vai_nhan": vai.value,
                            "muc_do": muc_do,
                            "tieu_de": tieu_de.strip(),
                            "nguon_id": nguon_id,
                        },
                        ensure_ascii=False,
                    ),
                    json.dumps(
                        {
                            "actor_auth_user_id": identity.auth_user_id,
                            "clinic_staff_id": identity.staff_id,
                            "clinic_role": identity.role.value,
                        }
                    ),
                    ma_su_kien,
                    duong_ghi,
                )

        logger.info(
            "thong_bao_gui",
            nguon=nguon,
            thong_bao_id=row["id"],
            vai_nhan=vai.value,
            by_staff_id=identity.staff_id,
        )
        return {"ok": True, "id": row["id"], "vai_nhan": vai.value}

    async def cua_toi(self, *, identity: StaffIdentity) -> list[dict[str, Any]]:
        """Thông báo CHƯA XỬ LÝ dành cho vai của tôi, hoặc đích danh tôi."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT t.id::text,
                       t.muc_do,
                       t.tieu_de,
                       t.noi_dung,
                       t.duong_dan,
                       t.tao_luc,
                       t.da_doc_luc,
                       s.full_name AS nguoi_goi
                  FROM public.thong_bao t
                  LEFT JOIN public.staff s ON s.id = t.nguoi_goi_staff_id
                 WHERE t.clinic_id = $1::uuid
                   AND t.da_xu_ly_luc IS NULL
                   AND (t.vai_nhan = $2 OR t.nguoi_nhan_staff_id = $3::uuid)
                 ORDER BY (t.muc_do = 'KHAN') DESC, t.tao_luc DESC
                 LIMIT 50
                """,
                identity.clinic_id,
                identity.role.value,
                identity.staff_id,
            )
        return [dict(r) for r in rows]

    async def danh_dau_da_doc(self, *, identity: StaffIdentity) -> dict[str, Any]:
        """Đóng dấu ĐÃ ĐỌC cho mọi thông báo đang mở của vai này.

        ĐỌC ≠ ĐÃ XỬ LÝ, và đó là cả lý do có hai cột. `da_xu_ly_luc` là việc
        đã xong; `da_doc_luc` chỉ là "tôi thấy rồi". Nút "Đánh dấu đã đọc" phải
        tắt được chấm đỏ mà KHÔNG đóng việc — đóng việc hộ ở đây là làm mất một
        hàng đợi thật chỉ vì ai đó mở cái chuông ra xem.

        Trước đây nút ấy chỉ gọi `setUnread(0)` ở trình duyệt, trong khi con số
        trên chuông là `unread + thongBao.length` — phần đến từ máy chủ không
        có đường nào tắt, nên chấm đỏ ở lại mãi và người dùng học cách lờ nó đi.
        """
        async with self._pool.acquire() as conn:
            so = await conn.fetchval(
                """
                UPDATE public.thong_bao
                   SET da_doc_luc = now()
                 WHERE clinic_id = $1::uuid
                   AND da_xu_ly_luc IS NULL
                   AND da_doc_luc IS NULL
                   AND (vai_nhan = $2 OR nguoi_nhan_staff_id = $3::uuid)
                RETURNING 1
                """,
                identity.clinic_id,
                identity.role.value,
                identity.staff_id,
            )
        logger.info(
            "thong_bao_danh_dau_da_doc",
            vai_nhan=identity.role.value,
            by_staff_id=identity.staff_id,
        )
        return {"ok": True, "co_thay_doi": so is not None}

    async def da_xu_ly(
        self, *, identity: StaffIdentity, thong_bao_id: str, ghi_chu: str | None
    ) -> dict[str, Any]:
        """Bên nhận đóng việc. Từ đây đo được thời gian phản hồi."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                UPDATE public.thong_bao
                   SET da_xu_ly_luc = now(),
                       da_xu_ly_boi = $3::uuid,
                       ghi_chu_xu_ly = $4,
                       da_doc_luc = coalesce(da_doc_luc, now())
                 WHERE id = $1::uuid AND clinic_id = $2::uuid
                   AND da_xu_ly_luc IS NULL
                RETURNING id::text,
                          extract(epoch FROM (now() - tao_luc))::int AS giay_phan_hoi
                """,
                thong_bao_id,
                identity.clinic_id,
                identity.staff_id,
                (ghi_chu or "").strip() or None,
            )
        if row is None:
            raise NotFoundError(
                "Không tìm thấy thông báo đang mở với mã này — "
                "có thể người khác vừa xử lý xong."
            )
        logger.info(
            "thong_bao_resolved",
            thong_bao_id=thong_bao_id,
            giay_phan_hoi=row["giay_phan_hoi"],
            by_staff_id=identity.staff_id,
        )
        return {"ok": True, "id": row["id"], "giay_phan_hoi": row["giay_phan_hoi"]}
