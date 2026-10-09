"""Ô "Làm trước – thu sau" ở KHUNG PHẢI phòng dịch vụ (Tuyền 09/10/2026), trên
Postgres thật: cờ `nhac_tick` của chỉ định chỉ bật khi FinanceGate đang chặn vì
chưa thu và chưa tick — mặc định KHÔNG hiện.

    scripts/test-nhanh.sh src/tests/services/test_nhac_tick_phong_db.py
"""

from __future__ import annotations

from typing import Any

import pytest

from clinicai.services import nhan_tai_phong as ntp
from clinicai.services.lam_truoc_thu_sau import LamTruocThuSauService
from tests.services.test_luot_kham_service_db import CLINIC
from tests.services.test_nhan_tai_phong_db import _cd_o, _nhan, bat  # noqa: F401
from tests.services.test_service_routing_db import RB, _paid, rb  # noqa: F401
from tests.services.test_thu_truoc_lam_truoc_tick_db import day_thu_truoc

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _dong(b: RB, room: str, oid: str) -> dict[str, Any]:
    async with b.pool.acquire() as conn:
        ds = await ntp.chi_dinh_cua_khach(conn, CLINIC, room, [b.visit_id])
    [c] = [c for c in ds[b.visit_id] if c["id"] == oid]
    return c


async def test_khung_phai_chi_moi_tick_khi_chua_thu_chua_tick(
    bat: RB,  # noqa: F811
) -> None:
    async with day_thu_truoc(bat.pool, True):
        no = await _cd_o(bat, bat.sa1, gia=200000)  # chưa thu
        mien = await _cd_o(bat, bat.sa1)  # 0đ — không cần qua cửa tiền
        # Ca 1 / ca 3: chưa thu, chưa tick → mời (cả ở Sắp đến lẫn khi đã chờ).
        assert (await _dong(bat, bat.sa1, no))["nhac_tick"] is True
        assert (await _dong(bat, bat.sa1, mien))["nhac_tick"] is False
        async with bat.pool.acquire() as conn:
            [k] = [
                k
                for k in await ntp.sap_den(conn, CLINIC, bat.sa1)
                if k["visit_id"] == bat.visit_id
            ]
        assert [c["nhac_tick"] for c in k["chi_dinh"] if c["id"] == no] == [True]
        await _nhan(bat, bat.sa1, no)
        assert (await _dong(bat, bat.sa1, no))["nhac_tick"] is True

        # Ca 2: đã tick (mức lượt — bác sĩ chính hay phòng tick đều thế) → ẩn.
        await LamTruocThuSauService(bat.pool).dat(
            visit_id=bat.visit_id, bat=True, identity=bat.bac_si
        )
        assert (await _dong(bat, bat.sa1, no))["nhac_tick"] is False
        # Bỏ tick (hoàn tác) → mời lại; thu tiền → không mời.
        await LamTruocThuSauService(bat.pool).dat(
            visit_id=bat.visit_id, bat=False, identity=bat.bac_si
        )
        assert (await _dong(bat, bat.sa1, no))["nhac_tick"] is True
        await _paid(bat, no)
        assert (await _dong(bat, bat.sa1, no))["nhac_tick"] is False


async def test_day_thu_truoc_tat_thi_khong_moi_tick(
    bat: RB,  # noqa: F811
) -> None:
    async with day_thu_truoc(bat.pool, False):
        no = await _cd_o(bat, bat.sa1, gia=200000)
        assert (await _dong(bat, bat.sa1, no))["nhac_tick"] is False
