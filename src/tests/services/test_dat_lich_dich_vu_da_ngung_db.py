"""Đặt lịch bằng dịch vụ ĐÃ NGỪNG nói đúng lý do (06/10/2026).

Lễ tân đặt tái khám cho khách có lượt trước là "Sản 3" (tắt khi chuẩn hoá danh
mục 02/10) và nhận câu "Mã dịch vụ không thuộc phòng khám này" — câu của trường
hợp dịch vụ thuộc phòng khám khác. Không ai đoán ra phải chọn dịch vụ khác.
"""

from __future__ import annotations

import datetime as dt
import uuid

import asyncpg
import pytest

from clinicai.api.exceptions import ValidationError
from clinicai.core.clock import CLINIC_TZ
from clinicai.services.booking_service import BookingService
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    pool,
)
from tests.services.test_thu_tien_xep_phong_mang_sang_db import Ca, _benh_nhan, _dung

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _dat(pool: asyncpg.Pool, ca: Ca, pid: str, dich_vu: str) -> None:  # noqa: F811
    bd = dt.datetime.combine(
        dt.datetime.now(CLINIC_TZ).date() + dt.timedelta(days=3),
        dt.time(9, 0),
        tzinfo=CLINIC_TZ,
    )
    await BookingService(pool).create(
        clinic_patient_id=pid,
        service_type_id=dich_vu,
        location_id=ca.loc,
        slot_start=bd,
        slot_end=bd + dt.timedelta(minutes=15),
        identity=ca.le_tan,
    )


async def test_dich_vu_da_ngung_bao_ten_va_bao_chon_lai(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    duoi = uuid.uuid4().hex[:8]
    da_ngung = await pool.fetchval(
        "INSERT INTO service_type (clinic_id, code, name, is_active)"
        " VALUES ($1::uuid, $2, $3, false) RETURNING id::text",
        CLINIC,
        f"SAN3-{duoi}",
        f"Sản 3 {duoi}",
    )
    pid = await _benh_nhan(pool, ca)
    with pytest.raises(ValidationError) as loi:
        await _dat(pool, ca, pid, str(da_ngung))
    assert f"Sản 3 {duoi}" in str(loi.value)
    assert "đã ngừng sử dụng" in str(loi.value)
    assert "không thuộc phòng khám" not in str(loi.value)
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM appointment WHERE clinic_patient_id = $1::uuid",
            pid,
        )
        == 0
    )


async def test_dich_vu_khong_ton_tai_van_bao_khong_thuoc_phong_kham(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    pid = await _benh_nhan(pool, ca)
    with pytest.raises(ValidationError, match="không thuộc phòng khám này"):
        await _dat(pool, ca, pid, str(uuid.uuid4()))
