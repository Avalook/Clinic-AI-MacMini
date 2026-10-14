"""Mã vạch thuốc (G3b): tra một chuỗi quét, gắn / gỡ mã, dữ liệu in tem lô.

Một chuỗi quét có thể là: tem lô của mình (`LT00000012`), mã vạch nhà sản xuất
đã gắn cho một thuốc, mã vuông GS1 (GTIN + số lô + hạn), hoặc mã hàng KiotViet.
Tra chỉ ĐỌC; chọn lô để bán/giao vẫn đi qua `phan_lo` / `cap_phat` (có chặn lô
hết hạn ở máy chủ) — quét chỉ làm việc chọn nhanh hơn, không mở lối mới.

Đầu vào rác → trả `{"loai": "rong"}` / "la", không ném (luật repo); ghi mã
rác → ValidationError tiếng Việt, không lưu gì.
"""

from __future__ import annotations

import re
from typing import Any

import asyncpg

from clinicai.api.exceptions import ConflictError, NotFoundError, ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.core.clock import hom_nay_vn
from clinicai.core.gs1 import chuan_ma, tach_gs1

MA_TOI_DA = 64
MA_TOI_THIEU = 4
TEM_TOI_DA = 200
_TEM = re.compile(r"^LT[0-9]{8}$")
_NGUON = ("tay", "quet", "gs1")

# Lô đã huỷ hết hạn: có DISCARD "expired_batch" mà chưa bị hoàn tác.
_DA_HUY = """
    EXISTS (SELECT 1 FROM public.inventory_txn t
             WHERE t.clinic_id = b.clinic_id AND t.drug_batch_id = b.id
               AND t.txn_type = 'DISCARD' AND t.ref_type = 'expired_batch'
               AND NOT EXISTS (SELECT 1 FROM public.inventory_txn u
                                WHERE u.clinic_id = t.clinic_id
                                  AND u.ref_type = 'discard_undo'
                                  AND u.ref_id = t.id))
"""


def _sach(ma: Any) -> str:
    """Chuỗi quét → bỏ khoảng trắng thừa; không phải chữ / quá dài → ''."""
    if not isinstance(ma, str):
        return ""
    chu = ma.strip()
    # NUL / ký tự không mã hoá được thì Postgres từ chối cả câu lệnh (500).
    if "\x00" in chu or not 0 < len(chu) <= 256:
        return ""
    try:
        chu.encode("utf-8")
    except UnicodeEncodeError:
        return ""
    return chu


def trang_thai_lo(
    *, het_han: bool, da_huy: bool, ton: Any, khac_co_so: bool = False
) -> str:
    if khac_co_so:
        return "khac_co_so"
    if da_huy:
        return "da_huy"
    if het_han:
        return "het_han"
    return "het_ton" if not ton or ton <= 0 else "ok"


_CAU_LO = f"""
    SELECT b.id::text, b.batch_code, b.expiry_date, b.quantity_on_hand, b.unit,
           b.ma_tem, b.drug_catalog_id::text, b.location_id::text AS co_so_id,
           c.name_base AS ten_thuoc, {_DA_HUY} AS da_huy
      FROM public.drug_batch b
      JOIN public.drug_catalog c
        ON c.id = b.drug_catalog_id AND c.clinic_id = b.clinic_id
"""


def _lo_ra(r: Any, identity: StaffIdentity) -> dict[str, Any]:
    han = r["expiry_date"]
    return {
        "id": r["id"],
        "batch_code": r["batch_code"],
        "expiry_date": han.isoformat() if han else None,
        "quantity_on_hand": r["quantity_on_hand"],
        "unit": r["unit"],
        "ma_tem": r["ma_tem"],
        "drug_catalog_id": r["drug_catalog_id"],
        "ten_thuoc": r["ten_thuoc"],
        "trang_thai": trang_thai_lo(
            het_han=han is not None and han < hom_nay_vn(),
            da_huy=bool(r["da_huy"]),
            ton=r["quantity_on_hand"],
            khac_co_so=r["co_so_id"] != str(identity.location_id),
        ),
    }


