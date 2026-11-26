"""Nút Xoá trong form Sửa của Danh mục thuốc (Tuyền chốt 26/11/2026, mục 5 + 15).

Luật: chỉ xoá khi thuốc chưa từng được DÙNG ở đâu. "Dùng" = có dòng ở bất kỳ bảng
nào có khoá ngoại tới `drug_catalog` (đơn, lô, phiếu kho, kiểm kê, hoá đơn, chờ
gán lô, phụ thu…), TRỪ hai bảng định nghĩa đi kèm thuốc (`DONG_DINH_NGHIA`: đơn vị
quy đổi, mã vạch) — chúng được chụp và xoá cùng thuốc. Danh sách bảng ĐỌC TỪ
Postgres (`pg_constraint`) chứ không viết tay: thêm bảng mới trỏ tới thuốc là tự
được đếm. Khoá ngoại `ON DELETE RESTRICT` vẫn là chốt cuối; khoá `SET NULL` (phụ
thu kèm dịch vụ) thì chỉ có bước đếm này giữ — nên đếm cả nó.

"Lưu vào đâu đó trước đã rồi xoá" (Tuyền 26/11): trước khi xoá, chụp NGUYÊN dòng
thuốc + dòng định nghĩa vào `drug_catalog_da_xoa` (ai, lúc nào, lý do). Hoàn tác =
`khoi_phuc_thuoc.khoi_phuc` dựng lại đúng các dòng ấy. Đã có lịch sử → không
xoá, màn đổi nút thành "Tắt" (giữ thuốc cho đơn cũ).

Tranh chấp: khoá dòng thuốc `FOR UPDATE` trước khi đếm — một dòng mới trỏ tới
thuốc (khoá ngoại cần khoá KEY SHARE trên dòng thuốc) phải chờ; nó đã kịp ghi
trước thì bước đếm thấy.
"""

from __future__ import annotations

from typing import Any

import asyncpg

from clinicai.api.exceptions import ConflictError, NotFoundError, ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.services.pharmacy_service import ghi_nhat_ky

#: Bảng định nghĩa của chính thuốc — chụp + xoá cùng thuốc, không tính là "dùng".
DONG_DINH_NGHIA = ("thuoc_quy_doi", "drug_ma_vach")

#: Tên bảng → chữ cho người đọc. Bảng chưa có ở đây hiện tên bảng thô.
NHAN_BANG: dict[str, str] = {
    "prescription": "dòng đơn thuốc",
    "drug_batch": "lô thuốc",
    "kiem_ke_ca_dong": "dòng kiểm kê ca",
    "phieu_kho_dong": "dòng phiếu kho",
    "thuoc_giao_chua_gan_lo": "lần giao chờ gán lô",
    "prescription_allocation": "lần phân lô",
    "phu_thu_mau": "mẫu phụ thu kèm dịch vụ",
}

_KHOA_NGOAI_SQL = """
SELECT DISTINCT format('%I.%I', n.nspname, r.relname) AS bang, r.relname AS ten_bang,
       format('%I', a.attname) AS cot
  FROM pg_constraint c
  JOIN pg_class r ON r.oid = c.conrelid
  JOIN pg_namespace n ON n.oid = r.relnamespace
  JOIN LATERAL unnest(c.conkey, c.confkey) AS k(con, cha) ON true
  JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k.con
  JOIN pg_attribute p ON p.attrelid = c.confrelid AND p.attnum = k.cha
 WHERE c.contype = 'f' AND c.confrelid = 'public.drug_catalog'::regclass
   AND p.attname = 'id'
 ORDER BY 2, 3
"""

LY_DO_TOI_DA = 500


async def dem_dung_thuoc(
    conn: asyncpg.Connection, clinic_id: str, thuoc_id: str
) -> list[dict[str, Any]]:
    """Mỗi bảng đang DÙNG thuốc: [{bang, nhan, so}]. Rỗng = chưa từng dùng.

    Người gọi đã xác nhận thuốc thuộc `clinic_id` (mã thuốc là duy nhất toàn hệ
    thống, nên đếm theo mã là đủ — không cần lọc phòng khám ở từng bảng)."""
    ra: list[dict[str, Any]] = []
    for fk in await conn.fetch(_KHOA_NGOAI_SQL):
        ten = str(fk["ten_bang"])
        if ten in DONG_DINH_NGHIA:
            continue
        # Tên bảng / cột lấy từ pg_catalog và đã được `format(%I)` bọc — không
        # có chữ người dùng nào trong câu SQL động này.
        so = await conn.fetchval(
            f"SELECT count(*) FROM {fk['bang']} WHERE {fk['cot']} = $1::uuid",
            thuoc_id,
        )
        if so:
            ra.append({"bang": ten, "nhan": NHAN_BANG.get(ten, ten), "so": int(so)})
    return ra


def cau_da_dung(dung: list[dict[str, Any]]) -> str:
    ds = ", ".join(f"{d['so']} {d['nhan']}" for d in dung)
    return (
        f"Thuốc đã có lịch sử ({ds}) — không xoá được, chỉ tắt được "
        "(đơn cũ vẫn giữ thuốc này)."
    )


