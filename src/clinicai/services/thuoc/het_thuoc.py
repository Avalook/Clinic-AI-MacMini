"""Ngày dự tính dùng hết thuốc của một lượt — cho quầy thu thuốc và hoá đơn thuốc in
(Tuyền 26/11: "hiện cả ở thu ngân thuốc … thêm 1 nút in ngày dự tính uống hết thuốc lên
hoá đơn").

Đọc các dòng đơn HIỆN HÀNH của lượt (`prescription.removed_at IS NULL`): số lượng + đơn
vị tách từ `quantity` ("2 hộp"), cách dùng là phần sau " — " của `dosage_instructions`
("Uống — Ngày 2 lần, mỗi lần 1 viên"). Tính bằng đúng hàm của màn kê đơn
(`cach_dung_db.tinh_don`) — không có công thức thứ hai. Chỉ trả dòng tính được.
"""

from __future__ import annotations

import re
from typing import Any

import asyncpg

from clinicai.api.exceptions import NotFoundError
from clinicai.api.identity import StaffIdentity
from clinicai.services.thuoc import cach_dung_db

_SO_DON_VI = re.compile(r"^\s*([0-9]+(?:[.,][0-9]+)?)\s*(.*?)\s*$")
NOI = " — "


def tach_so_luong(quantity: Any) -> tuple[str, str]:
    """ "2 hộp" → ("2", "hộp"); "10" → ("10", ""); rác → ("", "")."""
    m = _SO_DON_VI.match(str(quantity or ""))
    return (m[1], m[2]) if m else ("", "")


def cach_dung_cua_dong(dosage: Any) -> str:
    chu = str(dosage or "")
    return chu.split(NOI, 1)[1] if NOI in chu else chu


async def _luot_cua_phieu(conn: asyncpg.Connection, cid: str, phieu_id: str) -> str:
    v = await conn.fetchval(
        "SELECT visit_id::text FROM public.payment_cycle"
        " WHERE clinic_id = $1::uuid AND payment_cycle_id = $2::uuid",
        cid,
        phieu_id,
    )
    if v is None:
        raise NotFoundError("Không tìm thấy phiếu thu.")
    return str(v)


async def ngay_het_thuoc_cua_luot(
    pool: asyncpg.Pool,
    *,
    identity: StaffIdentity,
    visit_id: str | None = None,
    phieu_id: str | None = None,
) -> list[dict[str, Any]]:
    """[{ten, so_luong, so_ngay, ngay_het}] theo thứ tự kê. Người gọi đã gác quyền."""
    cid = identity.clinic_id
    async with pool.acquire() as conn:
        if visit_id is None and phieu_id is not None:
            visit_id = await _luot_cua_phieu(conn, cid, phieu_id)
        rows = await conn.fetch(
            "SELECT drug_catalog_id::text AS thuoc, drug_name_raw AS ten, quantity,"
            "       dosage_instructions"
            "  FROM public.prescription"
            " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid AND removed_at IS NULL"
            " ORDER BY created_at, id",
            cid,
            visit_id,
        )
    if not rows:
        return []
    dong = []
    for r in rows:
        sl, dv = tach_so_luong(r["quantity"])
        dong.append(
            {
                "drug_catalog_id": r["thuoc"],
                "so_luong": sl,
                "don_vi": dv,
                "chu": cach_dung_cua_dong(r["dosage_instructions"]),
            }
        )
    kq = await cach_dung_db.tinh_don(
        pool,
        identity=identity,
        visit_id=visit_id,
        dong=dong,
        kinh_lan_cuoi=None,
        chu_ky=None,
        da_gac_quyen=True,
    )
    return [
        {"ten": r["ten"], "so_luong": str(r["quantity"] or ""), **n}
        for r, k in zip(rows, kq["dong"], strict=True)
        if (n := _ngay_dung_cua_dong(k)) is not None
    ]


def _ngay_dung_cua_dong(k: dict[str, Any]) -> dict[str, Any] | None:
    """Kết quả một dòng → {so_ngay, ngay_het, bat_dau?}. Thuốc theo chu kỳ kinh lấy
    ngày ước tính (cần kinh lần cuối trên phiếu); chưa tính được thì None."""
    if not k["tinh_duoc"]:
        return None
    if k.get("uoc_tinh"):
        u = k["uoc_tinh"]
        return {"so_ngay": k["so_ngay"], "ngay_het": u["het"], "bat_dau": u["bat_dau"]}
    if k["ngay_het"] is None:
        return None
    return {"so_ngay": k["so_ngay"], "ngay_het": k["ngay_het"], "bat_dau": None}


async def ngay_het_tung_dong(
    pool: asyncpg.Pool,
    *,
    identity: StaffIdentity,
    visit_id: str,
    dong: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Quầy gửi dòng đang bán (số quầy nhập / số kê, đơn vị đang chọn, chữ cách dùng)
    → {id dòng: {so_ngay, ngay_het}}, chỉ dòng tính được. Người gọi đã gác quyền."""
    if not dong:
        return {}
    kq = await cach_dung_db.tinh_don(
        pool,
        identity=identity,
        visit_id=visit_id,
        dong=[{**d, "chu": cach_dung_cua_dong(d.get("chu"))} for d in dong],
        kinh_lan_cuoi=None,
        chu_ky=None,
        da_gac_quyen=True,
    )
    return {
        str(d["id"]): n
        for d, k in zip(dong, kq["dong"], strict=True)
        if (n := _ngay_dung_cua_dong(k)) is not None
    }


__all__ = [
    "cach_dung_cua_dong",
    "ngay_het_thuoc_cua_luot",
    "ngay_het_tung_dong",
    "tach_so_luong",
]
