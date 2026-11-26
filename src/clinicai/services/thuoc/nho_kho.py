"""Nút “Nhờ kho thêm thuốc” — hàng chờ tên thuốc chưa có trong danh mục (26/11).

Thay đường cũ: lưu đơn với tên lạ từng tự thêm thuốc vào danh mục (không giá, cờ
cần soát). Nay người kê bấm nhờ → một yêu cầu ở `thuoc_nho_kho` + sự kiện
`pharmacy.drug_requested` (chuông cho người nhận việc kho). Người kho thêm thuốc
ở Danh mục rồi bấm "Xong"; bấm nhầm thì "Mở lại" (hoàn tác).

Hai người nhờ cùng một tên lúc yêu cầu cũ còn mở = MỘT yêu cầu (UNIQUE từng phần
ở DB); người thứ hai nhận lại yêu cầu đang mở, không phát chuông lần nữa.
"""

from __future__ import annotations

from typing import Any

import asyncpg

from clinicai.api.exceptions import ConflictError, NotFoundError, ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.core.tran import canh_bao_neu_day
from clinicai.events import emit_event, nguoi
from clinicai.events.catalogue import ThuocNhoKho

TEN_TOI_DA = 200
GHI_CHU_TOI_DA = 500


def doc_ten_nho(ten: Any) -> str:
    """Tên gõ đã gọn dấu cách; rỗng → 422, dài quá → 422 (không cắt im lặng)."""
    gon = " ".join(str(ten or "").split())
    if not gon:
        raise ValidationError("Nhập tên thuốc cần nhờ kho thêm.")
    if len(gon) > TEN_TOI_DA:
        raise ValidationError(f"Tên thuốc dài quá {TEN_TOI_DA} ký tự.")
    return gon


async def nho_kho_them(
    pool: asyncpg.Pool,
    *,
    identity: StaffIdentity,
    ten: Any,
    ghi_chu: Any = None,
    visit_id: str | None = None,
) -> dict[str, Any]:
    """Ghi (hoặc nhận lại) yêu cầu đang mở cho tên này. `moi` = vừa tạo."""
    ten_go = doc_ten_nho(ten)
    chu = " ".join(str(ghi_chu or "").split())[:GHI_CHU_TOI_DA] or None
    async with pool.acquire() as conn, conn.transaction():
        moi = await conn.fetchval(
            """
            INSERT INTO public.thuoc_nho_kho
                (clinic_id, location_id, ten_go, ghi_chu, visit_id, tao_boi)
            VALUES ($1::uuid, $2::uuid, $3, $4, $5::uuid, $6::uuid)
            ON CONFLICT (clinic_id, lower(btrim(ten_go))) WHERE xong_luc IS NULL
            DO NOTHING
            RETURNING id::text
            """,
            identity.clinic_id,
            identity.location_id,
            ten_go,
            chu,
            visit_id,
            identity.staff_id,
        )
        if moi is not None:
            await emit_event(
                conn,
                ten="pharmacy.drug_requested",
                clinic_id=identity.clinic_id,
                aggregate_id=moi,
                payload=ThuocNhoKho(ten_go=ten_go, visit_id=visit_id),
                boi=nguoi(identity),
            )
            return {"id": moi, "ten_go": ten_go, "moi": True}
        cu = await conn.fetchval(
            "SELECT id::text FROM public.thuoc_nho_kho WHERE clinic_id = $1::uuid"
            " AND lower(btrim(ten_go)) = lower(btrim($2)) AND xong_luc IS NULL",
            identity.clinic_id,
            ten_go,
        )
    return {"id": cu, "ten_go": ten_go, "moi": False}


async def danh_sach_nho_kho(
    pool: asyncpg.Pool, *, identity: StaffIdentity
) -> list[dict[str, Any]]:
    """Yêu cầu đang mở trước, rồi 30 yêu cầu đã xong gần nhất."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            (SELECT n.id::text, n.ten_go, n.ghi_chu, n.tao_luc, n.xong_luc,
                    t.full_name AS nguoi_nho, x.full_name AS nguoi_xong
               FROM public.thuoc_nho_kho n
               LEFT JOIN public.staff t ON t.id = n.tao_boi
               LEFT JOIN public.staff x ON x.id = n.xong_boi
              WHERE n.clinic_id = $1::uuid AND n.xong_luc IS NULL
              ORDER BY n.tao_luc DESC LIMIT 200)
            UNION ALL
            (SELECT n.id::text, n.ten_go, n.ghi_chu, n.tao_luc, n.xong_luc,
                    t.full_name, x.full_name
               FROM public.thuoc_nho_kho n
               LEFT JOIN public.staff t ON t.id = n.tao_boi
               LEFT JOIN public.staff x ON x.id = n.xong_boi
              WHERE n.clinic_id = $1::uuid AND n.xong_luc IS NOT NULL
              ORDER BY n.xong_luc DESC LIMIT 30)
            """,
            identity.clinic_id,
        )
    mo = sum(1 for r in rows if r["xong_luc"] is None)
    canh_bao_neu_day("thuoc_nho_kho", mo, 200, clinic_id=identity.clinic_id)
    return [{**dict(r), "xong": r["xong_luc"] is not None} for r in rows]


async def danh_dau_nho_kho(
    pool: asyncpg.Pool, *, identity: StaffIdentity, yeu_cau_id: str, xong: bool
) -> dict[str, Any]:
    """Xong (đã thêm thuốc / bỏ qua) hoặc Mở lại — chiều này hoàn tác chiều kia."""
    async with pool.acquire() as conn, conn.transaction():
        try:
            ma = await conn.fetchval(
                """
                UPDATE public.thuoc_nho_kho
                   SET xong_luc = CASE WHEN $3 THEN now() END,
                       xong_boi = CASE WHEN $3 THEN $4::uuid END
                 WHERE clinic_id = $1::uuid AND id = $2::uuid
                   AND (xong_luc IS NULL) = $3
                RETURNING id::text
                """,
                identity.clinic_id,
                yeu_cau_id,
                xong,
                identity.staff_id,
            )
        except asyncpg.UniqueViolationError:
            raise ConflictError(
                "Đang có yêu cầu khác mở cho cùng tên thuốc — dùng yêu cầu đó."
            ) from None
    if ma is None:
        raise NotFoundError("Không thấy yêu cầu này, hoặc nó đã đổi — tải lại.")
    return {"id": ma, "xong": xong}


__all__ = ["danh_dau_nho_kho", "danh_sach_nho_kho", "doc_ten_nho", "nho_kho_them"]
