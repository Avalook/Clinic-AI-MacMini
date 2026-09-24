"""Dữ liệu màn ĐẶT LỊCH (/appointments) — một lần đọc ở backend (24/09/2026).

Trang từng tự đọc 6 bảng bằng Supabase VÀ tự tính "khách khám lần mấy / đang
trong chuỗi tái khám" — một luật nghiệp vụ nằm ở frontend. Luật giữ nguyên:
  * đếm lượt ĐÃ KHÁM XONG (COMPLETED) — đặt rồi huỷ thì chưa khám lần nào;
  * còn MỘT lịch chưa huỷ nối vào lượt trước (`lich_truoc_id`) là khách đang
    trong một chuỗi tái khám.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any

import asyncpg

from clinicai.api.identity import StaffIdentity
from clinicai.core.clock import CLINIC_TZ, now_vn
from clinicai.core.tran import canh_bao_neu_day


def _gia(v: Any) -> Any:
    return v.isoformat() if isinstance(v, (datetime, date)) else v


def _dong(r: asyncpg.Record) -> dict[str, Any]:
    return {k: _gia(v) for k, v in dict(r).items()}


def dem_lan_kham(lich: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Khách → {soLanKham, laTaiKham} (hàm thuần, test không cần database)."""
    kq: dict[str, dict[str, Any]] = {}
    for r in lich:
        o = kq.setdefault(r["clinic_patient_id"], {"soLanKham": 0, "laTaiKham": False})
        if r["status"] == "COMPLETED":
            o["soLanKham"] += 1
        if r.get("lich_truoc_id") and r["status"] != "CANCELLED":
            o["laTaiKham"] = True
    return kq


async def hub_dat_lich(
    pool: asyncpg.Pool, *, identity: StaffIdentity
) -> dict[str, Any]:
    cid = identity.clinic_id
    dau = datetime.combine(now_vn().date(), time.min, tzinfo=CLINIC_TZ)
    cuoi = dau + timedelta(days=1)
    async with pool.acquire() as conn:
        co_so = await conn.fetch(
            "SELECT id::text, name FROM clinic_location"
            " WHERE clinic_id = $1::uuid AND is_active ORDER BY name",
            cid,
        )
        dich_vu = await conn.fetch(
            "SELECT id::text, name FROM service_type"
            " WHERE clinic_id = $1::uuid AND is_active ORDER BY name",
            cid,
        )
        tinh = await conn.fetch(
            "SELECT code, name, full_name FROM province ORDER BY name"
        )
        khach = await conn.fetch(
            """
            SELECT clinic_patient_id::text, patient_code, full_name, phone_primary,
                   sdt_tim_kiem, date_of_birth, gender, address,
                   location_id::text
              FROM patient
             WHERE clinic_id = $1::uuid
             ORDER BY created_at DESC
             LIMIT 200
            """,
            cid,
        )
        lich_hom_nay = await conn.fetch(
            """
            SELECT id::text, slot_start, status, doctor_id::text,
                   service_type_id::text, clinic_patient_id::text
              FROM appointment
             WHERE clinic_id = $1::uuid AND slot_start >= $2 AND slot_start < $3
               AND status NOT IN ('CANCELLED', 'NO_SHOW', 'DOCTOR_DECLINED')
             LIMIT 1000
            """,
            cid,
            dau,
            cuoi,
        )
        ma_khach = [r["clinic_patient_id"] for r in khach]
        lich_su = (
            await conn.fetch(
                """
                SELECT clinic_patient_id::text, status, lich_truoc_id::text
                  FROM appointment
                 WHERE clinic_id = $1::uuid AND clinic_patient_id = ANY($2::uuid[])
                 ORDER BY slot_start
                 LIMIT 5000
                """,
                cid,
                ma_khach,
            )
            if ma_khach
            else []
        )
    canh_bao_neu_day("dat_lich.lich_hom_nay", len(lich_hom_nay), 1000, clinic_id=cid)
    canh_bao_neu_day("dat_lich.lich_su", len(lich_su), 5000, clinic_id=cid)
    return {
        "locations": [dict(r) for r in co_so],
        "services": [dict(r) for r in dich_vu],
        "provinces": [dict(r) for r in tinh],
        "patients": [_dong(r) for r in khach],
        "appts": [_dong(r) for r in lich_hom_nay],
        "lan_kham": dem_lan_kham([dict(r) for r in lich_su]),
    }


__all__ = ["dem_lan_kham", "hub_dat_lich"]
