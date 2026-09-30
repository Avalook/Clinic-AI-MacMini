"""Đường TẢI LÊN / XOÁ tệp không làm treo API khi ổ Viettel treo (29/09/2026).

PR #266 bọc đường ĐỌC. Ở đây: mkdir, mở/ghi từng khối, đổi tên, xoá tệp dở.
Ổ treo thì lượt tải báo "Kho lưu tệp đang chậm" trong vài giây, vòng sự kiện
vẫn chạy (việc khác của phòng khám không đứng theo), và dọn dẹp KHÔNG che lỗi
gốc.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import shutil
import threading
import time
from collections.abc import Awaitable, Iterator
from pathlib import Path
from typing import Any, TypeVar

import pytest

from clinicai.api.exceptions import ValidationError
from clinicai.core import kho_tep
from clinicai.core.exceptions import ExternalServiceError
from tests.services.fake_pool import FakePool
from tests.unit.test_tep_ket_qua import BN, _ai, _request, _than_multipart

T = TypeVar("T")

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
REC = "b0000000-0000-4000-8000-000000000002"
HAN = 0.2


@pytest.fixture(autouse=True)
def _mo_lai(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    kho_tep.mo_lai()
    monkeypatch.setattr(kho_tep, "HAN_GIAY", HAN)
    yield
    kho_tep.mo_lai()


@pytest.fixture
def nha() -> Iterator[threading.Event]:
    """Nhả mọi luồng đang "treo trên ổ" khi test xong — không để luồng rò."""
    ev = threading.Event()
    yield ev
    ev.set()


@pytest.fixture
def kho(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    from clinicai.services import media_service, nhan_tep_luong

    # 01/10/2026: tải lên ghi vào ổ VPS (MEDIA_LOCAL_ROOT), không vào CFS.
    monkeypatch.setattr(media_service, "MEDIA_LOCAL_ROOT", tmp_path)
    monkeypatch.setattr(nhan_tep_luong, "HAN_GHI_KHOI", HAN)
    monkeypatch.delenv("MEDIA_MARKER", raising=False)
    return tmp_path


async def _do_va_dem(viec: Awaitable[T]) -> tuple[float, int, BaseException | None]:
    """Chạy ``viec`` cùng một bộ đếm nhịp vòng sự kiện: (giây, số nhịp, lỗi)."""
    nhip = 0

    async def dem() -> None:
        nonlocal nhip
        while True:
            nhip += 1
            await asyncio.sleep(0.01)

    task = asyncio.create_task(dem())
    t0 = time.monotonic()
    loi: BaseException | None = None
    try:
        await viec
    except BaseException as e:  # noqa: BLE001 — trả về cho test soi
        loi = e
    task.cancel()
    return time.monotonic() - t0, nhip, loi


# ── nhận multipart theo luồng ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_mo_tep_treo_thi_bao_kho_cham_ma_vong_van_chay(
    kho: Path, monkeypatch: pytest.MonkeyPatch, nha: threading.Event
) -> None:
    """mkdir/open trên ổ treo → lỗi "kho chậm" trong < 1s, vòng sự kiện vẫn nhịp."""
    from clinicai.services import nhan_tep_luong
    from clinicai.services.nhan_tep_luong import nhan_multipart

    monkeypatch.setattr(nhan_tep_luong, "_mo_ghi", lambda _d: nha.wait(5))
    giay, nhip, loi = await _do_va_dem(
        nhan_multipart(_request(_than_multipart({}, ("a.png", PNG))))
    )
    assert isinstance(loi, ExternalServiceError)
    assert "Ổ lưu tạm" in str(loi) and "chậm" in str(loi)
    assert giay < 1.0
    assert nhip > 5
    # Ổ VPS treo chỉ ngắt mạch ổ VPS — đường đọc tệp đã đẩy sang CFS vẫn mở.
    assert kho_tep.dang_ngat("vps") and not kho_tep.dang_ngat("cfs")
    # Đang ngắt mạch: lượt sau trả lỗi NGAY, không đẻ thêm luồng chờ ổ.
    goi: list[int] = []
    monkeypatch.setattr(nhan_tep_luong, "_mo_ghi", lambda _d: goi.append(1))
    with pytest.raises(ExternalServiceError):
        await nhan_multipart(_request(_than_multipart({}, ("a.png", PNG))))
    assert goi == []


class _TepGhiTreo:
    """Tệp mở được nhưng mỗi lần ghi đứng chờ ổ."""

    def __init__(self, nha: threading.Event) -> None:
        self._nha = nha
        self.da_dong = False

    def write(self, _b: bytes) -> int:
        self._nha.wait(5)
        return 0

    def close(self) -> None:
        self.da_dong = True


@pytest.mark.asyncio
async def test_ghi_khoi_treo_thi_bao_kho_cham_va_khong_don_khi_dang_ngat(
    kho: Path, monkeypatch: pytest.MonkeyPatch, nha: threading.Event
) -> None:
    """Ghi một khối treo → "kho chậm"; đang ngắt mạch nên KHÔNG chạm ổ để dọn
    (đóng/xoá tệp dở cũng sẽ treo) — chỉ ghi log."""
    from clinicai.services import nhan_tep_luong
    from clinicai.services.nhan_tep_luong import nhan_multipart

    tep = _TepGhiTreo(nha)
    xoa: list[Path] = []
    monkeypatch.setattr(nhan_tep_luong, "_mo_ghi", lambda _d: tep)
    monkeypatch.setattr(nhan_tep_luong, "_xoa", xoa.append)
    data = PNG + b"x" * (5 * 1024 * 1024)
    giay, nhip, loi = await _do_va_dem(
        nhan_multipart(_request(_than_multipart({}, ("a.png", data)), khuc=65536))
    )
    assert isinstance(loi, ExternalServiceError)
    assert giay < 1.0 and nhip > 5
    assert xoa == [] and not tep.da_dong


@pytest.mark.asyncio
async def test_don_tep_do_loi_khong_che_loi_goc(
    kho: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Tệp rác bị từ chối; xoá tệp dở hỏng (OSError) vẫn trả đúng lỗi 422 gốc."""
    from clinicai.services import nhan_tep_luong
    from clinicai.services.nhan_tep_luong import nhan_multipart

    def _xoa_hong(_d: Path) -> None:
        raise OSError("ổ trả lỗi I/O")

    monkeypatch.setattr(nhan_tep_luong, "_xoa", _xoa_hong)
    with pytest.raises(ValidationError, match="một tệp"):
        than = _than_multipart({}, ("a.png", PNG)).replace(
            b"--ranhgioiXYZ--\r\n", b""
        ) + _than_multipart({}, ("b.png", PNG))
        await nhan_multipart(_request(than))


