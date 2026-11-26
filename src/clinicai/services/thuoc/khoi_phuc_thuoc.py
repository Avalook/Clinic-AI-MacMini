"""Khôi phục thuốc đã xoá khỏi Danh mục — hoàn tác của `xoa_thuoc` (26/11/2026).

Dựng lại ĐÚNG các dòng đã chụp (cùng id thuốc, cùng giá, đơn vị, mã hàng; cùng
các dòng `thuoc_quy_doi`, `drug_ma_vach`) từ `drug_catalog_da_xoa`, rồi đánh dấu
bản lưu đã khôi phục (ai, lúc nào). Bản lưu giữ nguyên — sổ chỉ ghi thêm.

Từ chối (409, câu tiếng Việt) khi: bản lưu đã khôi phục rồi; hoặc từ lúc xoá đã có
thuốc khác trùng tên / mã vạch (ràng buộc UNIQUE của danh mục) — đổi tên thuốc kia
trước rồi khôi phục.
"""

from __future__ import annotations

from typing import Any

import asyncpg

from clinicai.api.exceptions import ConflictError, NotFoundError
from clinicai.api.identity import StaffIdentity
from clinicai.core.tran import canh_bao_neu_day
from clinicai.services.pharmacy_service import ghi_nhat_ky

TRAN_DANH_SACH = 100


async def danh_sach_da_xoa(
    pool: asyncpg.Pool, *, identity: StaffIdentity
) -> list[dict[str, Any]]:
    """Thuốc đã xoá gần nhất (cả đã khôi phục) — mới nhất trước."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT d.id::text, d.drug_catalog_id::text, d.ten, d.ly_do, d.xoa_luc,
                   x.full_name AS nguoi_xoa, d.khoi_phuc_luc,
                   k.full_name AS nguoi_khoi_phuc
              FROM public.drug_catalog_da_xoa d
              LEFT JOIN public.staff x ON x.id = d.xoa_boi
              LEFT JOIN public.staff k ON k.id = d.khoi_phuc_boi
             WHERE d.clinic_id = $1::uuid
             ORDER BY d.xoa_luc DESC, d.id
             LIMIT 100
            """,
            identity.clinic_id,
        )
    canh_bao_neu_day("drug_catalog_da_xoa", len(rows), TRAN_DANH_SACH)
    return [{**dict(r), "da_khoi_phuc": r["khoi_phuc_luc"] is not None} for r in rows]


#: Chỉ ba bảng này được dựng lại — tên đi vào SQL động, nên là hằng, không chữ người.
_BANG_DUNG_LAI = frozenset({"drug_catalog", "thuoc_quy_doi", "drug_ma_vach"})


async def _dung_lai(
    conn: asyncpg.Connection, bang: str, dong_json: str, clinic_id: str
) -> int:
    """Chèn lại các dòng đã chụp (mảng JSON) vào `bang`, đúng phòng khám.

    Bỏ cột sinh tự động (`GENERATED`, vd `ma_chuan` của mã vạch) — Postgres tự
    tính lại. Trả số dòng đã chèn."""
    assert bang in _BANG_DUNG_LAI
    cot = await conn.fetchval(
        "SELECT string_agg(format('%I', attname), ', ' ORDER BY attnum)"
        "  FROM pg_attribute WHERE attrelid = $1::regclass AND attnum > 0"
        "   AND NOT attisdropped AND attgenerated = ''",
        f"public.{bang}",
    )
    kq = await conn.execute(
        f"INSERT INTO public.{bang} ({cot}) SELECT {cot}"
        f"  FROM jsonb_populate_recordset(NULL::public.{bang}, $1::jsonb) r"
        " WHERE r.clinic_id = $2::uuid",
        dong_json,
        clinic_id,
    )
    return int(str(kq).rsplit(" ", 1)[-1])


async def khoi_phuc(
    pool: asyncpg.Pool, *, identity: StaffIdentity, ban_luu_id: str
) -> dict[str, Any]:
    """Dựng lại thuốc + dòng định nghĩa từ bản lưu (một giao dịch)."""
    async with pool.acquire() as conn, conn.transaction():
        b = await conn.fetchrow(
            "SELECT drug_catalog_id::text, ten, ban_chup::text, quy_doi::text,"
            "       ma_vach::text, khoi_phuc_luc"
            "  FROM public.drug_catalog_da_xoa"
            " WHERE clinic_id = $1::uuid AND id = $2::uuid FOR UPDATE",
            identity.clinic_id,
            ban_luu_id,
        )
        if b is None:
            raise NotFoundError("Không thấy bản lưu thuốc đã xoá này.")
        if b["khoi_phuc_luc"] is not None:
            raise ConflictError(f"“{b['ten']}” đã được khôi phục rồi.")
        try:
            async with conn.transaction():
                so = await _dung_lai(
                    conn, "drug_catalog", f"[{b['ban_chup']}]", identity.clinic_id
                )
                if so != 1:
                    raise NotFoundError("Bản lưu không thuộc phòng khám này.")
                await _dung_lai(conn, "thuoc_quy_doi", b["quy_doi"], identity.clinic_id)
                await _dung_lai(conn, "drug_ma_vach", b["ma_vach"], identity.clinic_id)
        except asyncpg.UniqueViolationError:
            raise ConflictError(
                f"Không khôi phục được “{b['ten']}”: danh mục đã có thuốc trùng tên"
                " hoặc mã vạch từ lúc xoá — đổi tên / gỡ mã thuốc kia trước."
            ) from None
        await conn.execute(
            "UPDATE public.drug_catalog_da_xoa"
            "   SET khoi_phuc_luc = now(), khoi_phuc_boi = $3::uuid"
            " WHERE clinic_id = $1::uuid AND id = $2::uuid",
            identity.clinic_id,
            ban_luu_id,
            identity.staff_id,
        )
        await ghi_nhat_ky(
            conn,
            identity=identity,
            event_type="pharmacy.drug_restored",
            aggregate_type="drug_catalog",
            aggregate_id=b["drug_catalog_id"],
            payload={"ten": b["ten"], "ban_luu_id": ban_luu_id},
        )
    return {"id": b["drug_catalog_id"], "ten": b["ten"], "khoi_phuc": True}


__all__ = ["danh_sach_da_xoa", "khoi_phuc"]
