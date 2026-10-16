"""Quan sát API (14/10/2026): log request chậm, đo chờ mượn kết nối, cảnh báo bể đầy.

Mục tiêu: lần sau API chậm cả hệ thống như tối 12/10 thì log TỰ nói bể kết nối có
cạn không — không phải đoán từ log Caddy.
"""

from __future__ import annotations

import asyncio
import inspect
import json
from typing import Any

import asyncpg
import asyncpg.pool
import httpx
import pytest
import structlog
import structlog.testing
from fastapi import FastAPI

from clinicai.api.middleware import RequestIdMiddleware, TimingMiddleware
from clinicai.core import quan_sat as qs
from clinicai.core.database import (
    POOL_MAX_SIZE,
    WORKER_POOL_MAX_SIZE,
    doc_pool_max_size_api,
)
from clinicai.services import canh_gac_pool as cg


@pytest.fixture
def q() -> qs.QuanSat:
    return qs.QuanSat()


# ---------------------------------------------------------------- request chậm


def test_request_nhanh_khong_ghi_dong_rieng_nhung_van_dem(q: qs.QuanSat) -> None:
    q.request_bat_dau()
    assert q.request_xong(route="/a", method="GET", status=200, ms=499.9) is False
    tom = q.chot_phut()
    assert tom["so_request"] == 1 and tom["so_cham_500ms"] == 0


def test_request_cham_ghi_dong_rieng_va_gom_theo_route(q: qs.QuanSat) -> None:
    for ms in (600.0, 1800.0, 90.0):
        q.request_bat_dau()
        q.request_xong(route="/api/v1/x/{id}", method="GET", status=200, ms=ms)
    tom = q.chot_phut()
    assert tom["so_request"] == 3 and tom["so_cham_500ms"] == 2
    assert tom["max_ms"] == 1800.0
    top = tom["top_route_cham"]
    assert top == [{"route": "GET /api/v1/x/{id}", "so_lan": 2, "max_ms": 1800.0}]


def test_tran_dong_log_moi_phut_phan_vuot_van_duoc_dem(q: qs.QuanSat) -> None:
    ghi = sum(
        q.request_xong(route="/a", method="GET", status=200, ms=900.0)
        for _ in range(qs.TRAN_DONG_CHAM_MOI_PHUT + 25)
    )
    assert ghi == qs.TRAN_DONG_CHAM_MOI_PHUT
    tom = q.chot_phut()
    assert tom["so_cham_500ms"] == qs.TRAN_DONG_CHAM_MOI_PHUT + 25
    assert tom["dong_log_cham_bi_nen"] == 25
    # Phút mới: quota làm mới.
    assert q.request_xong(route="/a", method="GET", status=200, ms=900.0) is True


def test_dong_cung_luc_dinh_va_ke_thua_qua_phut(q: qs.QuanSat) -> None:
    for _ in range(3):
        q.request_bat_dau()
    q.request_xong(route="/a", method="GET", status=200, ms=1.0)
    tom = q.chot_phut()
    assert tom["dong_cung_luc_max"] == 3
    # Còn 2 request đang bay khi sang phút mới.
    assert q.chot_phut()["dong_cung_luc_max"] == 2


# ----------------------------------------------------------------------- pool


def test_cho_muon_qua_2s_ghi_log_va_quota(q: qs.QuanSat) -> None:
    q.muon_bat_dau()
    assert q.muon_xong(5.0) is False
    ghi = 0
    for _ in range(qs.TRAN_DONG_POOL_MOI_PHUT + 5):
        q.muon_bat_dau()
        ghi += q.muon_xong(qs.NGUONG_CHO_POOL_MS + 1)
    assert ghi == qs.TRAN_DONG_POOL_MOI_PHUT
    p = q.chot_phut()["pool"]
    assert p["so_cho_qua_2s"] == qs.TRAN_DONG_POOL_MOI_PHUT + 5
    assert p["so_muon_phai_cho"] == qs.TRAN_DONG_POOL_MOI_PHUT + 5
    assert p["cho_max_ms"] >= qs.NGUONG_CHO_POOL_MS


def test_dang_cho_dem_nguoi_cho_cung_luc(q: qs.QuanSat) -> None:
    for _ in range(4):
        q.muon_bat_dau()
    assert q.dang_cho() == 4
    for _ in range(4):
        q.muon_xong(1.0)
    assert q.dang_cho() == 0
    assert q.chot_phut()["pool"]["dang_cho_max"] == 4


