"""Lịch làm việc kèm VAI của từng người (27/09/2026 đợt 3, A9).

    DATABASE_URL_TEST=postgresql://postgres:postgres@127.0.0.1:55500/postgres \\
        poetry run pytest src/tests/services/test_lich_kem_vai_db.py

Hai gói cấp lịch — Trang chủ (`ManTrangChuService`) và /schedule
(`RosterService.lich_tuan`) — trả `vai` + `vai_ngan` mỗi dòng, lấy từ
`clinic_membership.role`. Dòng nhập tay không nối được ai → vai rỗng.
"""

from __future__ import annotations

import datetime as dt

import asyncpg
import pytest

from clinicai.core.clock import CLINIC_TZ
from clinicai.services.config_service import RosterService
from clinicai.services.man_trang_chu_service import ManTrangChuService
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    pool,
)
from tests.services.test_thu_tien_xep_phong_mang_sang_db import _dung

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def test_hai_goi_lich_tra_vai_moi_dong(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    hom_nay = dt.datetime.now(CLINIC_TZ).date()
    # Tuần xa trong tương lai — không đụng lịch các bài kiểm khác.
    thu2 = hom_nay + dt.timedelta(days=7 * 30 - hom_nay.weekday())
    for staff_id, ten, tram in (
        (ca.dd.staff_id, "ĐD thử", "T1_TT_DD"),
        (ca.le_tan.staff_id, "LT thử", "T1_LETAN"),
        (None, "Nhập tay", "T1_THUNGAN"),
    ):
        await pool.execute(
            "INSERT INTO work_roster (clinic_id, work_date, week_start, shift,"
            " station, staff_id, staff_name, status)"
            " VALUES ($1::uuid, $2, $2, 'TOI', $3, $4::uuid, $5, 'APPROVED')",
            CLINIC,
            thu2,
            tram,
            staff_id,
            ten,
        )

    goi = await ManTrangChuService(pool).goi_du_lieu(
        identity=ca.le_tan, week_appt=thu2, week_roster=thu2
    )
    theo_tram = {r["station"]: r for r in goi["roster"]}
    assert theo_tram["T1_TT_DD"]["vai"] == "Điều dưỡng"
    assert theo_tram["T1_TT_DD"]["vai_ngan"] == "ĐD"
    assert theo_tram["T1_LETAN"]["vai_ngan"] == "Lễ tân"
    assert theo_tram["T1_THUNGAN"]["vai"] == ""
    assert theo_tram["T1_THUNGAN"]["vai_ngan"] == ""
    assert "vai_ma" not in theo_tram["T1_LETAN"]

    lich = await RosterService(pool).lich_tuan(identity=ca.le_tan, tuan=thu2)
    theo_tram = {r["station"]: r for r in lich["dong"]}
    assert theo_tram["T1_TT_DD"]["vai_ngan"] == "ĐD"
    assert theo_tram["T1_THUNGAN"]["vai"] == ""
