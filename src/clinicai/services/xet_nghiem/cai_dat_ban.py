"""Cài đặt bàn XN của một phòng khám (`xet_nghiem_cai_dat`): ngưỡng "đã thu, chưa lấy
mẫu" + công tắc "Hiện mã ống" (Tuyền 09/11/2026). Tách khỏi `doi_tac.py` (trần 400
dòng — cùng cách `gmail_cai_dat.py` giữ mốc Gmail của cùng dòng cài đặt).

Ghi: quyền `config.clinic.manage` (màn Cài đặt → Đối tác, chỉ Quản lý), gọi qua
`cai_dat.CaiDatDoiTac` (một giao dịch + sự kiện).
"""

from __future__ import annotations

from dataclasses import dataclass

import asyncpg

from clinicai.api.exceptions import ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.services.xet_nghiem.o_nhap import doc_so_ngay


@dataclass(frozen=True)
class CaiDatXN:
    """Cài đặt bàn XN. Không có dòng ⇒ mặc định (2 ngày, ẩn mã)."""

    nguong_lay_mau_ngay: int = 2
    #: Tắt (mặc định, Tuyền 09/11): mọi cửa đọc trả `ma_mau = null` — mã vẫn có ở DB.
    hien_ma_ong: bool = False


async def doc_cai_dat(conn: asyncpg.Connection, cid: str) -> CaiDatXN:
    r = await conn.fetchrow(
        "SELECT nguong_lay_mau_ngay, hien_ma_ong FROM public.xet_nghiem_cai_dat"
        " WHERE clinic_id = $1::uuid",
        cid,
    )
    if r is None:
        return CaiDatXN()
    return CaiDatXN(int(r["nguong_lay_mau_ngay"]), bool(r["hien_ma_ong"]))


async def luu_nguong(
    conn: asyncpg.Connection,
    identity: StaffIdentity,
    raw: object,
    hien_ma_ong: bool | None = None,
) -> int:
    """Lưu số ngày cảnh báo + công tắc "Hiện mã ống" (None = giữ nguyên). Không đụng
    mốc Gmail (`gmail_tu_ngay` — `gmail_cai_dat.luu_moc`, cửa riêng)."""
    from clinicai.services.xet_nghiem.doi_tac import _vet  # doi_tac → đây (vòng)

    n = doc_so_ngay(raw, "Số ngày cảnh báo")
    if n is None or not 1 <= n <= 30:
        raise ValidationError("Số ngày cảnh báo: 1–30.")
    hien = await conn.fetchval(
        """
        INSERT INTO public.xet_nghiem_cai_dat
            (clinic_id, nguong_lay_mau_ngay, hien_ma_ong, sua_boi)
        VALUES ($1::uuid, $2, coalesce($3::boolean, false), $4::uuid)
        ON CONFLICT (clinic_id) DO UPDATE
           SET nguong_lay_mau_ngay = EXCLUDED.nguong_lay_mau_ngay,
               hien_ma_ong = coalesce($3::boolean, xet_nghiem_cai_dat.hien_ma_ong),
               sua_luc = now(), sua_boi = EXCLUDED.sua_boi
        RETURNING hien_ma_ong
        """,
        identity.clinic_id,
        n,
        hien_ma_ong,
        identity.staff_id,
    )
    await _vet(
        conn,
        identity,
        "lab.settings_saved",
        "xet_nghiem_cai_dat",
        identity.clinic_id,
        {"nguong_lay_mau_ngay": n, "hien_ma_ong": bool(hien)},
    )
    return n
