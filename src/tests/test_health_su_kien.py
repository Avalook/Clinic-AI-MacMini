"""Điểm đo sức khoẻ người đưa tin — ``GET /health/su-kien`` (27/09/2026).

Luật "worker im" đo theo tin ĐÃ TỚI HẠN mà chưa giao, KHÔNG theo lần giao
cuối: giờ vắng khách worker im cả tiếng là bình thường, tin mới vào hàng
không được làm đèn đỏ.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator
from typing import Any

import asyncpg
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from clinicai.api.v1.health import danh_gia_su_kien
from clinicai.core.database import get_db_pool
from clinicai.main import app

KHOE = {
    "dang_cho": 4,
    "tre_giao": 0,
    "ton_lau": 0,
    "chet_24h": 0,
    "hen_gio_tre": 0,
    "hen_gio_chet_24h": 0,
}


def test_tin_dang_cho_ma_chua_tre_la_khoe() -> None:
    assert danh_gia_su_kien(KHOE) == []


@pytest.mark.parametrize(
    ("khoa", "chu"),
    [
        ("tre_giao", "worker chết"),
        ("ton_lau", "tồn quá"),
        ("chet_24h", "DEAD"),
        ("hen_gio_tre", "hẹn giờ trễ"),
        ("hen_gio_chet_24h", "hẹn giờ chết"),
    ],
)
def test_moi_so_khac_khong_deu_thanh_mot_ly_do(khoa: str, chu: str) -> None:
    ly_do = danh_gia_su_kien({**KHOE, khoa: 2})
    assert len(ly_do) == 1
    assert chu in ly_do[0] and "2" in ly_do[0]


@pytest_asyncio.fixture
async def pool() -> Any:
    url = os.environ.get("DATABASE_URL") or ""
    if not url:
        pytest.skip("cần DATABASE_URL_TEST trỏ tới database dùng một lần")
    dsn = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    p = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=2)
    yield p
    await p.close()


async def _goi(pool: asyncpg.Pool) -> tuple[int, dict[str, Any]]:
    async def ghi_de() -> AsyncIterator[asyncpg.Pool]:
        yield pool

    app.dependency_overrides[get_db_pool] = ghi_de
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r = await client.get("/health/su-kien")
    finally:
        app.dependency_overrides.clear()
    return r.status_code, r.json()


@pytest.mark.db
@pytest.mark.asyncio
async def test_tin_toi_han_nam_lau_thi_503_tin_moi_thi_khong(
    pool: asyncpg.Pool,
) -> None:
    truoc_ma, truoc = await _goi(pool)
    assert set(truoc["so"]) == set(KHOE)

    event_id = await pool.fetchval("SELECT event_id FROM domain_event LIMIT 1")
    if event_id is None:
        pytest.skip("database thử chưa có sự kiện nào")
    ben_nhan = f"thu_suc_khoe_{uuid.uuid4().hex[:8]}"
    clinic = await pool.fetchval("SELECT id FROM clinic LIMIT 1")
    try:
        # Tin MỚI (vừa vào hàng): không được đổi đèn.
        await pool.execute(
            "INSERT INTO event_delivery (event_id, consumer, clinic_id,"
            " aggregate_id, aggregate_version) VALUES ($1, $2, $3, $4, 1)",
            event_id,
            ben_nhan + "_moi",
            clinic,
            uuid.uuid4(),
        )
        _, moi = await _goi(pool)
        assert moi["so"]["tre_giao"] == truoc["so"]["tre_giao"]
        assert moi["so"]["dang_cho"] == truoc["so"]["dang_cho"] + 1

        # Tin tới hạn 10 phút, tồn 20 phút: worker chết → 503.
        await pool.execute(
            "INSERT INTO event_delivery (event_id, consumer, clinic_id,"
            " aggregate_id, aggregate_version, created_at, next_attempt_at)"
            " VALUES ($1, $2, $3, $4, 1, now() - interval '20 minutes',"
            " now() - interval '10 minutes')",
            event_id,
            ben_nhan + "_tre",
            clinic,
            uuid.uuid4(),
        )
        ma, sau = await _goi(pool)
        assert ma == 503
        assert sau["status"] == "degraded"
        assert sau["so"]["tre_giao"] == truoc["so"]["tre_giao"] + 1
        assert sau["so"]["ton_lau"] == truoc["so"]["ton_lau"] + 1
        assert any("worker" in x for x in sau["ly_do"])
        # Chỉ số đếm — không lộ mã đối tượng / tên bên nhận.
        assert ben_nhan not in str(sau)
    finally:
        await pool.execute(
            "DELETE FROM event_delivery WHERE consumer LIKE $1", ben_nhan + "%"
        )
    assert truoc_ma in (200, 503)
