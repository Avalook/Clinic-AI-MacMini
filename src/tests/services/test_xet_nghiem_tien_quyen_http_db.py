"""Tab "Tiền thu hộ" của bàn XN CHỈ quản lý (Tuyền chốt 05/11 theo bản mẫu).

Chặn ở MÁY CHỦ (`GET /xet-nghiem/ban/tien` qua cửa `config.clinic.manage`), không chỉ ẩn
tab. Gọi app thật; chỉ thay nguồn danh tính — cửa quyền chạy thật.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import asyncpg
import pytest
from httpx import ASGITransport, AsyncClient

from clinicai.api.identity import StaffIdentity, _resolve_identity
from clinicai.core.database import get_db_pool
from clinicai.main import app
from tests.services.test_doi_tac_tu_thu_db import _nguoi_vai
from tests.services.test_tien_thuoc_cp1_db import tao_quay

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]

API = "/api/v1/xet-nghiem/ban/tien"


async def _goi(pool: asyncpg.Pool, ai: StaffIdentity, url: str) -> int:
    async def _pool() -> AsyncIterator[asyncpg.Pool]:
        yield pool

    app.dependency_overrides[get_db_pool] = _pool
    app.dependency_overrides[_resolve_identity] = lambda: ai
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            return (await c.get(url)).status_code
    finally:
        app.dependency_overrides.pop(get_db_pool, None)
        app.dependency_overrides.pop(_resolve_identity, None)


@pytest.mark.parametrize("vai", ["RECEPTION", "CSKH", "DOCTOR", "CASHIER"])
async def test_nhan_vien_goi_tien_thu_ho_bi_403(pool: asyncpg.Pool, vai: str) -> None:
    q = await tao_quay(pool)
    assert await _goi(pool, await _nguoi_vai(q, vai), API) == 403


async def test_bang_quyen_quan_ly_doc_duoc_nhan_vien_403(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Bảng Quyền (tab Cài đặt) đọc quyền THỰC TẾ — staging 05/11 từng 500 vì SQL nối
    `staff.clinic_id` (cột không có). Quản lý thấy chính mình có cả hai quyền."""
    q = await tao_quay(pool)
    ql = await _nguoi_vai(q, "MANAGEMENT")
    url = "/api/v1/xet-nghiem/quyen"
    assert await _goi(pool, await _nguoi_vai(q, "RECEPTION"), url) == 403

    async def _pool() -> AsyncIterator[asyncpg.Pool]:
        yield pool

    app.dependency_overrides[get_db_pool] = _pool
    app.dependency_overrides[_resolve_identity] = lambda: ql
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            r = await c.get(url)
    finally:
        app.dependency_overrides.pop(get_db_pool, None)
        app.dependency_overrides.pop(_resolve_identity, None)
    assert r.status_code == 200, r.text
    toi = [n for n in r.json()["nguoi"] if n["staff_id"] == ql.staff_id]
    assert toi and toi[0]["quan_ly"] is True


async def test_quan_ly_doc_duoc_tien_thu_ho_ngay_rac_van_200(
    pool: asyncpg.Pool,
) -> None:
    q = await tao_quay(pool)
    ql = await _nguoi_vai(q, "MANAGEMENT")
    assert await _goi(pool, ql, API) == 200
    assert await _goi(pool, ql, f"{API}?ngay=2026-13-40") == 200
