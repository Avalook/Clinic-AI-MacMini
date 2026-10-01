"""Trưởng ca xếp lịch làm việc (Tuyền 01/10/2026) — migration 20261001260000.

Trước đó xếp ca / áp dụng tuần đòi lego "Cài đặt phòng khám". Nay trưởng ca có
quyền riêng `roster.manage` (khối Điều phối ca) — xếp người khác, áp tuần, gỡ ca
— nhưng KHÔNG sửa được phạm vi vị trí (cấu hình, vẫn ở lego Cài đặt).
"""

from __future__ import annotations

import datetime as dt

import pytest

from clinicai.core.exceptions import SafetyGateError
from clinicai.permissions import cache
from clinicai.permissions.can import can
from clinicai.services.config_service import RosterService
from tests.goi_mau_cu import ve_goi_mau_cu
from tests.services.test_luot_kham_service_db import KichBan, _nguoi

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


def _ngay_toi() -> dt.date:
    # Tuần sau: không đụng lịch thật của hôm nay mà các bài khác dựa vào.
    hom_nay = dt.date.today()
    return hom_nay + dt.timedelta(days=7 - hom_nay.weekday() + 2)


async def test_truong_ca_co_quyen_xep_lich(kb: KichBan) -> None:
    async with kb.pool.acquire() as conn:
        assert await can(conn, kb.truong_ca, "roster.manage")
        assert await can(conn, kb.truong_ca, "roster.view")
        assert not await can(conn, kb.truong_ca, "config.clinic.manage")


async def test_truong_ca_xep_nguoi_khac_ap_tuan_va_go_ca(kb: KichBan) -> None:
    svc = RosterService(kb.pool)
    tram = await svc.tram_cho_nhan_vien(
        identity=kb.truong_ca, staff_id=kb.dieu_duong.staff_id
    )
    if not tram["tram"]:
        pytest.skip("DB thử chưa khai vị trí cho điều dưỡng")
    ngay = _ngay_toi()

    roster_id = await svc.add_shift(
        work_date=ngay,
        station=tram["tram"][0],
        shift="SANG",
        identity=kb.truong_ca,
        staff_id=kb.dieu_duong.staff_id,
    )
    async with kb.pool.acquire() as conn:
        dong = await conn.fetchrow(
            "SELECT staff_id::text, status FROM work_roster WHERE id = $1::uuid",
            roster_id,
        )
    assert dong is not None
    # Xếp cho NGƯỜI KHÁC (không bị đổi thành chính trưởng ca) và vào thẳng lịch.
    assert dong["staff_id"] == kb.dieu_duong.staff_id
    assert dong["status"] == "APPROVED"

    ket = await svc.apply_week(week_start=ngay, identity=kb.truong_ca)
    assert ket

    await svc.remove(roster_id=roster_id, identity=kb.truong_ca)
    async with kb.pool.acquire() as conn:
        assert not await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM work_roster WHERE id = $1::uuid)", roster_id
        )

    lich = await svc.lich_tuan(identity=kb.truong_ca, tuan=ngay)
    # Người xếp lịch nhận danh sách nhân sự để chọn vào ô "+".
    assert lich["nhan_su"]


async def test_truong_ca_khong_sua_pham_vi_vi_tri(kb: KichBan) -> None:
    with pytest.raises(SafetyGateError):
        await RosterService(kb.pool).dat_vi_tri_cho_vai(
            identity=kb.truong_ca, tram_ma="DIEU_PHOI", vai="CSKH", cho_phep=True
        )


async def test_nguoi_khong_co_quyen_chi_tu_xep_minh(kb: KichBan) -> None:
    """Không có `roster.manage` thì tên người khác gửi lên bị bỏ qua."""
    async with kb.pool.acquire() as conn:
        ai = await _nguoi(conn, kb.location_id, "CSKH")
        await ve_goi_mau_cu(conn, ai)
        cache.quen(ai.clinic_id)
        assert not await can(conn, ai, "roster.manage")
    assert not await RosterService(kb.pool)._xep_lich(ai)
