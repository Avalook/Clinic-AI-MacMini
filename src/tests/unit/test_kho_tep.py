"""Chạm ổ tệp không làm treo vòng sự kiện (sự cố 29/09/2026 20:00)."""

from __future__ import annotations

import asyncio
import threading
import time
from collections.abc import Iterator

import pytest

from clinicai.core import kho_tep
from clinicai.core.exceptions import ExternalServiceError


@pytest.fixture(autouse=True)
def _mo_lai() -> Iterator[None]:
    kho_tep.mo_lai()
    yield
    # Không để trạng thái ngắt mạch rò sang test khác.
    kho_tep.mo_lai()


@pytest.mark.asyncio
async def test_tra_ket_qua_khi_nhanh() -> None:
    assert await kho_tep.chay_tren_kho(lambda: 42) == 42


@pytest.mark.asyncio
async def test_o_treo_thi_tra_loi_ma_vong_su_kien_van_chay() -> None:
    nha = threading.Event()

    def treo() -> None:
        nha.wait(5)

    nhip = 0

    async def dem() -> None:
        nonlocal nhip
        while True:
            nhip += 1
            await asyncio.sleep(0.01)

    task = asyncio.create_task(dem())
    t0 = time.monotonic()
    with pytest.raises(ExternalServiceError):
        await kho_tep.chay_tren_kho(treo, han=0.2)
    assert time.monotonic() - t0 < 1.0
    assert nhip > 5  # vòng sự kiện vẫn chạy trong lúc chờ
    task.cancel()
    nha.set()


@pytest.mark.asyncio
async def test_ngat_mach_tra_loi_ngay_khong_de_them_luong() -> None:
    nha = threading.Event()
    with pytest.raises(ExternalServiceError):
        await kho_tep.chay_tren_kho(lambda: nha.wait(5), han=0.05)
    goi = []
    with pytest.raises(ExternalServiceError):
        await kho_tep.chay_tren_kho(lambda: goi.append(1))
    assert goi == []  # đang ngắt: không chạy hàm, không tạo luồng
    nha.set()
