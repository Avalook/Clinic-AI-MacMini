"""`GET /appointments/policy` với ngày / mã bác sĩ RÁC → luật mặc định, không 500.

Kiểm toán 27/09/2026: `?date=abc` sập ở `strptime`, `?doctor_id=abc` sập ở
Postgres. Luật CLAUDE.md: hàm nhận ngày giờ từ người dùng trả rỗng thay vì ném.
"""

from __future__ import annotations

import asyncpg
import pytest

from clinicai.api.v1.routers.booking import booking_policy
from tests.services.test_check_in_lai_sau_hoan_tac_db import pool  # noqa: F401
from tests.services.test_thu_tien_xep_phong_mang_sang_db import _dung

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


@pytest.mark.parametrize(
    ("doctor_id", "ngay"),
    [
        ("abc", "2026-09-27"),
        ("00000000-0000-4000-8000-000000000001", "abc"),
        ("00000000-0000-4000-8000-000000000001", "2026-02-31"),
        ("", ""),
        (None, "not-a-date"),
    ],
)
async def test_dau_vao_rac_tra_luat_mac_dinh(
    pool: asyncpg.Pool,  # noqa: F811
    doctor_id: str | None,
    ngay: str | None,
) -> None:
    ca = await _dung(pool)
    goc = await booking_policy(doctor_id=None, date=None, identity=ca.le_tan, pool=pool)
    kq = await booking_policy(
        doctor_id=doctor_id, date=ngay, identity=ca.le_tan, pool=pool
    )
    assert kq == goc
