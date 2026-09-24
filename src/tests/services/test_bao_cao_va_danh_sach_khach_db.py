"""Báo cáo · Toàn cảnh · danh sách khách đọc ở backend (24/09/2026).

Ba trang (/reports, tab Toàn cảnh của /ops, /customers) từng tự đọc Supabase.
Canh: số đếm theo NGÀY VIỆT NAM, bộ lọc khách giữ đúng luật cũ (bỏ lịch chết,
tìm không dấu, khách được trỏ tới ngoài trang vẫn hiện), đầu vào rác không ném.
"""

from __future__ import annotations

import uuid
from datetime import datetime, time, timedelta

import asyncpg
import pytest

from clinicai.core.clock import CLINIC_TZ, now_vn
from clinicai.services.danh_sach_khach_cskh import cua_so, danh_sach_khach
from clinicai.services.reports_service import toan_canh, tong_quan
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    pool,
)
from tests.services.test_thu_tien_xep_phong_mang_sang_db import (
    Ca,
    _benh_nhan,
    _check_in,
    _dung,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _khach_ten(pool: asyncpg.Pool, ca: Ca, ten: str) -> str:  # noqa: F811
    return str(
        await pool.fetchval(
            "INSERT INTO patient (clinic_id, patient_code, full_name, location_id)"
            " VALUES ($1::uuid, $2, $3, $4::uuid) RETURNING clinic_patient_id::text",
            CLINIC,
            f"DSK-{uuid.uuid4().hex[:8]}",
            ten,
            ca.loc,
        )
    )


async def _lich_trua_nay(
    pool: asyncpg.Pool,  # noqa: F811
    ca: Ca,
    pid: str,
    trang_thai: str,
) -> None:
    trua = datetime.combine(now_vn().date(), time(12, 0), tzinfo=CLINIC_TZ)
    await pool.execute(
        "INSERT INTO appointment (clinic_id, clinic_patient_id, location_id,"
        " service_type_id, slot_start, slot_end, doctor_id, status, ly_do_huy_ma)"
        " VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, $5, $6, $7::uuid, $8,"
        " CASE WHEN $8 = 'CANCELLED' THEN 'BAO_KHI_XAC_NHAN' END)",
        CLINIC,
        pid,
        ca.loc,
        ca.loai_kham,
        trua,
        trua + timedelta(minutes=15),
        ca.bac_si.staff_id,
        trang_thai,
    )


async def test_cua_so_theo_gio_viet_nam() -> None:
    # 23:30 Chủ nhật giờ VN — tuần vẫn là tuần bắt đầu thứ Hai trước đó.
    cn = datetime(2026, 9, 27, 23, 30, tzinfo=CLINIC_TZ)
    dau, cuoi = cua_so("week", cn) or (None, None)
    assert dau == datetime(2026, 9, 21, tzinfo=CLINIC_TZ)
    assert cuoi == datetime(2026, 9, 28, tzinfo=CLINIC_TZ)
    thang = cua_so("month", datetime(2026, 12, 15, tzinfo=CLINIC_TZ))
    assert thang == (
        datetime(2026, 12, 1, tzinfo=CLINIC_TZ),
        datetime(2027, 1, 1, tzinfo=CLINIC_TZ),
    )
    assert cua_so("rác", cn) is None
    assert cua_so(None, cn) is None


async def test_tong_quan_dem_lich_hom_nay_va_bay_ngay(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    truoc = await tong_quan(pool, identity=ca.le_tan)
    pid = await _benh_nhan(pool, ca)
    await _lich_trua_nay(pool, ca, pid, "SCHEDULED")
    sau = await tong_quan(pool, identity=ca.le_tan)
    assert sau["hom_nay"] == truoc["hom_nay"] + 1
    assert sau["hom_nay_chua_xn"] == truoc["hom_nay_chua_xn"] + 1
    assert sau["khach_moi_30"] == truoc["khach_moi_30"] + 1
    assert len(sau["theo_ngay"]) == 7
    assert sau["theo_ngay"][-1]["ngay"] == now_vn().date().isoformat()
    assert sau["theo_ngay"][-1]["count"] == sau["hom_nay"]
    assert sum(b["total"] for b in sau["theo_bac_si"]) == sau["hom_nay"]


async def test_toan_canh_dem_va_su_kien(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    pid = await _benh_nhan(pool, ca)
    await _check_in(pool, ca, pid, ca.loai_kham)
    tc = await toan_canh(pool, identity=ca.le_tan)
    assert tc["counts"]["visitsToday"] >= 1
    assert tc["counts"]["patientsToday"] >= 1
    assert tc["staff"], "phải có danh sách nhân sự"
    assert len(tc["recentEvents"]) <= 10


async def test_danh_sach_khach_tim_khong_dau_va_loc_theo_hen(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    duoi = uuid.uuid4().hex[:8]
    co_hen = await _khach_ten(pool, ca, f"Đặng Thùy {duoi} Linh")
    huy_hen = await _khach_ten(pool, ca, f"Đặng Thùy {duoi} Mai")
    await _lich_trua_nay(pool, ca, co_hen, "CONFIRMED")
    await _lich_trua_nay(pool, ca, huy_hen, "CANCELLED")

    # Tìm KHÔNG dấu ra cả hai (theo ngày tạo, hôm nay).
    kq = await danh_sach_khach(
        pool, identity=ca.le_tan, q=f"dang thuy {duoi}", ky="today", theo="created"
    )
    assert {r["clinic_patient_id"] for r in kq["rows"]} == {co_hen, huy_hen}
    assert kq["total"] == 2
    assert kq["rows"][0]["patient_sdt_them"] == []

    # Theo ngày hẹn: lịch đã huỷ không tính là "có hẹn".
    kq = await danh_sach_khach(
        pool, identity=ca.le_tan, q=duoi, ky="today", theo="appt"
    )
    assert [r["clinic_patient_id"] for r in kq["rows"]] == [co_hen]


async def test_khach_duoc_tro_toi_ngoai_trang_van_hien_va_rac_khong_nem(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    pid = await _benh_nhan(pool, ca)
    kq = await danh_sach_khach(pool, identity=ca.le_tan, trang=100000, chon=pid)
    assert kq["rows"][0]["clinic_patient_id"] == pid
    assert kq["total"] == 0
    kq = await danh_sach_khach(
        pool, identity=ca.le_tan, ky="xyz", theo="?", trang=-5, chon="rác", q="%_,()"
    )
    assert isinstance(kq["rows"], list)


async def test_bon_duong_doc_khung_trang(pool: asyncpg.Pool) -> None:  # noqa: F811
    """Bốn đường đọc cùng đợt: lịch bác sĩ từ chối, phiếu in theo lịch, ca của
    tôi, thời lượng khám đo được — chạy được trên lược đồ thật, lọc đúng người."""
    from clinicai.api.v1.routers.config import ca_cua_toi, thoi_luong_kham_do_duoc
    from clinicai.services.ho_so_lam_sang_doc import phieu_in_theo_lich
    from clinicai.services.lich_hen_doc import lich_bac_si_tu_choi

    ca = await _dung(pool)
    pid = await _benh_nhan(pool, ca)
    await _lich_trua_nay(pool, ca, pid, "DOCTOR_DECLINED")
    tu_choi = await lich_bac_si_tu_choi(pool, identity=ca.le_tan)
    assert any(r["patient"] and r["doctor"] for r in tu_choi), (
        "lịch bác sĩ từ chối hôm nay phải hiện kèm tên khách + bác sĩ"
    )

    await _check_in(pool, ca, pid, ca.loai_kham)
    appt = await pool.fetchval(
        "SELECT id::text FROM appointment WHERE clinic_patient_id = $1::uuid"
        " AND status <> 'DOCTOR_DECLINED'",
        pid,
    )
    phieu = await phieu_in_theo_lich(pool, identity=ca.bac_si, appointment_id=appt)
    assert phieu is not None
    assert phieu["appointment"]["clinic_patient_id"] == pid
    assert phieu["visit"] is not None
    assert (
        await phieu_in_theo_lich(
            pool, identity=ca.bac_si, appointment_id=str(uuid.uuid4())
        )
        is None
    )

    ca_toi = await ca_cua_toi(identity=ca.bac_si, pool=pool)
    assert isinstance(ca_toi["items"], list)
    do = await thoi_luong_kham_do_duoc(identity=ca.le_tan, pool=pool)
    assert isinstance(do["items"], list)
