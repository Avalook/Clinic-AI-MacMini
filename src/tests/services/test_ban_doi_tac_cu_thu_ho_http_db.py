"""KHÔNG LÀM VỠ NHÂN VIÊN ĐANG DÙNG — bàn đối tác CŨ ghi thu hộ hằng ngày trên prod
(SQL chặng 0, 05/11/2026: lần cuối 04/11). Chặng 2 thêm `tien_mat`/`chuyen_khoan` +
CHECK `so_tien = tien_mat + chuyen_khoan` ⇒ cửa cũ phải vẫn chạy và điền đúng cột mới.

Gọi ĐÚNG cửa HTTP cũ (`POST /doi-tac/viec/{id}/da-thu-tien`, `…/huy-da-thu`) qua app
thật; chỉ thay nguồn danh tính (`_resolve_identity`) — cửa quyền `partner.work` của
`get_partner_identity` vẫn chạy thật. GIỮ test này tới khi tắt bàn cũ (chặng 4).
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import asyncpg
import pytest
from httpx import ASGITransport, AsyncClient

from clinicai.api.identity import StaffIdentity, _resolve_identity
from clinicai.core.database import get_db_pool
from clinicai.main import app
from tests.services.test_doi_tac_tu_thu_db import _nguoi_vai, _viec_da_nhan
from tests.services.test_luot_kham_service_db import CLINIC
from tests.services.test_tien_thuoc_cp1_db import tao_quay

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


def _dat_nguoi(pool: asyncpg.Pool, ai: StaffIdentity) -> None:
    async def _pool() -> AsyncIterator[asyncpg.Pool]:
        yield pool

    app.dependency_overrides[get_db_pool] = _pool
    app.dependency_overrides[_resolve_identity] = lambda: ai


def _bo_ghi_de() -> None:
    app.dependency_overrides.pop(get_db_pool, None)
    app.dependency_overrides.pop(_resolve_identity, None)


async def _dong(pool: asyncpg.Pool, oid: str) -> asyncpg.Record:
    r = await pool.fetchrow(
        "SELECT so_tien, tien_mat, chuyen_khoan, hinh_thuc FROM doi_tac_thanh_toan"
        " WHERE clinic_id = $1::uuid AND service_order_id = $2::uuid"
        " AND huy_luc IS NULL",
        CLINIC,
        oid,
    )
    assert r is not None
    return r


@pytest.mark.parametrize(
    ("hinh_thuc", "cot"), [("CASH", "tien_mat"), ("TRANSFER", "chuyen_khoan")]
)
async def test_cua_cu_ghi_thu_dien_dung_cot_moi_va_huy_van_chay(
    pool: asyncpg.Pool, hinh_thuc: str, cot: str
) -> None:
    q = await tao_quay(pool)
    dt = await _nguoi_vai(q, "PARTNER")
    oid = await _viec_da_nhan(q)
    api = f"/api/v1/doi-tac/viec/{oid}"
    try:
        _dat_nguoi(pool, dt)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            r = await c.post(
                f"{api}/da-thu-tien",
                json={"so_tien": "900.000", "hinh_thuc": hinh_thuc, "ghi_chu": "ok"},
            )
            assert r.status_code == 200, r.text
            d = await _dong(pool, oid)
            assert d["so_tien"] == 900_000 and d["hinh_thuc"] == hinh_thuc
            assert d[cot] == 900_000
            khac = "chuyen_khoan" if cot == "tien_mat" else "tien_mat"
            assert d[khac] == 0

            r = await c.post(f"{api}/huy-da-thu", json={"ly_do": "ghi nhầm số"})
            assert r.status_code == 200, r.text
            assert r.json()["already"] is False
            assert not await pool.fetchval(
                "SELECT count(*) FROM doi_tac_thanh_toan WHERE clinic_id = $1::uuid"
                " AND service_order_id = $2::uuid AND huy_luc IS NULL",
                CLINIC,
                oid,
            )
            # Huỷ xong ghi lại được (đường "sửa số" của bàn cũ).
            r = await c.post(
                f"{api}/da-thu-tien", json={"so_tien": 800000, "hinh_thuc": hinh_thuc}
            )
            assert r.status_code == 200, r.text
            assert (await _dong(pool, oid))[cot] == 800_000
    finally:
        _bo_ghi_de()