async def goi_y_lo(
    conn: asyncpg.Connection, identity: StaffIdentity, drug_catalog_id: str
) -> list[dict[str, Any]]:
    """Lô còn bán được của một thuốc ở kho cơ sở đang làm, FEFO: hạn gần nhất
    trước, lô chưa có hạn xếp CUỐI. Không có lô hết hạn / đã huỷ / tồn 0."""
    rows = await conn.fetch(
        _CAU_LO
        + """
     WHERE b.clinic_id = $1::uuid AND b.location_id = $2::uuid
       AND b.drug_catalog_id = $3::uuid AND b.quantity_on_hand > 0
       AND (b.expiry_date IS NULL OR b.expiry_date >= $4)
     ORDER BY b.expiry_date NULLS LAST, b.batch_code
        """,
        identity.clinic_id,
        identity.location_id,
        drug_catalog_id,
        hom_nay_vn(),
    )
    lo_ra = (_lo_ra(r, identity) for r in rows)
    return [lo for lo in lo_ra if lo["trang_thai"] == "ok"]


async def _thuoc_theo_ma(
    conn: asyncpg.Connection, identity: StaffIdentity, ma: str
) -> dict[str, Any] | None:
    chuan = chuan_ma(ma)
    r: Any = await conn.fetchrow(
        """
        SELECT c.id::text AS id, c.name_base AS ten, 'ma_vach' AS nguon,
               v.id::text AS ma_vach_id
          FROM public.drug_ma_vach v
          JOIN public.drug_catalog c
            ON c.id = v.drug_catalog_id AND c.clinic_id = v.clinic_id
         WHERE v.clinic_id = $1::uuid AND v.ma_chuan = $2
        """,
        identity.clinic_id,
        chuan,
    )
    if r is None:
        # Mã hàng KiotViet in trên tem kệ cũ cũng quét ra thuốc.
        con = await conn.fetch(
            """
            SELECT id::text AS id, name_base AS ten, 'ma_hang' AS nguon
              FROM public.drug_catalog
             WHERE clinic_id = $1::uuid AND upper(btrim(ma_hang)) = upper($2)
             LIMIT 2
            """,
            identity.clinic_id,
            ma,
        )
        # Hai thuốc cùng mã hàng thì KHÔNG đoán — coi như mã lạ để người chọn.
        r = con[0] if len(con) == 1 else None
    return None if r is None else dict(r)


async def tra_ma(
    pool: asyncpg.Pool, *, identity: StaffIdentity, ma: Any
) -> dict[str, Any]:
    """Một chuỗi quét → `loai`:
    `tem` (đúng một lô; có `trang_thai`), `thuoc` (thuốc + `goi_y_lo` FEFO; nếu
    mã vuông có số lô trùng một lô thì kèm `lo_theo_ma`), `la` (chưa gắn —
    kèm `gs1` nếu là mã vuông để hộp gắn mã điền sẵn), `rong` (không đọc được)."""
    chu = _sach(ma)
    if not chu:
        return {"loai": "rong"}
    async with pool.acquire() as conn:
        if _TEM.match(chu.upper()):
            r = await conn.fetchrow(
                _CAU_LO + " WHERE b.clinic_id = $1::uuid AND b.ma_tem = $2",
                identity.clinic_id,
                chu.upper(),
            )
            if r is None:
                return {"loai": "la", "ma": chu.upper()}
            return {"loai": "tem", "lo": _lo_ra(r, identity)}
        gs1 = tach_gs1(chu)
        tra = gs1.gtin if gs1 else chu
        thuoc = await _thuoc_theo_ma(conn, identity, tra)
        if thuoc is None:
            la: dict[str, Any] = {"loai": "la", "ma": tra}
            if gs1:
                la["gs1"] = {
                    "gtin": gs1.gtin,
                    "so_lo": gs1.so_lo,
                    "han": gs1.han.isoformat() if gs1.han else None,
                }
            return la
        kq: dict[str, Any] = {
            "loai": "thuoc",
            "thuoc": {"id": thuoc["id"], "ten": thuoc["ten"]},
            "nguon": thuoc["nguon"],
            "ma_vach_id": thuoc.get("ma_vach_id"),
            "goi_y_lo": await goi_y_lo(conn, identity, thuoc["id"]),
        }
        if gs1:
            kq["gs1"] = {
                "gtin": gs1.gtin,
                "so_lo": gs1.so_lo,
                "han": gs1.han.isoformat() if gs1.han else None,
            }
            if gs1.so_lo:
                lo = await conn.fetchrow(
                    _CAU_LO
                    + " WHERE b.clinic_id = $1::uuid AND b.location_id = $2::uuid"
                    " AND b.drug_catalog_id = $3::uuid AND b.batch_code = $4",
                    identity.clinic_id,
                    identity.location_id,
                    thuoc["id"],
                    gs1.so_lo,
                )
                if lo is not None:
                    kq["lo_theo_ma"] = _lo_ra(lo, identity)
        return kq


