"""Quản lý mở được hồ sơ MỌI khách, kể cả khi lego Bàn khám cộng vai DOCTOR.

Kiểm toán chức năng 27/09/2026 (L2): tài khoản ql bật đủ 21 lego → vai hiệu
lực có DOCTOR → rơi vào nhánh "bác sĩ chỉ mở khách có lịch với mình" → 403.
"""

from __future__ import annotations

from typing import Any, cast

import asyncpg
import pytest

from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.services.ho_so_khach_doc import duoc_mo


class _PoolCam:
    """Quản lý không được phải tra lịch hẹn — chạm pool là sai."""

    async def fetchval(self, *_: Any) -> Any:
        raise AssertionError("quản lý không cần tra lịch hẹn")


@pytest.mark.asyncio
async def test_quan_ly_co_vai_bac_si_tu_lego_van_mo_duoc() -> None:
    ql = StaffIdentity(
        staff_id="s1",
        auth_user_id="u1",
        full_name="Quản lý",
        department="QL",
        role=ClinicRole.MANAGEMENT,
        clinic_id="a0000000-0000-4000-8000-000000000001",
        location_id="fe45d9f6-0d67-428d-9d16-5ba5c36befff",
        location_name="Kim Ngưu",
        vai_theo_lego=frozenset({ClinicRole.MANAGEMENT, ClinicRole.DOCTOR}),
    )
    assert ql.co_vai({ClinicRole.DOCTOR}), "tình huống thật: lego cộng vai bác sĩ"
    pool = cast(asyncpg.Pool, _PoolCam())
    assert await duoc_mo(pool, ql, "b0000000-0000-4000-8000-000000000009") is True
