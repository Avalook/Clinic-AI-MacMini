"""LÝ DO HUỶ / LÝ DO VỀ GIỮA CHỪNG PHẢI HIỆN Ở CHỖ NGƯỜI TA NHÌN (30/10/2026).

    scripts/test-nhanh.sh src/tests/services/test_ly_do_huy_va_ve_hien_db.py

Nhân sự báo "huỷ lịch không có chỗ ghi lý do". Máy chủ ghi ĐÚNG — lỗi ở chỗ
nhìn: khung khách chỉ đọc chữ tự do (`cancellation_reason`), nên chọn mã mà
không gõ chữ (đường thường gặp nhất) thì lý do biến mất. Khách bỏ về giữa chừng
cũng thế: `visit.incomplete_reason` ghi rồi mà không màn nào in ra.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta

import asyncpg
import pytest

from clinicai.core.clock import CLINIC_TZ, now_vn
from clinicai.services.checkout_service import CheckoutService
from clinicai.services.ghi_chu_khach_service import GhiChuKhachService
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


async def _lich_da_huy(
    pool: asyncpg.Pool,  # noqa: F811
    ca: Ca,
    pid: str,
    ngay_sau: int,
    ma: str,
    chu: str | None,
) -> str:
    bd = datetime.combine(
        now_vn().date() + timedelta(days=ngay_sau), time(9, 0), tzinfo=CLINIC_TZ
    )
    return str(
        await pool.fetchval(
            "INSERT INTO appointment (clinic_id, clinic_patient_id, location_id,"
            " service_type_id, slot_start, slot_end, doctor_id, status,"
            " ly_do_huy_ma, cancellation_reason, cancelled_at)"
            " VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, $5, $6, $7::uuid,"
            " 'CANCELLED', $8, $9, now()) RETURNING id::text",
            CLINIC,
            pid,
            ca.loc,
            ca.loai_kham,
            bd,
            bd + timedelta(minutes=15),
            ca.bac_si.staff_id,
            ma,
            chu,
        )
    )


async def test_khung_khach_tra_ca_ma_ly_do_khong_chi_chu(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    pid = await _benh_nhan(pool, ca)
    chi_ma = await _lich_da_huy(pool, ca, pid, 3, "BAO_KHI_NHAC_HEN", None)
    ca_hai = await _lich_da_huy(pool, ca, pid, 4, "KHAC", "Khách chuyển nhà")

    tt = await GhiChuKhachService(pool).tom_tat(
        identity=ca.le_tan, clinic_patient_id=pid
    )
    theo_id = {x["id"]: x for x in tt["lich_da_qua"]}
    # Chọn mã, không gõ chữ: trước đây khung khách nhận đúng {ly_do_huy: None}.
    assert theo_id[chi_ma]["ly_do_huy_ma"] == "BAO_KHI_NHAC_HEN"
    assert theo_id[chi_ma]["ly_do_huy"] is None
    assert theo_id[ca_hai]["ly_do_huy_ma"] == "KHAC"
    assert theo_id[ca_hai]["ly_do_huy"] == "Khách chuyển nhà"


async def test_khach_ve_giua_chung_tra_ly_do_o_khung_khach_va_check_out(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    pid = await _benh_nhan(pool, ca)
    visit = await _check_in(pool, ca, pid, ca.loai_kham)

    tt = await GhiChuKhachService(pool).tom_tat(
        identity=ca.le_tan, clinic_patient_id=pid
    )
    # Lượt còn mở: chưa có lý do về.
    assert tt["luot_gan_nhat"][0]["ly_do_ve"] is None

    await CheckoutService(pool).close(
        identity=ca.le_tan,
        visit_id=visit,
        incomplete=True,
        incomplete_reason="Con ốm, phải về đón",
        ly_do_tu_dong="Lễ tân cho khách về.",
    )
    tt = await GhiChuKhachService(pool).tom_tat(
        identity=ca.le_tan, clinic_patient_id=pid
    )
    assert tt["luot_gan_nhat"][0]["trang_thai"] == "INCOMPLETE"
    assert tt["luot_gan_nhat"][0]["ly_do_ve"] == "Con ốm, phải về đón"

    ct = await CheckoutService(pool).chi_tiet(identity=ca.le_tan, visit_id=visit)
    assert ct["visit_status"] == "INCOMPLETE"
    assert ct["ly_do_ve"] == "Con ốm, phải về đón"