def test_mau_day_hai_giay_lien_tiep_moi_bao_mot_lan(q: qs.QuanSat) -> None:
    assert q.lay_mau_pool(20, 20) is None
    assert q.lay_mau_pool(20, 20) == "day"
    assert q.lay_mau_pool(20, 20) is None  # cùng một đợt: không lặp
    q.lay_mau_pool(3, 20)  # hết đầy
    assert q.lay_mau_pool(20, 20) is None
    assert q.lay_mau_pool(20, 20) == "day"  # đợt mới


def test_ban_cao_keo_dai_muoi_giay_moi_bao(q: qs.QuanSat) -> None:
    ket = [q.lay_mau_pool(16, 20) for _ in range(qs.NGUONG_BAN_LIEN_TIEP_GIAY)]
    assert ket[:-1] == [None] * (qs.NGUONG_BAN_LIEN_TIEP_GIAY - 1)
    assert ket[-1] == "ban_keo_dai"
    p = q.chot_phut()["pool"]
    assert p["giay_ban_cao_lien_max"] == qs.NGUONG_BAN_LIEN_TIEP_GIAY
    assert p["giay_day"] == 0 and p["ban_max"] == 16


def test_ban_cao_ngat_quang_khong_tinh_lien_tiep(q: qs.QuanSat) -> None:
    for _ in range(3):
        for _ in range(qs.NGUONG_BAN_LIEN_TIEP_GIAY - 1):
            assert q.lay_mau_pool(18, 20) is None
        q.lay_mau_pool(2, 20)
    assert q.chot_phut()["pool"]["giay_ban_cao_lien_max"] < (
        qs.NGUONG_BAN_LIEN_TIEP_GIAY
    )


# ------------------------------------------------------------ bọc Pool._acquire


def test_asyncpg_con_hat_acquire_rieng_tu_ma_ta_boc() -> None:
    """Nâng asyncpg mà đổi/mất `Pool._acquire` thì bài này đỏ — tín hiệu để sửa
    `gan_do_pool` (không thì mất số đo im lặng)."""
    ham = asyncpg.pool.Pool._acquire
    assert list(inspect.signature(ham).parameters) == ["self", "timeout"]
    assert inspect.iscoroutinefunction(ham)


class _PoolGia:
    """Chỉ có phần `do_acquire` đọc: kích cỡ bể."""

    def get_size(self) -> int:
        return 5

    def get_idle_size(self) -> int:
        return 1

    def get_max_size(self) -> int:
        return 5

    def get_min_size(self) -> int:
        return 2


def _muon(tre: float, loi: Exception | None = None) -> Any:
    async def _goc(timeout: Any) -> str:
        await asyncio.sleep(tre)
        if loi:
            raise loi
        return "conn"

    return _goc


@pytest.fixture
def quan_sat_sach(monkeypatch: pytest.MonkeyPatch) -> qs.QuanSat:
    moi = qs.QuanSat()
    monkeypatch.setattr(qs, "quan_sat", moi)
    moi.pool_max = 5
    return moi


async def test_do_acquire_do_thoi_gian_cho(quan_sat_sach: qs.QuanSat) -> None:
    pool = _PoolGia()
    with structlog.testing.capture_logs() as logs:
        kq = await asyncio.gather(
            *(qs.do_acquire(_muon(0.15), None, pool) for _ in range(3))
        )
    assert kq == ["conn"] * 3
    p = quan_sat_sach.chot_phut()["pool"]
    assert p["so_muon"] == 3 and p["so_muon_phai_cho"] == 3
    assert p["dang_cho_max"] == 3 and p["toi_da"] == 5
    assert p["cho_max_ms"] >= 140
    assert quan_sat_sach.dang_cho() == 0
    assert logs == []  # chưa tới 2s: không ghi dòng cảnh báo