async def gan_ma(
    pool: asyncpg.Pool,
    *,
    identity: StaffIdentity,
    drug_catalog_id: str,
    ma: Any,
    nguon: str = "quet",
) -> dict[str, Any]:
    """Gắn một mã vạch cho thuốc. Mã đã thuộc CHÍNH thuốc này → ok (gửi lại
    không lỗi); thuộc thuốc khác → 409 nêu tên thuốc đó."""
    from clinicai.services.pharmacy_service import ghi_nhat_ky

    chu = _sach(ma)
    gs1 = tach_gs1(chu) if chu else None
    if gs1:
        chu = gs1.gtin
        nguon = "gs1"
    if not (MA_TOI_THIEU <= len(chu) <= MA_TOI_DA) or any(c.isspace() for c in chu):
        raise ValidationError(
            f"Mã vạch phải dài {MA_TOI_THIEU}–{MA_TOI_DA} ký tự, không có khoảng trắng."
        )
    if _TEM.match(chu.upper()):
        raise ValidationError(
            "Đây là mã tem lô của phòng khám, không gắn cho thuốc được."
        )
    if nguon not in _NGUON:
        nguon = "quet"
    # Mã in sẵn thường là EAN-13; lưu đúng như người dùng quét/gõ, so khớp ở
    # `ma_chuan` (đệm 0) nên GTIN-14 của mã vuông cũng khớp.
    if gs1 and gs1.gtin.startswith("0"):
        chu = gs1.gtin[1:]
    async with pool.acquire() as conn, conn.transaction():
        thuoc = await conn.fetchrow(
            "SELECT id::text, name_base FROM public.drug_catalog"
            " WHERE id = $1::uuid AND clinic_id = $2::uuid FOR SHARE",
            drug_catalog_id,
            identity.clinic_id,
        )
        if thuoc is None:
            raise NotFoundError("Không tìm thấy thuốc này trong danh mục.")
        cu = await conn.fetchrow(
            """
            SELECT v.id::text, v.drug_catalog_id::text, c.name_base
              FROM public.drug_ma_vach v
              JOIN public.drug_catalog c
                ON c.id = v.drug_catalog_id AND c.clinic_id = v.clinic_id
             WHERE v.clinic_id = $1::uuid AND v.ma_chuan = $2
            """,
            identity.clinic_id,
            chuan_ma(chu),
        )
        if cu is not None:
            if cu["drug_catalog_id"] == str(drug_catalog_id):
                return {"ok": True, "id": cu["id"], "gui_lai": True}
            raise ConflictError(
                f"Mã này đã gắn cho thuốc “{cu['name_base']}”. Gỡ mã ở thuốc đó "
                "trước nếu gắn nhầm."
            )
        try:
            vid = await conn.fetchval(
                "INSERT INTO public.drug_ma_vach"
                " (clinic_id, drug_catalog_id, ma, nguon, tao_boi)"
                " VALUES ($1::uuid, $2::uuid, $3, $4, $5::uuid) RETURNING id::text",
                identity.clinic_id,
                drug_catalog_id,
                chu,
                nguon,
                identity.staff_id,
            )
        except asyncpg.UniqueViolationError as exc:
            # Hai người gắn cùng một mã cùng lúc: người sau nhận 409, không 500.
            raise ConflictError(
                "Mã này vừa được gắn cho một thuốc khác — quét lại để xem."
            ) from exc
        await ghi_nhat_ky(
            conn,
            identity=identity,
            event_type="pharmacy.ma_vach_gan",
            aggregate_type="drug_catalog",
            aggregate_id=drug_catalog_id,
            payload={"ma": chu, "nguon": nguon, "ten_thuoc": thuoc["name_base"]},
        )
    return {"ok": True, "id": vid, "gui_lai": False}


