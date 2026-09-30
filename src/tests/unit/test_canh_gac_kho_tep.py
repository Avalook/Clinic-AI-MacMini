"""Canh gác kho tệp (29/09/2026): ổ giả lập nhanh / chậm / treo / lỗi."""

from __future__ import annotations

import asyncio
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from clinicai.services import canh_gac_kho_tep as ck
from clinicai.services.canh_gac import KetQuaKiem


@pytest.fixture(autouse=True)
def _sach(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[list[KetQuaKiem]]]:
    ck._luong = None
    ck.MOI_NHAT = None
    monkeypatch.setattr(ck, "_theo_doi", ck.TheoDoi())
    goi: list[list[KetQuaKiem]] = []

    async def _ap(_pool: Any, kq: list[KetQuaKiem]) -> None:
        goi.append(kq)

    monkeypatch.setattr(ck, "ap_dung", _ap)
    yield goi


@pytest.fixture
def cua_treo() -> Iterator[threading.Event]:
    ev = threading.Event()
    yield ev
    ev.set()  # thả luồng treo cho test sau


def _gia(ghi: float, doc: float) -> Any:
    return lambda _goc: (ghi, doc)


def test_do_that_tren_o_may(tmp_path: Path) -> None:
    ghi, doc = ck.do_dong_bo(tmp_path)
    assert ghi >= 0 and doc >= 0
    assert (tmp_path / ck.THU_MUC_DO / ck.TEN_TEP_DO).stat().st_size == ck.CO_TEP_DO


def test_thieu_tep_danh_dau_la_loi(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MEDIA_MARKER", ".kho-that")
    with pytest.raises(FileNotFoundError):
        ck.do_dong_bo(tmp_path)


async def test_nhanh_khong_mo(
    monkeypatch: pytest.MonkeyPatch, _sach: list[Any]
) -> None:
    monkeypatch.setattr(ck, "do_dong_bo", _gia(0.05, 0.1))
    pd = await ck.mot_vong(None, Path("/x"))
    assert pd is not None and not pd.cham
    assert pd.doc_kb_s == 2560.0
    assert ck.MOI_NHAT and ck.MOI_NHAT["cham"] is False
    assert _sach[-1][0].co_chuyen is None  # 1 lần ổn: chưa đóng
    await ck.mot_vong(None, Path("/x"))
    assert _sach[-1][0].co_chuyen is False  # 2 lần ổn: đóng


async def test_cham_hai_lan_moi_mo_roi_on_hai_lan_moi_dong(
    monkeypatch: pytest.MonkeyPatch, _sach: list[Any]
) -> None:
    monkeypatch.setattr(ck, "do_dong_bo", _gia(0.1, 3.7))  # 256KB/3.7s ≈ 69KB/s
    await ck.mot_vong(None, Path("/x"))
    assert _sach[-1][0].co_chuyen is None
    await ck.mot_vong(None, Path("/x"))
    k = _sach[-1][0]
    assert (k.ma, k.co_chuyen, k.muc) == (ck.MA, True, "warning")
    assert "đọc 69.2 KB/s" in k.noi_dung

    monkeypatch.setattr(ck, "do_dong_bo", _gia(0.1, 0.1))
    await ck.mot_vong(None, Path("/x"))
    assert _sach[-1][0].co_chuyen is None  # hồi 1 lần: giữ mở
    await ck.mot_vong(None, Path("/x"))
    assert _sach[-1][0].co_chuyen is False


def test_xen_ke_khong_mo() -> None:
    t = ck.TheoDoi()
    assert [t.cap_nhat(c) for c in (True, False, True, False)] == [None] * 4


def test_ghi_cham_noi_ro_ghi() -> None:
    pd = ck.PhepDo(luc="x", ghi_giay=4.0, doc_giay=0.1)
    assert pd.cham and "ghi 64 KB/s" in ck.noi_dung(pd)


async def test_loi_o_thanh_cham_critical(
    monkeypatch: pytest.MonkeyPatch, _sach: list[Any]
) -> None:
    def _hong(_goc: Path) -> tuple[float, float]:
        raise OSError("Host is down")

    monkeypatch.setattr(ck, "do_dong_bo", _hong)
    for _ in range(2):
        pd = await ck.mot_vong(None, Path("/x"))
    assert pd is not None and "Host is down" in pd.loi
    k = _sach[-1][0]
    assert (k.co_chuyen, k.muc) == (True, "critical")


async def test_treo_khong_chan_vong_su_kien_va_khong_de_them_luong(
    monkeypatch: pytest.MonkeyPatch, cua_treo: threading.Event, _sach: list[Any]
) -> None:
    so_lan_goi = 0

    def _treo(_goc: Path) -> tuple[float, float]:
        nonlocal so_lan_goi
        so_lan_goi += 1
        cua_treo.wait(30)
        return 0.0, 0.0

    monkeypatch.setattr(ck, "do_dong_bo", _treo)
    nhip = 0

    async def _dem() -> None:
        nonlocal nhip
        while True:
            nhip += 1
            await asyncio.sleep(0.01)

    dem = asyncio.create_task(_dem())
    t0 = time.monotonic()
    pd1 = await ck.mot_vong(None, Path("/x"), han=0.3)
    pd2 = await ck.mot_vong(None, Path("/x"), han=0.3)
    dem.cancel()
    assert time.monotonic() - t0 < 1.0  # lần 2 trả ngay, không chờ thêm hạn
    assert nhip >= 10  # vòng sự kiện vẫn quay trong lúc ổ treo
    assert pd1 is not None and "quá hạn" in pd1.loi
    assert pd2 is not None and "đang treo" in pd2.loi
    assert so_lan_goi == 1  # không đẻ luồng thứ hai
    assert _sach[-1][0].co_chuyen is True

    cua_treo.set()
    assert ck._luong is not None
    ck._luong.join(2)
    monkeypatch.setattr(ck, "do_dong_bo", _gia(0.1, 0.1))
    pd3 = await ck.mot_vong(None, Path("/x"))
    assert pd3 is not None and not pd3.cham  # ổ hồi thì đo lại được


async def test_db_hong_khong_nem(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _no(_pool: Any, _kq: Any) -> None:
        raise ConnectionError("db chết")

    monkeypatch.setattr(ck, "ap_dung", _no)
    monkeypatch.setattr(ck, "do_dong_bo", _gia(0.1, 0.1))
    assert await ck.mot_vong(None, Path("/x")) is None


def test_chi_bat_khi_co_media_root(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MEDIA_ROOT", raising=False)
    assert not ck.bat()
    monkeypatch.setenv("MEDIA_ROOT", "/var/lib/clinicai/media")
    assert ck.bat()
    monkeypatch.setenv("CANH_GAC_KHO_TEP", "0")
    assert not ck.bat()
