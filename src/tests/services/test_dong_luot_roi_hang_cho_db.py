"""Đóng lượt thì khách rời MỌI hàng chờ (27/09/2026).

Trước bản sửa, check-out chỉ huỷ `work_item`; `queue_entry` để nguyên "waiting"
nên khách đã về vẫn nằm trong hàng bàn khám / phòng dịch vụ (đo trên prod: 4
chỗ). Helper `_dong_luot` của test cũ TỰ đặt `left` trước khi đóng — nên lỗi
không bao giờ lộ ra trong test. Ở đây đóng bằng đúng lệnh thật.
"""

from __future__ import annotations

import json

import asyncpg
import pytest

from clinicai.services.checkout_service import CheckoutService
from tests.chay_nguoi_dua_tin import chay_hanh_trinh
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    pool,
)
from tests.services.test_thu_tien_xep_phong_mang_sang_db import (
    _benh_nhan,
    _check_in,
    _dung,
    _kham_va_chi_dinh,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _con_mo(pool: asyncpg.Pool, visit: str) -> int:  # noqa: F811
    return int(
        await pool.fetchval(
            "SELECT count(*) FROM queue_entry WHERE visit_id = $1::uuid"
            " AND status IN ('blocked', 'waiting', 'called', 'serving')",
            visit,
        )
    )


@pytest.mark.parametrize("bo_ve", [False, True])
async def test_dong_luot_thi_khach_roi_moi_hang_cho(
    pool: asyncpg.Pool,  # noqa: F811
    bo_ve: bool,
) -> None:
    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    await chay_hanh_trinh(pool)
    await _kham_va_chi_dinh(pool, ca, visit)
    assert await _con_mo(pool, visit) >= 1, "đang khám: có chỗ chờ bác sĩ mở"

    kq = await CheckoutService(pool).close(
        identity=ca.le_tan,
        visit_id=visit,
        override_reason=None if bo_ve else "Khách xin về trước, hẹn làm sau",
        incomplete=bo_ve,
        incomplete_reason="Khách có việc gấp" if bo_ve else None,
    )
    assert kq["ok"]
    assert await _con_mo(pool, visit) == 0, "khách đã về không còn trong hàng nào"
    payload = await pool.fetchval(
        "SELECT payload FROM event_log WHERE aggregate_id = $1::uuid"
        " AND event_type IN ('dispatch.checkout', 'visit.closed_incomplete')"
        " ORDER BY recorded_at DESC LIMIT 1",
        visit,
    )
    assert json.loads(payload)["hang_cho_roi"] >= 1