def doc_ly_do_xoa(ly_do: Any) -> str:
    """Lý do bắt buộc, gọn dấu cách; rỗng / dài quá → 422 (không cắt im lặng)."""
    gon = " ".join(str(ly_do or "").split())
    if not gon:
        raise ValidationError("Ghi lý do xoá thuốc.")
    if len(gon) > LY_DO_TOI_DA:
        raise ValidationError(f"Lý do xoá dài quá {LY_DO_TOI_DA} ký tự.")
    return gon


async def _khoa_thuoc_de_xoa(
    conn: asyncpg.Connection, clinic_id: str, thuoc_id: str
) -> asyncpg.Record:
    r = await conn.fetchrow(
        "SELECT id::text, name_raw, ma_hang, to_jsonb(c.*)::text AS ban_chup"
        "  FROM public.drug_catalog c"
        " WHERE clinic_id = $1::uuid AND id = $2::uuid FOR UPDATE",
        clinic_id,
        thuoc_id,
    )
    if r is None:
        raise NotFoundError("Không tìm thấy thuốc này trong danh mục.")
    return r


async def thuoc_xoa_duoc(
    pool: asyncpg.Pool, *, identity: StaffIdentity, thuoc_id: str
) -> dict[str, Any]:
    """Cho form Sửa: nút là "Xoá" hay "Tắt", kèm câu vì sao."""
    async with pool.acquire() as conn, conn.transaction():
        await _khoa_thuoc_de_xoa(conn, identity.clinic_id, thuoc_id)
        dung = await dem_dung_thuoc(conn, identity.clinic_id, thuoc_id)
    return {
        "xoa_duoc": not dung,
        "ly_do": cau_da_dung(dung) if dung else None,
        "da_dung": dung,
    }


_CHUP_DONG_SQL = (
    "SELECT coalesce(jsonb_agg(to_jsonb(x.*)), '[]'::jsonb)::text"
    "  FROM public.{bang} x"
    " WHERE x.clinic_id = $1::uuid AND x.drug_catalog_id = $2::uuid"
)


async def xoa_thuoc(
    pool: asyncpg.Pool, *, identity: StaffIdentity, thuoc_id: str, ly_do: Any
) -> dict[str, Any]:
    """Chụp thuốc + dòng định nghĩa vào bản lưu, rồi xoá. Đã dùng → 409."""
    ly = doc_ly_do_xoa(ly_do)
    async with pool.acquire() as conn, conn.transaction():
        r = await _khoa_thuoc_de_xoa(conn, identity.clinic_id, thuoc_id)
        dung = await dem_dung_thuoc(conn, identity.clinic_id, thuoc_id)
        if dung:
            raise ConflictError(cau_da_dung(dung))
        phu = {
            bang: await conn.fetchval(
                _CHUP_DONG_SQL.format(bang=bang), identity.clinic_id, thuoc_id
            )
            for bang in DONG_DINH_NGHIA
        }
        luu = await conn.fetchval(
            """
            INSERT INTO public.drug_catalog_da_xoa
                (clinic_id, drug_catalog_id, ten, ban_chup, quy_doi, ma_vach,
                 ly_do, xoa_boi)
            VALUES ($1::uuid, $2::uuid, $3, $4::jsonb, $5::jsonb, $6::jsonb, $7,
                    $8::uuid)
            RETURNING id::text
            """,
            identity.clinic_id,
            thuoc_id,
            r["name_raw"],
            r["ban_chup"],
            phu["thuoc_quy_doi"],
            phu["drug_ma_vach"],
            ly,
            identity.staff_id,
        )
        try:
            async with conn.transaction():
                for bang in DONG_DINH_NGHIA:
                    await conn.execute(
                        f"DELETE FROM public.{bang} WHERE clinic_id = $1::uuid"
                        " AND drug_catalog_id = $2::uuid",
                        identity.clinic_id,
                        thuoc_id,
                    )
                await conn.execute(
                    "DELETE FROM public.drug_catalog"
                    " WHERE clinic_id = $1::uuid AND id = $2::uuid",
                    identity.clinic_id,
                    thuoc_id,
                )
        except asyncpg.ForeignKeyViolationError:
            raise ConflictError(
                "Thuốc vừa được dùng ở chỗ khác — không xoá được, chỉ tắt được."
            ) from None
        await ghi_nhat_ky(
            conn,
            identity=identity,
            event_type="pharmacy.drug_deleted",
            aggregate_type="drug_catalog",
            aggregate_id=thuoc_id,
            payload={
                "ten": r["name_raw"],
                "ma_hang": r["ma_hang"],
                "ban_luu_id": luu,
                "ly_do": ly,
            },
        )
    return {"id": thuoc_id, "da_xoa": True, "ten": r["name_raw"], "ban_luu_id": luu}


__all__ = [
    "DONG_DINH_NGHIA",
    "NHAN_BANG",
    "cau_da_dung",
    "dem_dung_thuoc",
    "doc_ly_do_xoa",
    "thuoc_xoa_duoc",
    "xoa_thuoc",
]
