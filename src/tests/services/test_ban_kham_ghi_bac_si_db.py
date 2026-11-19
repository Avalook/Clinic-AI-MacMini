"""Làm dịch vụ TẠI BÀN KHÁM cũng ghi bác sĩ thực hiện (Tuyền 19/11/2026).

Bẫy đã cắn: đường [Bắt đầu]/[Hoàn tất] ở phòng gọi `_bu_bac_si`, đường [Làm tại
bàn khám] thì không → staging 04–19/11: 12/12 chỉ định làm tại bàn khám có
`bac_si_lam_id` trống (cột BS thực hiện ở Xuất hoá đơn, KPI bác sĩ)."""

from collections.abc import AsyncIterator

import asyncpg
import pytest
import pytest_asyncio

from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    pool,
)
from tests.services.test_dieu_tri_ban_kham_db import (
    _bam,
    _ke,
    _laser,
    _lich_ban_kham,
    _the,
    _vao_kham,
)
from tests.services.test_thu_tien_xep_phong_mang_sang_db import (
    _benh_nhan,
    _check_in,
    _dung,
)
from tests.services.test_thu_truoc_lam_truoc_tick_db import day_thu_truoc

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


@pytest_asyncio.fixture(autouse=True)
async def _chua_thu_lam_duoc(pool: asyncpg.Pool) -> AsyncIterator[None]:  # noqa: F811
    async with day_thu_truoc(pool, False):
        yield


async def _bs_lam(pool: asyncpg.Pool, order: str) -> str | None:  # noqa: F811
    v = await pool.fetchval(
        "SELECT bac_si_lam_id::text FROM service_order WHERE id = $1::uuid", order
    )
    return str(v) if v is not None else None


async def test_lam_tai_ban_kham_ghi_bac_si_thuc_hien(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    laser = await _laser(pool)
    await _lich_ban_kham(pool, ca)  # bác sĩ đứng ô bác sĩ của phòng bàn khám
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    con = await _vao_kham(pool, ca, visit)
    order = (await _ke(pool, ca, con, laser["ma"]))["order_ids"][0]
    assert await _bs_lam(pool, order) is None

    await _bam(pool, ca, visit, await _the(pool, ca, visit), "lam")
    assert await _bs_lam(pool, order) == ca.bac_si.staff_id
    ev = await pool.fetchval(
        "SELECT count(*) FROM domain_event WHERE aggregate_id = $1::uuid"
        " AND event_type = 'service.doctor_chosen'",
        order,
    )
    assert ev == 1, "đổi bác sĩ phải có sự kiện (hoàn tác / tra lại được)"

    # Bỏ trống giữa chừng (lịch đổi) → Xong điền bù, như đường ở phòng.
    await pool.execute(
        "UPDATE service_order SET bac_si_lam_id = NULL WHERE id = $1::uuid", order
    )
    await _bam(pool, ca, visit, await _the(pool, ca, visit), "xong")
    assert await _bs_lam(pool, order) == ca.bac_si.staff_id