async def go_ma(
    pool: asyncpg.Pool, *, identity: StaffIdentity, ma_vach_id: str
) -> dict[str, Any]:
    """Gỡ một mã gắn nhầm (hoàn tác của `gan_ma`) — ghi nhật ký ai gỡ, mã gì."""
    from clinicai.services.pharmacy_service import ghi_nhat_ky

    async with pool.acquire() as conn, conn.transaction():
        r = await conn.fetchrow(
            "DELETE FROM public.drug_ma_vach"
            " WHERE id = $1::uuid AND clinic_id = $2::uuid"
            " RETURNING drug_catalog_id::text, ma",
            ma_vach_id,
            identity.clinic_id,
        )
        if r is None:
            return {"ok": True, "gui_lai": True}
        await ghi_nhat_ky(
            conn,
            identity=identity,
            event_type="pharmacy.ma_vach_go",
            aggregate_type="drug_catalog",
            aggregate_id=r["drug_catalog_id"],
            payload={"ma": r["ma"]},
        )
    return {"ok": True, "gui_lai": False}


async def ma_cua_thuoc(
    pool: asyncpg.Pool, *, identity: StaffIdentity, drug_catalog_id: str
) -> list[dict[str, Any]]:
    rows = await pool.fetch(
        "SELECT id::text, ma, nguon, tao_luc FROM public.drug_ma_vach"
        " WHERE clinic_id = $1::uuid AND drug_catalog_id = $2::uuid"
        " ORDER BY tao_luc, ma",
        identity.clinic_id,
        drug_catalog_id,
    )
    return [dict(r) for r in rows]


async def du_lieu_tem(
    pool: asyncpg.Pool,
    *,
    identity: StaffIdentity,
    lo_ids: list[str] | None = None,
    phieu_kho_id: str | None = None,
) -> list[dict[str, Any]]:
    """Dữ liệu in tem: các lô (theo danh sách id hoặc theo phiếu nhập) của kho
    cơ sở đang làm. Tối đa `TEM_TOI_DA` tem một lần. Id rác bị bỏ qua."""
    async with pool.acquire() as conn:
        if phieu_kho_id:
            rows = await conn.fetch(
                _CAU_LO + " JOIN public.phieu_kho_dong d"
                "   ON d.drug_batch_id = b.id AND d.clinic_id = b.clinic_id"
                " WHERE b.clinic_id = $1::uuid AND b.location_id = $2::uuid"
                "   AND d.phieu_kho_id = $3::uuid AND d.loai = 'NHAP'"
                " ORDER BY d.stt LIMIT $4",
                identity.clinic_id,
                identity.location_id,
                phieu_kho_id,
                TEM_TOI_DA,
            )
        else:
            rows = await conn.fetch(
                _CAU_LO + " WHERE b.clinic_id = $1::uuid AND b.location_id = $2::uuid"
                "   AND b.id = ANY($3::uuid[])"
                " ORDER BY c.name_base, b.batch_code LIMIT $4",
                identity.clinic_id,
                identity.location_id,
                (lo_ids or [])[:TEM_TOI_DA],
                TEM_TOI_DA,
            )
    return [_lo_ra(r, identity) for r in rows]
