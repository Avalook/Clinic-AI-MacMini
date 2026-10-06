"""Lượt đồng bộ mật khẩu định kỳ trong su-kien: hỏng thì ghi kho lỗi, không ném."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import asyncpg
import pytest

from clinicai.services import dong_bo_mat_khau, kho_loi


@pytest.mark.asyncio
async def test_loi_ghi_kho_loi_va_khong_nem(monkeypatch: pytest.MonkeyPatch) -> None:
    pool: Any = AsyncMock()
    pool.fetchrow.side_effect = asyncpg.PostgresConnectionError("mất kết nối")
    ghi = AsyncMock()
    monkeypatch.setattr(kho_loi, "ghi_loi", ghi)

    assert await dong_bo_mat_khau.mot_vong(pool) is None

    ghi.assert_awaited_once()
    goi = ghi.await_args
    assert goi is not None
    assert goi.kwargs["nguon"] == "worker"
    assert goi.kwargs["vi_tri"] == "dong_bo_app_credential"


@pytest.mark.asyncio
async def test_goi_ham_sql_cho_moi_nhan_vien_khong_mo_lai() -> None:
    pool: Any = AsyncMock()
    pool.fetchrow.return_value = {"them": 2, "sua": 1, "mo_lai": 0, "trung_email": 0}

    ket = await dong_bo_mat_khau.mot_vong(pool)

    assert ket == {"them": 2, "sua": 1, "mo_lai": 0, "trung_email": 0}
    goi = pool.fetchrow.await_args
    assert goi is not None
    sql, staff_id, mo_lai = goi.args
    assert "dong_bo_app_credential" in sql
    assert staff_id is None and mo_lai is False
