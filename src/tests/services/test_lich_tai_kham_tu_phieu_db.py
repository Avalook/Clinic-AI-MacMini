"""Bác sĩ đặt LỊCH HẸN THẬT từ ô "Ngày tái khám" (Tuyền 02/10/2026).

Kiểm: đặt "Chưa phân bác sĩ" ra một `appointment` thật gắn lượt; việc gọi của
CSKH VẪN MỞ (không bị trigger / `dong_bo` đóng "đã có lịch") và có kèm lịch;
một lượt chỉ một lịch còn sống; huỷ trên phiếu rồi đặt lại được (hoàn tác);
không huỷ được lịch của lượt khác.
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

import asyncpg
import pytest

from clinicai.api.exceptions import ConflictError, NotFoundError
from clinicai.api.identity import StaffIdentity
from clinicai.core.clock import CLINIC_TZ
from clinicai.services.capacity_service import CapacityService
from clinicai.services.hen_tai_kham_service import chi_tiet_viec
from clinicai.services.lich_tai_kham_service import GHI_CHU_LICH, LichTaiKhamService
from tests.services.test_hen_tai_kham_db import _chuan_bi, _luu, _viec
from tests.services.test_phieu_kham_db import CLINIC, _o, pool  # noqa: F401

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _san_sang(
    pool: asyncpg.Pool,  # noqa: F811
) -> tuple[StaffIdentity, dict[str, str], dt.date]:
    bs, luot = await _chuan_bi(pool)
    loai = await pool.fetchval(
        "INSERT INTO service_type (clinic_id, code, name, is_active)"
        " VALUES ($1::uuid, $2, 'Khám phụ khoa test', true) RETURNING id::text",
        CLINIC,
        f"TKP-{uuid.uuid4().hex[:8]}",
    )
    await pool.execute(
        "UPDATE visit SET service_type_id = $2::uuid WHERE visit_id = $1::uuid",
        luot["visit"],
        loai,
    )
    ngay = dt.datetime.now(CLINIC_TZ).date() + dt.timedelta(days=30)
    return bs, luot, ngay


async def _khung_trong(
    pool: asyncpg.Pool,  # noqa: F811
    bs: StaffIdentity,
    ngay: dt.date,
    bo: int = 0,
) -> tuple[dt.datetime, dt.datetime]:
    """Khung còn mở của hàng "Chưa phân bác sĩ" — đọc từ chính quote."""
    q = await CapacityService(pool).quote(
        date=ngay.isoformat(),
        location_id=bs.location_id,
        doctor_id=None,
        clinic_id=CLINIC,
    )
    mo = [k for k in q["slots"] if k["state"] != "closed"]
    if len(mo) <= bo:
        pytest.skip("phòng khám test không có khung mở ngày này")
    k: dict[str, Any] = mo[bo]
    h, m = map(int, k["time"].split(":"))
    bat_dau = dt.datetime.combine(ngay, dt.time(h, m), tzinfo=CLINIC_TZ)
    return bat_dau, bat_dau + dt.timedelta(minutes=int(k["slot_minutes"]))


async def test_dat_chua_phan_bac_si_ra_lich_that_va_viec_cskh_van_mo(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    bs, luot, ngay = await _san_sang(pool)
    v = luot["visit"]
    await _luu(pool, bs, v, {"pk_follow_date": _o(ngay.isoformat())})
    bat_dau, ket_thuc = await _khung_trong(pool, bs, ngay)

    svc = LichTaiKhamService(pool)
    kq = await svc.dat(
        visit_id=v,
        identity=bs,
        slot_start=bat_dau,
        slot_end=ket_thuc,
        doctor_id=None,
    )
    lich = kq["lich"]
    assert lich is not None and lich["ngay"] == ngay.isoformat()
    assert lich["bac_si"] is None and lich["huy_duoc"] is True
    a = await pool.fetchrow(
        "SELECT clinic_patient_id::text AS khach, doctor_id, patient_kind, notes,"
        " hen_tu_visit_id::text AS tu FROM appointment WHERE id = $1::uuid",
        lich["appointment_id"],
    )
    assert a["khach"] == luot["patient"] and a["doctor_id"] is None
    assert (a["patient_kind"], a["notes"], a["tu"]) == ("RETURN", GHI_CHU_LICH, v)

    # Việc gọi của CSKH GIỮ NGUYÊN — trigger không đóng "đã có lịch".
    (viec,) = await _viec(pool, v)
    assert viec["trang_thai"] == "CHO_GOI"
    # Lưu lại phiếu (dong_bo chạy lại) cũng không đóng.
    kq2 = await _luu(pool, bs, v, {"pk_follow_note": _o("Nhịn ăn sáng")})
    (viec,) = await _viec(pool, v)
    assert viec["trang_thai"] == "CHO_GOI", kq2
    # Việc của CSKH nói luôn lịch bác sĩ đã đặt.
    async with pool.acquire() as conn:
        ct = await chi_tiet_viec(conn, CLINIC, v)
    assert ct is not None
    assert ct["lich_bac_si_dat"]["appointment_id"] == lich["appointment_id"]

    # Một lượt = một lịch còn sống.
    with pytest.raises(ConflictError):
        await svc.dat(
            visit_id=v,
            identity=bs,
            slot_start=bat_dau,
            slot_end=ket_thuc,
            doctor_id=None,
        )
    assert (await svc.doc(visit_id=v, identity=bs))["lich"]["appointment_id"] == (
        lich["appointment_id"]
    )


async def test_huy_tren_phieu_roi_dat_lai_duoc_khong_huy_lich_luot_khac(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    bs, luot, ngay = await _san_sang(pool)
    v = luot["visit"]
    bat_dau, ket_thuc = await _khung_trong(pool, bs, ngay)
    svc = LichTaiKhamService(pool)
    lich = (
        await svc.dat(
            visit_id=v,
            identity=bs,
            slot_start=bat_dau,
            slot_end=ket_thuc,
            doctor_id=None,
        )
    )["lich"]

    # Lượt khác không huỷ được lịch của lượt này.
    _, luot_khac, _ = await _san_sang(pool)
    with pytest.raises(NotFoundError):
        await svc.huy(
            visit_id=luot_khac["visit"],
            appointment_id=lich["appointment_id"],
            identity=bs,
        )

    kq = await svc.huy(visit_id=v, appointment_id=lich["appointment_id"], identity=bs)
    assert kq["status"] == "CANCELLED"
    r = await pool.fetchrow(
        "SELECT status, cancellation_reason FROM appointment WHERE id = $1::uuid",
        lich["appointment_id"],
    )
    assert r["status"] == "CANCELLED" and r["cancellation_reason"]
    assert (await svc.doc(visit_id=v, identity=bs))["lich"] is None

    # Hoàn tác = đặt lại (khung khác cũng được).
    bat_dau2, ket_thuc2 = await _khung_trong(pool, bs, ngay, bo=1)
    lai = await svc.dat(
        visit_id=v,
        identity=bs,
        slot_start=bat_dau2,
        slot_end=ket_thuc2,
        doctor_id=None,
    )
    assert lai["lich"]["appointment_id"] != lich["appointment_id"]
