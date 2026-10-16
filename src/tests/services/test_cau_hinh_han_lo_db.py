"""Ngưỡng cảnh báo là dữ liệu, quyền cấu hình do máy chủ trả."""

# ruff: noqa: F811
from unittest.mock import AsyncMock

import pytest

from clinicai.api.v1.routers import pharmacy
from clinicai.services import lo_thuoc_service as lo
from tests.services.test_tien_thuoc_cp1_db import Quay, q  # noqa: F401

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


@pytest.mark.parametrize("duoc", [False, True])
async def test_quyen_chinh_canh_bao_tu_server(
    q: Quay, monkeypatch: pytest.MonkeyPatch, duoc: bool
) -> None:
    quyen = AsyncMock(return_value=duoc)
    monkeypatch.setattr(pharmacy, "can", quyen)
    result = await pharmacy.so_ngay_canh_bao(identity=q.duoc_si, pool=q.pool)
    assert result["sua_canh_bao_duoc"] is duoc
    assert quyen.await_args is not None
    assert quyen.await_args.args[1:] == (q.duoc_si, "config.clinic.manage")


async def test_ngay_canh_bao_luu_va_doc_lai(q: Quay) -> None:
    async with q.pool.acquire() as conn:
        cu = await lo.so_ngay_canh_bao(conn, q.duoc_si.clinic_id)
    try:
        await lo.doi_canh_bao(q.pool, identity=q.duoc_si, so_ngay=0)
        async with q.pool.acquire() as conn:
            assert await lo.so_ngay_canh_bao(conn, q.duoc_si.clinic_id) == 0
    finally:
        await lo.doi_canh_bao(q.pool, identity=q.duoc_si, so_ngay=cu)
