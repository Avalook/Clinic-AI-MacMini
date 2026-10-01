"""Tải lên lưu ổ VPS trước, đẩy sang Viettel CFS sau (Tuyền chốt 30/09/2026).

Lớp không cần database: chép + kiểm sha256, lùi dần, đọc ưu tiên ổ VPS, lỗi
nhanh khi CFS đang ngắt mạch, đọc từng mảnh có hạn giờ, vòng lặp không đẩy khi
CFS chậm, cảnh báo ổ VPS gần đầy.
"""

from __future__ import annotations

import hashlib
import threading
import time
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from clinicai.api.exceptions import NotFoundError
from clinicai.core import kho_tep
from clinicai.core.exceptions import ExternalServiceError
from clinicai.services import canh_gac_kho_tep, day_tep, media_service
from clinicai.services import tep_ket_qua_service as tep_mod

DATA = b"%PDF-1.4\n" + b"x" * 5000
SHA = hashlib.sha256(DATA).hexdigest()
KHOA = "a0000000-0000-4000-8000-000000000001/ket-qua/bn/abc.pdf"


@pytest.fixture(autouse=True)
def _mo_lai() -> Iterator[None]:
    kho_tep.mo_lai()
    yield
    kho_tep.mo_lai()


@pytest.fixture
def hai_o(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    vps, cfs = tmp_path / "vps", tmp_path / "cfs"
    vps.mkdir()
    cfs.mkdir()
    monkeypatch.setattr(media_service, "MEDIA_LOCAL_ROOT", vps)
    monkeypatch.setattr(media_service, "MEDIA_ROOT", cfs)
    monkeypatch.setattr(tep_mod, "MEDIA_ROOT", cfs)
    monkeypatch.delenv("MEDIA_MARKER", raising=False)
    return vps, cfs


def _dat(goc: Path, khoa: str = KHOA, data: bytes = DATA) -> Path:
    p = goc / khoa
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    return p


# ── lùi dần / hạn ──────────────────────────────────────────────────────────


def test_lui_dan_gap_doi_toi_tran() -> None:
    assert [day_tep.lui_giay(n) for n in (0, 1, 2, 3, 5)] == [60, 60, 120, 240, 960]
    assert day_tep.lui_giay(50) == day_tep.LUI_TOI_DA_GIAY


def test_han_day_theo_co_tep() -> None:
    assert day_tep.han_day(0) == kho_tep.HAN_GIAY
    assert day_tep.han_day(10 * 1024 * 1024) == kho_tep.HAN_GIAY + 20


# ── chép + kiểm ────────────────────────────────────────────────────────────


def test_chep_va_kiem_khop_thi_dat_dung_khoa(hai_o: tuple[Path, Path]) -> None:
    vps, cfs = hai_o
    nguon = _dat(vps)
    dich = day_tep.chep_va_kiem(nguon, cfs, KHOA, len(DATA), SHA)
    assert dich == (cfs / KHOA).resolve()
    assert dich.read_bytes() == DATA
    assert nguon.exists()  # bản VPS giữ lại — việc dọn là bước riêng
    assert list((cfs / ".tam").iterdir()) == []


def test_ban_vps_lech_sha_thi_khong_dat_va_khong_de_rac(
    hai_o: tuple[Path, Path],
) -> None:
    vps, cfs = hai_o
    nguon = _dat(vps, data=DATA[:-1] + b"y")
    with pytest.raises(day_tep.DayTepError, match="ổ VPS lệch"):
        day_tep.chep_va_kiem(nguon, cfs, KHOA, len(DATA), SHA)
    assert not (cfs / KHOA).exists()
    assert list((cfs / ".tam").iterdir()) == []


def test_doc_lai_tren_cfs_lech_thi_khong_dat(
    hai_o: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ghi xong, ĐỌC LẠI từ CFS lệch sha (ổ ghi hỏng giữa đường) → không đổi tên
    về khoá, không để lại tệp tạm."""
    vps, cfs = hai_o
    nguon = _dat(vps)
    monkeypatch.setattr(day_tep, "_sha_doc_lai", lambda _p: (len(DATA), "0" * 64))
    with pytest.raises(day_tep.DayTepError, match="đọc lại trên CFS"):
        day_tep.chep_va_kiem(nguon, cfs, KHOA, len(DATA), SHA)
    assert not (cfs / KHOA).exists()
    assert list((cfs / ".tam").iterdir()) == []


def test_kho_cfs_chua_gan_thi_khong_day(
    hai_o: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ổ rớt → thư mục bind trỏ xuống ổ VPS bên dưới: đẩy vào đó là tự lừa."""
    vps, cfs = hai_o
    monkeypatch.setenv("MEDIA_MARKER", ".o-viettel-cfs")
    with pytest.raises(day_tep.DayTepError, match="chưa gắn"):
        day_tep.chep_va_kiem(_dat(vps), cfs, KHOA, len(DATA), SHA)
    assert not (cfs / KHOA).exists()


def test_mat_ban_vps_la_loi_cua_tep(hai_o: tuple[Path, Path]) -> None:
    vps, cfs = hai_o
    with pytest.raises(day_tep.DayTepError, match="không thấy bản"):
        day_tep.chep_va_kiem(vps / KHOA, cfs, KHOA, len(DATA), SHA)


# ── đọc: ổ VPS trước, CFS sau, lỗi nhanh khi CFS ngắt mạch ─────────────────


async def test_doc_uu_tien_ban_vps(hai_o: tuple[Path, Path]) -> None:
    vps, cfs = hai_o
    _dat(vps, data=b"BAN-VPS")
    _dat(cfs, data=b"BAN-CFS")
    p, kho, f = await tep_mod._tim_ban(KHOA, "cfs", mo=True)
    assert kho == "vps" and f is not None
    assert f.read() == b"BAN-VPS"
    f.close()


async def test_het_ban_vps_thi_doc_cfs(hai_o: tuple[Path, Path]) -> None:
    _vps, cfs = hai_o
    _dat(cfs, data=b"BAN-CFS")
    p, kho, _f = await tep_mod._tim_ban(KHOA, "cfs", mo=False)
    assert kho == "cfs" and p.read_bytes() == b"BAN-CFS"


async def test_cfs_dang_ngat_mach_thi_loi_nhanh_nhung_ban_vps_van_doc_duoc(
    hai_o: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    vps, cfs = hai_o
    _dat(cfs)
    kho_tep._ngat_den["cfs"] = time.monotonic() + 30
    goi: list[Path] = []

    def _mo(g: Path, k: str, _m: bool) -> tuple[Path, None, bool]:
        goi.append(g)
        return g / k, None, False

    monkeypatch.setattr(tep_mod, "_mo_trong", _mo)
    t0 = time.monotonic()
    with pytest.raises(ExternalServiceError, match="chậm"):
        await tep_mod._tim_ban(KHOA, "cfs", mo=False)
    assert time.monotonic() - t0 < 0.5
    assert goi == [vps]  # chỉ hỏi ổ VPS; KHÔNG đẻ luồng chờ CFS
    monkeypatch.undo()
    monkeypatch.setattr(media_service, "MEDIA_LOCAL_ROOT", vps)
    _dat(vps)
    _p, kho, _f = await tep_mod._tim_ban(KHOA, "cfs", mo=False)
    assert kho == "vps"


async def test_tep_chua_day_mat_ban_vps_khong_cham_cfs(
    hai_o: tuple[Path, Path],
) -> None:
    _vps, cfs = hai_o
    _dat(cfs)  # có trên CFS cũng không được đọc: dòng nói chưa đẩy
    kho_tep._ngat_den["cfs"] = time.monotonic() + 30
    with pytest.raises(NotFoundError):
        await tep_mod._tim_ban(KHOA, "vps", mo=False)


async def test_doc_dan_dung_khoang_va_dong_tep(hai_o: tuple[Path, Path]) -> None:
    vps, _cfs = hai_o
    p = _dat(vps)
    tep = tep_mod.TepMoDoc(
        f=p.open("rb"), kho="cfs", duong=p, mime="x", so_byte=len(DATA), ten=""
    )
    ra = b"".join([m async for m in tep_mod.doc_dan(tep, 100, 399_999)])
    assert ra == DATA[100:]
    assert tep.f.closed


async def test_doc_dan_manh_treo_thi_loi_theo_han_va_van_dong_tep(
    hai_o: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """29/09: bản cũ đọc CFS bằng generator đồng bộ không hạn — ổ treo là luồng
    treo tới cạn pool. Giờ MỖI MẢNH có hạn."""
    vps, _cfs = hai_o
    p = _dat(vps)
    nha = threading.Event()
    monkeypatch.setattr(kho_tep, "HAN_GIAY", 0.2)

    class _Treo:
        closed = False

        def seek(self, _n: int) -> int:
            return 0

        def read(self, _n: int) -> bytes:
            nha.wait(5)
            return b""

        def close(self) -> None:
            self.closed = True

    f = _Treo()
    tep = tep_mod.TepMoDoc(f=f, kho="cfs", duong=p, mime="x", so_byte=10, ten="")  # type: ignore[arg-type]
    t0 = time.monotonic()
    with pytest.raises(ExternalServiceError):
        async for _ in tep_mod.doc_dan(tep, 0, 9):
            pass
    nha.set()
    assert time.monotonic() - t0 < 1.0


# ── vòng lặp ───────────────────────────────────────────────────────────────


async def test_cfs_cham_thi_khong_day(
    hai_o: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    vps, cfs = hai_o

    async def _do_cham(*_a: Any, **_k: Any) -> canh_gac_kho_tep.PhepDo:
        return canh_gac_kho_tep.PhepDo(luc="x", doc_giay=9.0, ghi_giay=0.1)

    async def _khong_duoc_goi(*_a: Any, **_k: Any) -> dict[str, Any]:
        pytest.fail("CFS chậm mà vẫn đẩy")

    async def _don(*_a: Any, **_k: Any) -> dict[str, Any]:
        return {"dung": 0}

    async def _ap(*_a: Any, **_k: Any) -> None:
        return None

    monkeypatch.setattr(canh_gac_kho_tep, "do_kho", _do_cham)
    monkeypatch.setattr(day_tep, "day_mot_lo", _khong_duoc_goi)
    monkeypatch.setattr(day_tep, "don_ban_vps", _don)
    monkeypatch.setattr(day_tep, "ap_dung", _ap)
    tt = day_tep.TrangThai()
    for _ in range(3):
        ket = await day_tep.mot_vong(None, tt, goc_vps=vps, goc_cfs=cfs)
        assert ket["day"]["bo_qua"] == "cfs_chua_on"


async def test_on_mot_lan_chua_day_on_hai_lan_moi_day(
    hai_o: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    vps, cfs = hai_o
    goi: list[int] = []

    async def _do_on(*_a: Any, **_k: Any) -> canh_gac_kho_tep.PhepDo:
        return canh_gac_kho_tep.PhepDo(luc="x", doc_giay=0.1, ghi_giay=0.1)

    async def _day(*_a: Any, **_k: Any) -> dict[str, Any]:
        goi.append(1)
        return {"da_day": 0, "loi": 0, "bo_qua": None}

    async def _don(*_a: Any, **_k: Any) -> dict[str, Any]:
        return {"dung": 0}

    async def _ap(*_a: Any, **_k: Any) -> None:
        return None

    monkeypatch.setattr(canh_gac_kho_tep, "do_kho", _do_on)
    monkeypatch.setattr(day_tep, "day_mot_lo", _day)
    monkeypatch.setattr(day_tep, "don_ban_vps", _don)
    monkeypatch.setattr(day_tep, "ap_dung", _ap)
    tt = day_tep.TrangThai()
    await day_tep.mot_vong(None, tt, goc_vps=vps, goc_cfs=cfs)
    assert goi == []
    await day_tep.mot_vong(None, tt, goc_vps=vps, goc_cfs=cfs)
    # Một lô cho mỗi bảng tệp: tep_ket_qua + anh_chuyen_khoan (01/10).
    assert goi == [1] * len(day_tep.BANG_TEP)


async def test_vong_khong_bao_gio_nem(
    hai_o: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    vps, cfs = hai_o

    async def _hong(*_a: Any, **_k: Any) -> Any:
        raise RuntimeError("DB mất")

    monkeypatch.setattr(canh_gac_kho_tep, "do_kho", _hong)
    monkeypatch.setattr(day_tep, "don_ban_vps", _hong)
    monkeypatch.setattr(day_tep, "ap_dung", _hong)
    ket = await day_tep.mot_vong(None, day_tep.TrangThai(), goc_vps=vps, goc_cfs=cfs)
    assert ket["day"]["bo_qua"] == "cfs_chua_on"


def test_do_toc_do_dung_tep_rieng(tmp_path: Path) -> None:
    """API và day-tep đo CÙNG ổ: chung một tệp thì ghi đè nhau → "không khớp" giả."""
    canh_gac_kho_tep.do_dong_bo(tmp_path, day_tep.TEN_TEP_DO)
    assert (tmp_path / ".canh-gac" / day_tep.TEN_TEP_DO).is_file()
    assert not (tmp_path / ".canh-gac" / canh_gac_kho_tep.TEN_TEP_DO).exists()


# ── cảnh báo ───────────────────────────────────────────────────────────────


def test_canh_bao_o_vps() -> None:
    gb = 1024**3
    on = day_tep.danh_gia_o_vps(1 * gb, 20 * gb, tran=8 * gb)
    assert on.co_chuyen is False
    gan_tran = day_tep.danh_gia_o_vps(7 * gb, 20 * gb, tran=8 * gb)
    assert gan_tran.co_chuyen is True and gan_tran.muc == "warning"
    may_day = day_tep.danh_gia_o_vps(1 * gb, 4 * gb, tran=8 * gb)
    assert may_day.co_chuyen is True
    tu_choi = day_tep.danh_gia_o_vps(1 * gb, gb, tran=8 * gb)
    assert tu_choi.muc == "critical" and "TỪ CHỐI" in tu_choi.noi_dung


def test_suc_khoe_duong_day() -> None:
    now = datetime(2026, 10, 1, 12, tzinfo=UTC)
    on = {"cho_day": 2, "cu_nhat_luc": (now - timedelta(minutes=5)).isoformat()}
    assert day_tep.danh_gia_suc_khoe(on, now) == []
    lau = {"cho_day": 2, "cu_nhat_luc": (now - timedelta(hours=7)).isoformat()}
    assert day_tep.danh_gia_suc_khoe(lau, now)
    assert day_tep.danh_gia_suc_khoe({"loi_nang": 1}, now)
    assert day_tep.danh_gia_suc_khoe({"cu_nhat_luc": "rác"}, now) == []


def test_dung_luong_dem_ca_thu_muc_con(tmp_path: Path) -> None:
    _dat(tmp_path, "a/b/c.bin", b"x" * 10)
    _dat(tmp_path, ".tam/d.part", b"y" * 5)
    assert day_tep.dung_luong(tmp_path) == 15
    assert day_tep.dung_luong(tmp_path / "khong-co") == 0
