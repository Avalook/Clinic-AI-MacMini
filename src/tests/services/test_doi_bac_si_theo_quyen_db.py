"""Đổi bác sĩ giữa lượt: người nhận phải KHÁM ĐƯỢC và KHÉP ĐƯỢC lượt (24/09/2026).

Bộ mô phỏng 20 khách (K11) bắt được: danh sách "đổi sang bác sĩ" lọc theo TÊN
VAI (bác sĩ / bác sĩ siêu âm) nên có cả BS siêu âm không có khối Khám; đổi sang
là khách kẹt — không ai bắt đầu hay kết thúc được. Nay hỏi QUYỀN.
"""

from __future__ import annotations

import asyncpg
import pytest

from clinicai.api.exceptions import ValidationError
from clinicai.services.doi_bac_si_service import DoiBacSiService
from clinicai.services.permission_service import PermissionService
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    _nguoi,
    pool,
)
from tests.services.test_thu_tien_xep_phong_mang_sang_db import (
    _benh_nhan,
    _check_in,
    _dung,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def test_chi_nguoi_kham_va_hoan_tat_duoc_moi_nhan_khach(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    async with pool.acquire() as conn:
        sa = await _nguoi(conn, ca.loc, "ULTRASOUND_DOCTOR")
        ql = await _nguoi(conn, ca.loc, "MANAGEMENT")
        tc = await _nguoi(conn, ca.loc, "TRUONG_CA")
    svc = DoiBacSiService(pool)
    ds = {r["id"] for r in await svc.bac_si_trong_phong_kham(identity=tc)}
    assert ca.bac_si.staff_id in ds
    assert sa.staff_id not in ds, (
        "BS siêu âm chưa có khối Khám không được vào danh sách"
    )

    pid = await _benh_nhan(pool, ca)
    vid = await _check_in(pool, ca, pid, ca.loai_kham)
    with pytest.raises(ValidationError):
        await svc.doi(
            identity=tc, visit_id=vid, bac_si_moi_id=sa.staff_id, ly_do="quá tải"
        )

    pq = PermissionService(pool)
    for khoi in ("kham", "hoan_tat_kham"):
        await pq.cap_khoi(identity=ql, staff_id=sa.staff_id, khoi=khoi)
    ds = {r["id"] for r in await svc.bac_si_trong_phong_kham(identity=tc)}
    assert sa.staff_id in ds
    await svc.doi(identity=tc, visit_id=vid, bac_si_moi_id=sa.staff_id, ly_do="quá tải")
