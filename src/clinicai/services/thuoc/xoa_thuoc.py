"""Nút Xoá trong form Sửa của Danh mục thuốc (Tuyền chốt 26/11/2026, mục 5 + 15).

Luật: chỉ xoá THẬT khi thuốc chưa từng được dùng ở đâu. "Dùng" = có bất kỳ dòng
nào ở bảng có khoá ngoại tới `drug_catalog` (đơn, lô, phiếu kho, kiểm kê, quy
đổi đơn vị, mã vạch, hoá đơn, chờ gán lô…). Danh sách bảng ĐỌC TỪ Postgres
(`pg_constraint`) chứ không viết tay: thêm bảng mới trỏ tới thuốc là tự được đếm.
Khoá ngoại `ON DELETE RESTRICT` vẫn là chốt cuối; khoá `SET NULL` (phụ thu kèm
dịch vụ) thì chỉ có bước đếm này giữ — nên đếm cả nó.

Đã có lịch sử → không xoá, màn đổi nút thành "Tắt" (giữ thuốc cho đơn cũ). Xoá
ghi nhật ký (`pharmacy.drug_deleted`, cùng sổ với đổi giá thuốc): ai, lúc nào,
tên + mã hàng của thuốc đã xoá.

Tranh chấp: khoá dòng thuốc `FOR UPDATE` trước khi đếm — một dòng mới trỏ tới
thuốc (khoá ngoại cần khoá KEY SHARE trên dòng thuốc) phải chờ; nó đã kịp ghi
trước thì bước đếm thấy.
"""

from __future__ import annotations

from typing import Any

import asyncpg

from clinicai.api.exceptions import ConflictError, NotFoundError
from clinicai.api.identity import StaffIdentity
from clinicai.services.pharmacy_service import ghi_nhat_ky

#: Tên bảng → chữ cho người đọc. Bảng chưa có ở đây hiện tên bảng thô.
NHAN_BANG: dict[str, str] = {
    "prescription": "dòng đơn thuốc",
    "drug_batch": "lô thuốc",
    "thuoc_quy_doi": "đơn vị quy đổi",
    "kiem_ke_ca_dong": "dòng kiểm kê ca",
    "phieu_kho_dong": "dòng phiếu kho",
    "drug_ma_vach": "mã vạch",
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


async def dem_dung_thuoc(
    conn: asyncpg.Connection, clinic_id: str, thuoc_id: str
) -> list[dict[str, Any]]:
    """Mỗi bảng đang trỏ tới thuốc: [{bang, nhan, so}]. Rỗng = chưa từng dùng.

    Người gọi đã xác nhận thuốc thuộc `clinic_id` (mã thuốc là duy nhất toàn hệ
    thống, nên đếm theo mã là đủ — không cần lọc phòng khám ở từng bảng)."""
    ra: list[dict[str, Any]] = []
    for fk in await conn.fetch(_KHOA_NGOAI_SQL):
        # Tên bảng / cột lấy từ pg_catalog và đã được `format(%I)` bọc — không
        # có chữ người dùng nào trong câu SQL động này.
        so = await conn.fetchval(
            f"SELECT count(*) FROM {fk['bang']} WHERE {fk['cot']} = $1::uuid",
            thuoc_id,
        )
        if so:
            ten = str(fk["ten_bang"])
            ra.append({"bang": ten, "nhan": NHAN_BANG.get(ten, ten), "so": int(so)})
    return ra


def cau_da_dung(dung: list[dict[str, Any]]) -> str:
    ds = ", ".join(f"{d['so']} {d['nhan']}" for d in dung)
    return (
        f"Thuốc đã có lịch sử ({ds}) — không xoá được, chỉ tắt được "
        "(đơn cũ vẫn giữ thuốc này)."
    )


async def _khoa_thuoc_de_xoa(
    conn: asyncpg.Connection, clinic_id: str, thuoc_id: str
) -> asyncpg.Record:
    r = await conn.fetchrow(
        "SELECT id::text, name_raw, ma_hang FROM public.drug_catalog"
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


async def xoa_thuoc(
    pool: asyncpg.Pool, *, identity: StaffIdentity, thuoc_id: str
) -> dict[str, Any]:
    """Xoá thật thuốc chưa từng dùng; đã dùng → 409 kèm câu "chỉ tắt được"."""
    async with pool.acquire() as conn, conn.transaction():
        r = await _khoa_thuoc_de_xoa(conn, identity.clinic_id, thuoc_id)
        dung = await dem_dung_thuoc(conn, identity.clinic_id, thuoc_id)
        if dung:
            raise ConflictError(cau_da_dung(dung))
        try:
            async with conn.transaction():
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
            payload={"ten": r["name_raw"], "ma_hang": r["ma_hang"]},
        )
    return {"id": thuoc_id, "da_xoa": True, "ten": r["name_raw"]}


__all__ = ["NHAN_BANG", "cau_da_dung", "dem_dung_thuoc", "thuoc_xoa_duoc", "xoa_thuoc"]
