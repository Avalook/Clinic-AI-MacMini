"""PHIẾU HƯỚNG DẪN phòng (Tuyền 30/09/2026) — khách làm trước, thu sau vẫn cầm
được giấy ghi đi phòng nào; phiếu không có tiền.

    DATABASE_URL_TEST=postgresql://postgres:postgres@127.0.0.1:55500/postgres \\
        poetry run pytest src/tests/services/test_phieu_huong_dan_db.py
"""

from __future__ import annotations

import uuid

import asyncpg
import pytest

from clinicai.api.exceptions import NotFoundError
from clinicai.services.quay_thu_service import QuayThuService
from tests.chay_nguoi_dua_tin import chay_hanh_trinh
from tests.services.test_check_in_lai_sau_hoan_tac_db import pool  # noqa: F401
from tests.services.test_thu_tien_xep_phong_mang_sang_db import (
    _benh_nhan,
    _check_in,
    _chon,
    _dung,
    _kham_va_chi_dinh,
    _thu,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def test_phieu_huong_dan_in_duoc_khi_chua_thu_va_co_phong_sau_khi_xep(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    _, order = await _kham_va_chi_dinh(pool, ca, visit)
    qt = QuayThuService(pool)

    # Khách chưa chốt làm → chưa có gì để hướng dẫn.
    p = await qt.phieu(identity=ca.le_tan, id_=visit, loai="huong_dan")
    assert p["loai"] == "huong_dan" and p["dong"] == []

    # Chốt làm, CHƯA THU: dịch vụ lên phiếu, không có tiền.
    await _chon(pool, ca, visit, [order])
    p = await qt.phieu(identity=ca.le_tan, id_=visit, loai="huong_dan")
    [d] = p["dong"]
    assert d["order_id"] == order and d["thanh_tien"] is None
    assert p["tong"] == 0 and p["hinh_thuc"] is None and p["nguoi_thu"] is None
    assert p["khach"] and p["id"] == visit

    # Đã xếp phòng → phiếu ghi đúng TÊN phòng.
    await _thu(pool, visit, ca.le_tan)
    await chay_hanh_trinh(pool)
    ten_phong = await pool.fetchval(
        "SELECT r.name FROM service_order o JOIN clinic_room r ON r.id = o.room_id"
        " WHERE o.id = $1::uuid",
        order,
    )
    assert ten_phong
    [d] = (await qt.phieu(identity=ca.le_tan, id_=visit, loai="huong_dan"))["dong"]
    assert d["phong"]["ten"] == ten_phong and d["cho_xep"] is False


async def test_phieu_huong_dan_luot_khong_co_thi_404(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    with pytest.raises(NotFoundError):
        await QuayThuService(pool).phieu(
            identity=ca.le_tan, id_=str(uuid.uuid4()), loai="huong_dan"
        )
