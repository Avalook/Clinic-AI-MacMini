"""Cửa ca trực cho thao tác lâm sàng làm thay bác sĩ.

Tách khỏi ``quyen_theo_lich``: file kia gác người làm dịch vụ trong phòng; cửa
này chỉ gác chuỗi khám/chỉ định/kê đơn/kết quả mang danh bác sĩ phụ trách.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import date

import asyncpg

from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.core.clock import hom_nay_vn
from clinicai.core.exceptions import SafetyGateError
from clinicai.events.emit import pham_vi_lam_thay
from clinicai.services.day_noi import giai_gia_tri


@dataclass(frozen=True)
class CaLam:
    staff_id: str
    room_id: str
    ca: str
    lan: int | None
    bac_si: bool


def _trung_ca(a: str, b: str) -> bool:
    """FULL chạm mọi ca; ca có tên giống nhau chạm nhau."""
    return a == "FULL" or b == "FULL" or a == b


def duoc_lam_thay(
    *,
    nguoi_bam: str,
    bac_si_id: str,
    vai_goc: ClinicRole,
    lich: Sequence[CaLam],
) -> bool:
    """Luật thuần: bác sĩ tự làm trong ngày, hoặc TKYK/ĐD cùng ca/phòng/làn."""
    cua_bs = [d for d in lich if d.staff_id == bac_si_id and d.bac_si]
    if not cua_bs:
        return False
    if nguoi_bam == bac_si_id:
        return True
    if vai_goc not in {ClinicRole.TKYK, ClinicRole.NURSE_ULTRASOUND}:
        return False
    cua_toi = [d for d in lich if d.staff_id == nguoi_bam]
    for toi in cua_toi:
        for bs in cua_bs:
            if toi.room_id != bs.room_id or not _trung_ca(toi.ca, bs.ca):
                continue
            so_bs = len(
                {d.staff_id for d in lich if d.room_id == bs.room_id and d.bac_si}
            )
            # Phòng nhiều bác sĩ chỉ tách làn khi CẢ HAI vị trí đã khai làn.
            if so_bs >= 2 and toi.lan is not None and bs.lan is not None:
                if toi.lan != bs.lan:
                    continue
            return True
    return False


async def _lich_hom_nay(
    conn: asyncpg.Connection, clinic_id: str, ngay: date
) -> list[CaLam]:
    rows = await conn.fetch(
        """
        SELECT w.staff_id::text AS staff_id, v.room_id::text AS room_id,
               w.shift, v.lan, (v.nhom_nghe = 'BAC_SI') AS bac_si
          FROM work_roster w
          JOIN vi_tri_lam_viec v
            ON v.clinic_id=w.clinic_id AND v.code=w.station AND v.is_active
         WHERE w.clinic_id=$1::uuid AND w.work_date=$2::date
           AND w.status <> 'REJECTED' AND w.staff_id IS NOT NULL
           AND v.room_id IS NOT NULL
        """,
        clinic_id,
        ngay,
    )
    return [
        CaLam(
            staff_id=str(r["staff_id"]),
            room_id=str(r["room_id"]),
            ca=str(r["shift"]),
            lan=int(r["lan"]) if r["lan"] is not None else None,
            bac_si=bool(r["bac_si"]),
        )
        for r in rows
    ]


async def _dang_co_ngoai_le(
    conn: asyncpg.Connection,
    identity: StaffIdentity,
    bac_si_id: str,
    ngay: date,
) -> bool:
    return bool(
        await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM ngoai_le_ca_truc"
            " WHERE clinic_id=$1::uuid AND staff_id=$2::uuid AND ngay=$3::date"
            " AND (bac_si_id IS NULL OR bac_si_id=$4::uuid) AND huy_luc IS NULL)",
            identity.clinic_id,
            identity.staff_id,
            ngay,
            bac_si_id,
        )
    )


async def _duoc_noi_tiep_luot_cu(
    conn: asyncpg.Connection, clinic_id: str, visit_id: str | None
) -> bool:
    if not visit_id:
        return False
    row = await conn.fetchrow(
        """
        SELECT v.checked_in_at,
               (SELECT d.gia_tri FROM day_nghiep_vu d
                 WHERE d.clinic_id=v.clinic_id AND d.ma='ca_truc_lam_sang') AS day,
               (SELECT d.sua_luc FROM day_nghiep_vu d
                 WHERE d.clinic_id=v.clinic_id AND d.ma='ca_truc_lam_sang') AS bat_luc
          FROM visit v
         WHERE v.clinic_id=$1::uuid AND v.visit_id=$2::uuid
        """,
        clinic_id,
        visit_id,
    )
    if row is None or row["checked_in_at"] is None:
        return False
    # Lượt ngày cũ luôn mở; lượt đang dở trước mốc triển khai/bật lại không kẹt.
    checked = row["checked_in_at"]
    if checked.date() < hom_nay_vn():
        return True
    return row["bat_luc"] is not None and checked < row["bat_luc"]


async def kiem_dung_ca(
    conn: asyncpg.Connection,
    identity: StaffIdentity,
    bac_si_id: str | None,
    *,
    visit_id: str | None = None,
) -> str | None:
    """Kiểm cửa không mở context; dùng cho service có transaction dài."""
    if not bac_si_id:
        return None
    # Lệnh HTTP thật luôn có staff nối auth.users (get_current_identity từ chối
    # nếu không). Các job nhập lịch sử và fixture cũ gọi service bằng nhân sự
    # chưa nối tài khoản: không biến cửa triển khai mới thành khoá dữ liệu cũ.
    if not await conn.fetchval(
        "SELECT auth_user_id FROM staff WHERE id=$1::uuid", identity.staff_id
    ):
        return bac_si_id
    row = await conn.fetchrow(
        "SELECT gia_tri FROM day_nghiep_vu"
        " WHERE clinic_id=$1::uuid AND ma='ca_truc_lam_sang'",
        identity.clinic_id,
    )
    if row is not None and not giai_gia_tri("ca_truc_lam_sang", row["gia_tri"]):
        return bac_si_id
    if await _duoc_noi_tiep_luot_cu(conn, identity.clinic_id, visit_id):
        return bac_si_id
    ngay = hom_nay_vn()
    if await _dang_co_ngoai_le(conn, identity, bac_si_id, ngay):
        return bac_si_id
    lich = await _lich_hom_nay(conn, identity.clinic_id, ngay)
    if duoc_lam_thay(
        nguoi_bam=identity.staff_id,
        bac_si_id=bac_si_id,
        vai_goc=identity.vai_goc,
        lich=lich,
    ):
        return bac_si_id
    ten = await conn.fetchval(
        "SELECT full_name FROM staff WHERE id=$1::uuid", bac_si_id
    )
    raise SafetyGateError(
        f"Bạn không có ca trực hôm nay với BS {ten or 'phụ trách'} — "
        "nhờ quản lý mở ngoại lệ."
    )


@asynccontextmanager
async def doi_dung_ca(
    conn: asyncpg.Connection,
    identity: StaffIdentity,
    bac_si_id: str | None,
    *,
    visit_id: str | None = None,
) -> AsyncIterator[str | None]:
    """Kiểm cửa rồi gắn ``on_behalf_of`` cho mọi domain event trong lệnh."""
    da_kiem = await kiem_dung_ca(conn, identity, bac_si_id, visit_id=visit_id)
    if da_kiem is None:
        # Dữ liệu legacy chưa xác định bác sĩ: không khoá cứng lượt đang dở.
        yield None
        return
    with pham_vi_lam_thay(staff_id=identity.staff_id, bac_si_id=da_kiem):
        yield da_kiem


__all__ = ["CaLam", "doi_dung_ca", "duoc_lam_thay", "kiem_dung_ca"]
