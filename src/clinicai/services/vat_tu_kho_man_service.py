"""Màn kho vật tư: nơi chứa, mức tối thiểu, nhắc, danh sách phiếu (chỉ đọc + mức)."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

import asyncpg

from clinicai.api.identity import StaffIdentity
from clinicai.services.danh_muc_dich_vu_service import doc_vat_tu
from clinicai.services.vat_tu_kho_service import (
    _khoa_co_so,
    _so,
    _ton,
    _uuid,
    doc_ton,
)

_GIOI_HAN_MAC_DINH = 50
_GIOI_HAN_TOI_DA = 200


async def doc_canh_bao(
    pool: asyncpg.Pool, *, identity: StaffIdentity
) -> list[dict[str, Any]]:
    """Chỉ những nơi chứa cần nhắc: tồn âm (cần kiểm đếm) hoặc dưới mức tối thiểu."""
    return [r for r in await doc_ton(pool, identity=identity) if r["canh_bao"]]


async def dat_muc_toi_thieu(
    pool: asyncpg.Pool,
    *,
    identity: StaffIdentity,
    vat_tu_id: Any,
    room_id: Any,
    muc: Any,
) -> dict[str, Any]:
    """Đặt mức tối thiểu cho một vật tư ở kho cơ sở (room_id rỗng) hoặc một phòng.

    Chưa từng có sổ ở nơi đó vẫn đặt được (tồn 0 → nhắc luôn); số rác → 422.
    """
    vt = _uuid(vat_tu_id)
    room = _uuid(room_id) if room_id else None
    so = _so(muc, cho_0=True)
    async with pool.acquire() as conn, conn.transaction():
        await _khoa_co_so(conn, identity)
        ton = await _ton(conn, identity, vt, room)
        await conn.execute(
            "UPDATE vat_tu_ton SET ton_toi_thieu=$1, muc_sua_boi=$2::uuid,"
            " muc_sua_luc=now() WHERE id=$3::uuid AND clinic_id=$4::uuid",
            so,
            identity.staff_id,
            ton["id"],
            identity.clinic_id,
        )
    return {"ok": True, "ton_id": ton["id"], "ton_toi_thieu": so}


async def doc_noi_chua(
    pool: asyncpg.Pool, *, identity: StaffIdentity
) -> list[dict[str, Any]]:
    """Kho cơ sở + phòng đang bật + phòng đã tắt NHƯNG còn tồn (để kiểm/trả kho)."""
    rows = await pool.fetch(
        "SELECT r.id::text AS room_id, r.name AS ten, r.is_active AS dang_bat"
        " FROM clinic_room r WHERE r.clinic_id=$1::uuid AND r.location_id=$2::uuid"
        " AND (r.is_active OR EXISTS (SELECT 1 FROM vat_tu_ton t WHERE"
        " t.room_id=r.id AND t.clinic_id=r.clinic_id AND t.so_luong<>0))"
        " ORDER BY r.is_active DESC, r.name, r.id",
        identity.clinic_id,
        identity.location_id,
    )
    return [{"room_id": None, "ten": "Kho cơ sở", "dang_bat": True}] + [
        dict(r) for r in rows
    ]


def _gioi_han(v: Any) -> int:
    try:
        n = int(str(v))
    except (ValueError, TypeError):
        return _GIOI_HAN_MAC_DINH
    return n if 1 <= n <= _GIOI_HAN_TOI_DA else _GIOI_HAN_MAC_DINH


async def doc_phieu(
    pool: asyncpg.Pool, *, identity: StaffIdentity, gioi_han: Any = None
) -> list[dict[str, Any]]:
    """Phiếu gần nhất của cơ sở đang làm, kèm dòng, người lập, đã đảo hay chưa."""
    rows = await pool.fetch(
        "SELECT p.id::text, p.ma_phieu, p.loai, p.tao_luc, p.ghi_chu,"
        " p.tao_boi::text AS nguoi_tao_id, s.full_name AS nguoi_tao,"
        " p.dao_phieu_id::text AS dao_phieu_id,"
        " EXISTS (SELECT 1 FROM vat_tu_phieu d WHERE d.dao_phieu_id=p.id"
        "   AND d.clinic_id=p.clinic_id) AS da_dao,"
        " (SELECT coalesce(jsonb_agg(jsonb_build_object("
        "   'vat_tu_id', x.vat_tu_id::text, 'ten', v.name, 'don_vi', v.don_vi,"
        "   'noi_chua', coalesce(r.name, 'Kho cơ sở'), 'so_luong', x.so_luong,"
        "   'thuc_te', x.thuc_te, 'gia_nhap', x.gia_nhap) ORDER BY x.id), '[]'::jsonb)"
        "   FROM vat_tu_txn x JOIN vat_tu_ton t ON t.id=x.ton_id"
        "   JOIN service_price v ON v.id=x.vat_tu_id"
        "   LEFT JOIN clinic_room r ON r.id=t.room_id"
        "   WHERE x.phieu_id=p.id AND x.clinic_id=p.clinic_id) AS dong"
        " FROM vat_tu_phieu p LEFT JOIN staff s ON s.id=p.tao_boi"
        " WHERE p.clinic_id=$1::uuid AND p.location_id=$2::uuid"
        " ORDER BY p.tao_luc DESC, p.ma_phieu DESC LIMIT $3",
        identity.clinic_id,
        identity.location_id,
        _gioi_han(gioi_han),
    )
    return [{**dict(r), "dong": _json(r["dong"])} for r in rows]


def _json(v: Any) -> list[dict[str, Any]]:
    # Số lượng giữ Decimal, không để json biến thành float.
    if isinstance(v, str):
        return list(json.loads(v, parse_float=Decimal))
    return list(v or [])


async def doc_vat_tu_chon(
    pool: asyncpg.Pool, *, identity: StaffIdentity
) -> list[dict[str, Any]]:
    """Danh mục vật tư để chọn khi lập phiếu (cùng nguồn Bảng giá, kể cả hàng tắt)."""
    async with pool.acquire() as conn:
        return await doc_vat_tu(conn, identity.clinic_id)
