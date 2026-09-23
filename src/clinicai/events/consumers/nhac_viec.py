"""Tới giờ việc tự nhắc (nhóm 5) → réo chuông ĐÍCH DANH người đã hẹn.

Luật của hẹn giờ: tới giờ KIỂM LẠI — người ấy đã tự đánh dấu xong thì thôi.
"""

from __future__ import annotations

import asyncpg

from clinicai.events.consumers.chuong import ghi_chuong_nguoi
from clinicai.events.hen_gio import HenDenHan, dang_ky_loai
from clinicai.services.nhac_viec_service import HEN_NHAC


async def nhac_ca_nhan(conn: asyncpg.Connection, cai_hen: HenDenHan) -> bool:
    row = await conn.fetchrow(
        "SELECT staff_id::text AS staff_id, noi_dung, xong_luc,"
        "       clinic_patient_id::text AS pid"
        "  FROM nhac_viec_ca_nhan WHERE clinic_id = $1::uuid AND id = $2::uuid",
        cai_hen.clinic_id,
        cai_hen.ve_cai_gi,
    )
    if row is None or row["xong_luc"] is not None:
        return False
    await ghi_chuong_nguoi(
        conn,
        clinic_id=cai_hen.clinic_id,
        nguoi_nhan=row["staff_id"],
        tieu_de="Nhắc việc: " + row["noi_dung"][:80],
        noi_dung=row["noi_dung"],
        nguon="nhac_viec",
        nguon_id=f"nhac:{cai_hen.ve_cai_gi}",
        duong_dan=f"/customers?selected={row['pid']}" if row["pid"] else None,
        nguoi_goi=row["staff_id"],
    )
    return True


dang_ky_loai(HEN_NHAC, nhac_ca_nhan)

__all__ = ["nhac_ca_nhan"]
