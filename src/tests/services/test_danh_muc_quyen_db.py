"""Danh mục quyền trong code phải khớp danh mục trong database.

Hai bản sao là hai bản sẽ lệch. Bảng `capability` tồn tại để dòng cấp quyền khoá
ngoại được (cấp một quyền không tồn tại phải hỏng NGAY lúc ghi), còn code cần
danh mục để lệnh gọi tên quyền. Bài kiểm này là thứ giữ hai bên bằng nhau — thiếu
nó thì một hôm nào đó `can(...)` trả False mãi mãi vì DB không có dòng ấy, và
không ai hiểu vì sao nút bấm không ăn.
"""

from __future__ import annotations

import os
from typing import Any

import asyncpg
import pytest
import pytest_asyncio

from clinicai.permissions.catalogue import KHOI, PRESET, QUYEN

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


@pytest_asyncio.fixture
async def pool() -> Any:
    url = os.environ.get("DATABASE_URL") or ""
    if not url:
        pytest.skip("cần DATABASE_URL_TEST trỏ tới database dùng một lần")
    dsn = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    p = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=2)
    yield p
    await p.close()


async def test_khoi_cong_viec_khop(pool: asyncpg.Pool) -> None:
    rows = await pool.fetch("SELECT ma, ten, module FROM work_pack")
    assert {r["ma"] for r in rows} == set(KHOI)
    for r in rows:
        assert r["ten"] == KHOI[r["ma"]].ten
        assert r["module"] == KHOI[r["ma"]].module


async def test_quyen_khop(pool: asyncpg.Pool) -> None:
    rows = await pool.fetch(
        "SELECT ma, ten, work_pack, module, rui_ro, chung_chi_lam_sang FROM capability"
    )
    assert {r["ma"] for r in rows} == set(QUYEN)
    for r in rows:
        q = QUYEN[r["ma"]]
        assert r["ten"] == q.ten
        assert r["work_pack"] == q.khoi
        assert r["module"] == q.module
        assert r["rui_ro"] == q.rui_ro.value
        assert r["chung_chi_lam_sang"] == q.chung_chi_lam_sang


async def test_moi_quyen_thuoc_mot_khoi_co_that(pool: asyncpg.Pool) -> None:
    """Quyền mồ côi = quản lý không bao giờ bật được nó trên màn."""
    for ma, q in QUYEN.items():
        assert q.khoi in KHOI, f"Quyền {ma} thuộc khối không tồn tại: {q.khoi}"


async def test_preset_chi_tro_toi_khoi_co_that() -> None:
    for vai, khoi in PRESET.items():
        for k in khoi:
            assert k in KHOI, f"Preset {vai} trỏ tới khối không tồn tại: {k}"


async def test_moi_khoi_deu_co_quyen_con() -> None:
    """Khối rỗng hiện lên màn quản lý như một ô bật được mà bật xong không đổi gì."""
    co_quyen = {q.khoi for q in QUYEN.values()}
    thieu = set(KHOI) - co_quyen
    assert not thieu, f"Khối chưa có quyền con nào: {sorted(thieu)}"