@pytest.mark.asyncio
async def test_don_tep_tam_khong_nem_khi_o_treo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, nha: threading.Event
) -> None:
    """Router gọi `don_tep_tam` trong `finally`: ổ treo thì nuốt + log, không ném
    đè lên kết quả/lỗi của lượt tải."""
    from clinicai.services import nhan_tep_luong
    from clinicai.services.nhan_tep_luong import TepDaNhan, don_tep_tam

    monkeypatch.setattr(nhan_tep_luong, "_xoa", lambda _d: nha.wait(5))
    tep = TepDaNhan(duong=tmp_path / "x.part", so_byte=1, sha256="", dau=b"", ten=None)
    giay, _nhip, loi = await _do_va_dem(don_tep_tam(tep))
    assert loi is None and giay < 1.0
    assert kho_tep.dang_ngat("vps")


# ── service tệp kết quả ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_tai_len_doi_ten_treo_thi_bao_kho_cham(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, nha: threading.Event
) -> None:
    """Đổi tên `.part` → chỗ ở thật treo → "kho chậm", không ghi dòng database."""
    from clinicai.services import tep_ket_qua_service as mod
    from clinicai.services.nhan_tep_luong import TepDaNhan

    monkeypatch.setattr(mod, "MEDIA_ROOT", tmp_path)
    monkeypatch.setattr("clinicai.services.media_service.MEDIA_ROOT", tmp_path)
    monkeypatch.setattr("clinicai.services.media_service.MEDIA_LOCAL_ROOT", tmp_path)
    monkeypatch.delenv("MEDIA_MARKER", raising=False)
    monkeypatch.setattr(os, "replace", lambda *_a: nha.wait(5))
    part = tmp_path / ".tam" / "x.part"
    part.parent.mkdir()
    part.write_bytes(PNG)
    tep = TepDaNhan(
        duong=part,
        so_byte=len(PNG),
        sha256=hashlib.sha256(PNG).hexdigest(),
        dau=PNG,
        ten="a.png",
    )
    pool = FakePool(1, False, "tep-1")
    giay, nhip, loi = await _do_va_dem(
        mod.TepKetQuaService(pool).tai_len(
            identity=_ai(), clinic_patient_id=BN, tep_da_nhan=tep
        )
    )
    assert isinstance(loi, ExternalServiceError)
    assert giay < 1.0 and nhip > 5
    assert not pool.wrote("INSERT INTO public.tep_ket_qua")


@pytest.mark.asyncio
async def test_tai_len_mkdir_treo_thi_bao_kho_cham(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, nha: threading.Event
) -> None:
    from clinicai.services import tep_ket_qua_service as mod

    monkeypatch.setattr(mod, "MEDIA_ROOT", tmp_path)
    monkeypatch.setattr("clinicai.services.media_service.MEDIA_ROOT", tmp_path)
    monkeypatch.setattr("clinicai.services.media_service.MEDIA_LOCAL_ROOT", tmp_path)
    monkeypatch.delenv("MEDIA_MARKER", raising=False)
    monkeypatch.setattr(shutil, "disk_usage", lambda _p: nha.wait(5))
    giay, _nhip, loi = await _do_va_dem(
        mod.TepKetQuaService(FakePool(1)).tai_len(
            identity=_ai(), clinic_patient_id=BN, data=PNG
        )
    )
    assert isinstance(loi, ExternalServiceError)
    assert giay < 1.0
    assert not any(p.is_file() for p in tmp_path.rglob("*"))


# ── ảnh siêu âm ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_anh_sieu_am_ghi_treo_thi_bao_kho_cham(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, nha: threading.Event
) -> None:
    from clinicai.services.media_service import MediaService

    monkeypatch.setattr("clinicai.services.media_service.MEDIA_ROOT", tmp_path)
    monkeypatch.delenv("MEDIA_MARKER", raising=False)

    def ghi_treo(_self: Path, _data: Any) -> int:
        nha.wait(5)
        return 0

    monkeypatch.setattr(Path, "write_bytes", ghi_treo)
    pool = FakePool({"ultrasound_id": REC, "signed_at": None})
    identity = _ai()
    giay, nhip, loi = await _do_va_dem(
        MediaService(pool).attach_ultrasound_image(
            identity=identity, ultrasound_id=REC, data=JPEG, display_name=None
        )
    )
    assert isinstance(loi, ExternalServiceError)
    assert giay < 1.5 and nhip > 5
    assert not pool.wrote("UPDATE public.ultrasound_record")
