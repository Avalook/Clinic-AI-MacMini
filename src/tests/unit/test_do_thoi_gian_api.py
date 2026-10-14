"""Đo thời gian API + bể kết nối (14/10/2026, sau sự cố treo tối 12/10).

Tối 12/10 hơn 4.500 request chậm >3s, đỉnh 100s; log API không ghi thời gian xử
lý nên không biết API nào chậm và bể 10 kết nối có cạn không. Ba thứ được canh ở
đây: (1) đọc trần bể từ env mà không bao giờ ném, (2) số đo bể, (3) log request
chậm + cảnh báo bể đầy mà không lộ id trong đường dẫn.
"""

import asyncio
from collections.abc import Mapping, Sequence
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from structlog.testing import capture_logs

from clinicai.api import middleware
from clinicai.core.database import (
    be_ket_noi_dang_ban,
    doc_pool_max,
    thong_ke_be,
)


class BeGia:
    """Có đúng ba hàm đọc số đo mà asyncpg.Pool có."""

    def __init__(self, tong: int, ranh: int, tran: int) -> None:
        self._t, self._r, self._m = tong, ranh, tran

    def get_size(self) -> int:
        return self._t

    def get_idle_size(self) -> int:
        return self._r

    def get_max_size(self) -> int:
        return self._m


def test_tran_be_doc_tu_env_khong_bao_gio_nem() -> None:
    assert doc_pool_max(None) == 20
    assert doc_pool_max("") == 20
    assert doc_pool_max("rác") == 20
    assert doc_pool_max("12") == 12
    assert doc_pool_max(" 30 ") == 30
    # Ngoài 5–40 (gõ nhầm 2 hay 200) quay về mặc định, không để API chạy 2 kết
    # nối hoặc xin 200 kết nối của Postgres 100.
    assert doc_pool_max("2") == 20
    assert doc_pool_max("200") == 20
    assert doc_pool_max("-5") == 20


def test_thong_ke_be_va_nguong_day() -> None:
    assert thong_ke_be(BeGia(20, 5, 20)) == {
        "tong": 20,
        "ranh": 5,
        "ban": 15,
        "tran": 20,
    }
    assert thong_ke_be(object()) is None
    assert thong_ke_be(None) is None
    # Bể mở lười: mới mở 2/20, cả hai đang bận ≠ đầy (còn 18 chỗ để mở thêm).
    assert be_ket_noi_dang_ban(BeGia(2, 0, 20)) is False
    assert be_ket_noi_dang_ban(BeGia(20, 2, 20)) is False
    assert be_ket_noi_dang_ban(BeGia(20, 1, 20)) is True  # chỉ còn 1 kết nối rảnh
    assert be_ket_noi_dang_ban(BeGia(20, 0, 20)) is True
    assert be_ket_noi_dang_ban(object()) is False


def _app(pool: object | None) -> FastAPI:
    app = FastAPI()
    app.add_middleware(middleware.TimingMiddleware)
    if pool is not None:
        app.state.db_pool = pool

    @app.get("/khach/{ma}")
    async def khach(ma: str) -> dict[str, str]:
        await asyncio.sleep(0.03)
        return {"ma": ma}

    @app.get("/hong")
    async def hong() -> dict[str, str]:
        raise RuntimeError("hỏng")

    return app


async def _goi(app: FastAPI, *duong: str) -> list[int]:
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        return [(await c.get(d)).status_code for d in duong]


@pytest.fixture(autouse=True)
def _dat_lai(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(middleware, "_lan_canh_bao_be", 0.0)
    monkeypatch.setattr(middleware, "_dang_xu_ly", 0)


def _dong_log(
    logs: Sequence[Mapping[str, Any]], su_kien: str
) -> list[Mapping[str, Any]]:
    return [x for x in logs if x["event"] == su_kien]


async def test_request_cham_ghi_log_voi_route_template_khong_lo_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(middleware, "SLOW_REQUEST_MS", 10.0)
    app = _app(BeGia(20, 18, 20))
    with capture_logs() as logs:
        assert await _goi(app, "/khach/BN-0123-NGUYEN-VAN-A") == [200]
    [cham] = _dong_log(logs, "api_cham")
    assert cham["route"] == "/khach/{ma}"
    assert cham["method"] == "GET" and cham["status"] == 200
    assert cham["duration_ms"] >= 10
    assert (cham["tong"], cham["ranh"], cham["ban"], cham["tran"]) == (20, 18, 2, 20)
    assert cham["dang_xu_ly"] == 0
    # Đường dẫn thật (có mã khách) không được lọt vào bất kỳ trường nào.
    assert "BN-0123" not in repr(logs)


async def test_request_nhanh_khong_ghi_log(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(middleware, "SLOW_REQUEST_MS", 60_000.0)
    with capture_logs() as logs:
        await _goi(_app(BeGia(20, 18, 20)), "/khach/x")
    assert _dong_log(logs, "api_cham") == []


async def test_be_gan_day_canh_bao_toi_da_mot_lan_moi_5_giay() -> None:
    app = _app(BeGia(20, 0, 20))
    with capture_logs() as logs:
        await _goi(app, "/khach/a", "/khach/b", "/khach/c")
    [canh_bao] = _dong_log(logs, "db_pool_gan_day")
    assert canh_bao["ban"] == 20 and canh_bao["tran"] == 20
    assert canh_bao["dang_xu_ly"] == 1


async def test_be_con_rong_khong_canh_bao() -> None:
    with capture_logs() as logs:
        await _goi(_app(BeGia(20, 15, 20)), "/khach/a")
    assert _dong_log(logs, "db_pool_gan_day") == []


async def test_khong_co_be_hoac_loi_van_chay_va_dem_tro_ve_khong() -> None:
    # Không gắn bể (test, hay khởi động dở): không ném, không log nhầm.
    with capture_logs() as logs:
        assert await _goi(_app(None), "/khach/a") == [200]
    assert _dong_log(logs, "db_pool_gan_day") == []
    # Handler ném: số "đang xử lý" vẫn về 0, không kẹt dương mãi.
    assert await _goi(_app(BeGia(20, 18, 20)), "/hong") == [500]
    assert middleware._dang_xu_ly == 0