async def test_do_acquire_cho_qua_nguong_ghi_pool_cho_lau(
    quan_sat_sach: qs.QuanSat, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(qs, "NGUONG_CHO_POOL_MS", 50.0)
    with structlog.testing.capture_logs() as logs:
        await qs.do_acquire(_muon(0.08), None, _PoolGia())
    (dong,) = [x for x in logs if x["event"] == "pool_cho_lau"]
    assert dong["log_level"] == "warning"
    assert dong["toi_da"] == 5 and dong["ban"] == 4 and dong["cho_ms"] >= 70


async def test_do_acquire_van_tra_so_khi_mat_ket_noi_hoac_bi_huy(
    quan_sat_sach: qs.QuanSat,
) -> None:
    with pytest.raises(ConnectionError):
        await qs.do_acquire(_muon(0.01, ConnectionError("rớt")), None, _PoolGia())
    assert quan_sat_sach.dang_cho() == 0  # không rò bộ đếm "đang chờ"

    t = asyncio.create_task(qs.do_acquire(_muon(5), None, _PoolGia()))
    await asyncio.sleep(0.02)
    assert quan_sat_sach.dang_cho() == 1
    t.cancel()
    with pytest.raises(asyncio.CancelledError):
        await t
    assert quan_sat_sach.dang_cho() == 0


async def test_gan_do_pool_doi_lop_bể_asyncpg_that_chua_noi_db(
    quan_sat_sach: qs.QuanSat,
) -> None:
    """`create_pool` chưa await = một `Pool` chưa nối DB: đủ để thấy việc đổi
    lớp chạy được trên asyncpg thật và `_acquire` đi qua bộ đo."""
    pool = asyncpg.create_pool("postgresql://x@127.0.0.1:1/x", min_size=1, max_size=7)
    assert qs.gan_do_pool(pool) is True
    assert type(pool).__name__ == "_PoolCoDo" and isinstance(pool, asyncpg.Pool)
    assert quan_sat_sach.pool_max == 7
    with pytest.raises(asyncpg.InterfaceError):  # chưa khởi tạo → từ chối ngay
        await pool._acquire(None)
    p = quan_sat_sach.chot_phut()["pool"]
    assert p["so_muon"] == 1 and quan_sat_sach.dang_cho() == 0


def test_gan_do_pool_khong_lam_hong_app_khi_khong_phai_pool_asyncpg() -> None:
    class KhongPhaiPool:
        pass

    assert qs.gan_do_pool(KhongPhaiPool()) is False


# ---------------------------------------------------------- middleware end-to-end


def _app_thu() -> FastAPI:
    app = FastAPI()

    @app.get("/khach/{ma}")
    async def khach(ma: str) -> dict[str, str]:
        await asyncio.sleep(0.03)
        return {"ok": "1"}

    app.add_middleware(TimingMiddleware)
    app.add_middleware(RequestIdMiddleware)
    return app


async def test_middleware_ghi_request_cham_bang_mau_duong_dan_khong_ghi_ma_khach(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    moi = qs.QuanSat()
    monkeypatch.setattr("clinicai.api.middleware.quan_sat", moi)
    monkeypatch.setattr(qs, "NGUONG_CHAM_MS", 10.0)
    ma_khach = "KH-0901234567-NGUYEN"
    transport = httpx.ASGITransport(app=_app_thu())
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        with structlog.testing.capture_logs() as logs:
            r = await c.get(f"/khach/{ma_khach}?q=0901234567")
    assert r.status_code == 200
    (dong,) = [x for x in logs if x["event"] == "request_cham"]
    assert dong["path"] == "/khach/{ma}"
    assert dong["method"] == "GET" and dong["status"] == 200 and dong["ms"] >= 25
    assert dong["request_id"] == r.headers["X-Request-ID"]
    # Không chỗ nào trong dòng log có mã khách / số điện thoại / query.
    chu = json.dumps(dong, default=str)
    assert ma_khach not in chu and "0901234567" not in chu
    tom = moi.chot_phut()
    assert tom["so_request"] == 1 and tom["so_cham_500ms"] == 1
    assert tom["top_route_cham"][0]["route"] == "GET /khach/{ma}"


async def test_middleware_request_nhanh_khong_ghi_dong_cham(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("clinicai.api.middleware.quan_sat", qs.QuanSat())
    transport = httpx.ASGITransport(app=_app_thu())
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        with structlog.testing.capture_logs() as logs:
            await c.get("/khach/x")
    assert [x for x in logs if x["event"] == "request_cham"] == []


# ------------------------------------------------------ đánh giá + chống nháy


def _tom(**pool: Any) -> dict[str, Any]:
    p = {
        "toi_da": 20,
        "ban_max": 4,
        "so_cho_qua_2s": 0,
        "cho_max_ms": 3.0,
        "giay_ban_cao_lien_max": 0,
    }
    p.update(pool)
    return {"so_request": 800, "p95_ms": 120.0, "pool": p}


def test_binh_thuong_khong_co_dau_hieu() -> None:
    co, nd = cg.danh_gia_phut(_tom())
    assert co is False and "bình thường" in nd


def test_cho_qua_2s_la_dau_hieu_va_noi_dung_chi_co_so() -> None:
    co, nd = cg.danh_gia_phut(_tom(so_cho_qua_2s=7, cho_max_ms=9300.0))
    assert co is True
    assert "7 lần" in nd and "9.3s" in nd and "800 request" in nd


def test_ban_cao_keo_dai_la_dau_hieu() -> None:
    co, nd = cg.danh_gia_phut(_tom(giay_ban_cao_lien_max=45, ban_max=20))
    assert co is True and "45 giây" in nd and "20/20" in nd


def test_ban_cao_ngan_hon_nguong_khong_phai_dau_hieu() -> None:
    co, _ = cg.danh_gia_phut(_tom(giay_ban_cao_lien_max=9))
    assert co is False


def test_chong_nhay_mo_ngay_dong_sau_3_phut_on() -> None:
    c = cg.ChongNhay()
    assert c.cap_nhat(False) is None  # chưa từng mở: không đóng vô cớ
    assert c.cap_nhat(False) is None and c.cap_nhat(False) is None
    assert c.cap_nhat(True) is True
    assert [c.cap_nhat(False), c.cap_nhat(False)] == [None, None]
    assert c.cap_nhat(True) is True  # tái phát: đếm ổn làm lại từ đầu
    assert [c.cap_nhat(False) for _ in range(3)] == [None, None, False]
    assert c.cap_nhat(False) is None  # đã đóng, không đóng lại


async def test_chot_phut_ghi_dong_tong_hop_va_mo_canh_bao(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    moi = qs.QuanSat()
    monkeypatch.setattr(cg, "quan_sat", moi)
    goi: list[Any] = []

    async def _ap(pool: Any, kq: list[Any]) -> None:
        goi.append((pool, kq))

    monkeypatch.setattr(cg, "ap_dung", _ap)
    moi.request_bat_dau()
    moi.request_xong(route="/a", method="GET", status=200, ms=700.0)
    moi.muon_bat_dau()
    moi.muon_xong(qs.NGUONG_CHO_POOL_MS + 500)
    chong = cg.ChongNhay()
    with structlog.testing.capture_logs() as logs:
        tom = await cg.chot_phut("POOL_PHU", chong)
    assert tom is not None and moi.phut_gan_nhat is tom
    (nhip,) = [x for x in logs if x["event"] == "api_nhip_phut"]
    assert nhip["so_request"] == 1 and nhip["pool"]["so_cho_qua_2s"] == 1
    (pool_dung, (kq,)) = goi[0]
    assert pool_dung == "POOL_PHU"  # ghi bằng bể phụ, không bằng bể chính
    assert (kq.ma, kq.muc, kq.co_chuyen) == ("POOL_API_DAY", "warning", True)


async def test_chot_phut_khong_bao_gio_nem(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _hong(*_a: Any, **_k: Any) -> None:
        raise RuntimeError("DB chết")

    moi = qs.QuanSat()
    monkeypatch.setattr(cg, "quan_sat", moi)
    monkeypatch.setattr(cg, "ap_dung", _hong)
    moi.muon_bat_dau()
    moi.muon_xong(qs.NGUONG_CHO_POOL_MS + 1)
    with structlog.testing.capture_logs():
        assert await cg.chot_phut(None, cg.ChongNhay()) is None


# -------------------------------------------------------------- trần kết nối


def test_pool_max_size_mac_dinh_api_20_worker_10() -> None:
    assert POOL_MAX_SIZE == 20 and WORKER_POOL_MAX_SIZE == 10
    assert doc_pool_max_size_api("") == 20


def test_pool_max_size_doc_tu_moi_truong_va_gat_gia_tri_sai() -> None:
    assert doc_pool_max_size_api("12") == 12
    assert doc_pool_max_size_api(" 30 ") == 30
    for xau in ("0", "1", "-5", "abc", "1000", "20.5"):
        assert doc_pool_max_size_api(xau) == 20, xau


def test_bang_so_lieu_pool_tuc_thoi_khong_co_pool() -> None:
    assert qs.QuanSat().tuc_thoi() == {"co_pool": False}


def test_bang_so_lieu_pool_tuc_thoi_co_pool() -> None:
    q = qs.QuanSat()
    q.pool = _PoolGia()
    t = q.tuc_thoi()
    assert (t["toi_da"], t["dang_mo"], t["ranh"], t["ban"]) == (5, 5, 1, 4)
