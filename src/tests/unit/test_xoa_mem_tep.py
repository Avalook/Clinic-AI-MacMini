"""V9 (30/09/2026) — luật xoá / khôi phục tệp kết quả (hàm thuần) + job dọn ổ."""

from __future__ import annotations

import os
import pathlib
import time
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from clinicai.api.exceptions import ValidationError
from clinicai.services.don_tep_ket_qua import don_tep_tam, duong_an_toan, kho_san_sang
from clinicai.services.tep_ket_qua_service import (
    LOAI_DINH_CHINH,
    LOAI_XOA,
    QuyenXoaTep,
    chuan_ly_do_xoa,
    gan_co_xoa,
    han_khoi_phuc,
    khoi_phuc_duoc,
    xoa_duoc,
)

TOI = "s-toi"
KHAC = "s-khac"
BAY_GIO = datetime(2026, 9, 30, 10, 0, tzinfo=UTC)


def _q(xoa: bool = False, duyet: bool = False, doc: bool = True) -> QuyenXoaTep:
    return QuyenXoaTep(TOI, doc, xoa, duyet)


def _tep(**kw: Any) -> dict[str, Any]:
    t: dict[str, Any] = {
        "x_tai_len_boi": KHAC,
        "x_da_xem_luc": None,
        "x_da_xem_boi": None,
        "x_cho_phep_luc": None,
        "x_cho_phep_boi": None,
        "x_gui_luc": None,
        "x_phien_doc_dong": False,
        "da_xoa_luc": None,
        "da_xoa_loai": None,
        "x_da_xoa_boi": None,
        "da_don_tep_luc": None,
    }
    t.update(kw)
    return t


def test_co_lego_ket_qua_xoa_duoc_moi_luc() -> None:
    kq = xoa_duoc(_tep(x_da_xem_luc=BAY_GIO, x_da_xem_boi=KHAC), _q(xoa=True))
    assert kq.duoc and kq.loai == LOAI_XOA


def test_nguoi_tai_len_xoa_khi_chua_ai_khac_xem() -> None:
    assert xoa_duoc(_tep(x_tai_len_boi=TOI), _q()).duoc
    # Chính mình xem / tự cho phép gửi (bác sĩ tải lên) không tính.
    assert xoa_duoc(
        _tep(
            x_tai_len_boi=TOI,
            x_da_xem_luc=BAY_GIO,
            x_da_xem_boi=TOI,
            x_cho_phep_luc=BAY_GIO,
            x_cho_phep_boi=TOI,
        ),
        _q(),
    ).duoc
    kq = xoa_duoc(
        _tep(x_tai_len_boi=TOI, x_da_xem_luc=BAY_GIO, x_da_xem_boi=KHAC), _q()
    )
    assert not kq.duoc and kq.ly_do and "đã xem" in kq.ly_do
    kq = xoa_duoc(
        _tep(x_tai_len_boi=TOI, x_cho_phep_luc=BAY_GIO, x_cho_phep_boi=KHAC), _q()
    )
    assert not kq.duoc


def test_khong_tai_len_khong_quyen_thi_khong() -> None:
    kq = xoa_duoc(_tep(), _q())
    assert not kq.duoc and kq.ly_do
    # Không đọc được tệp mà cũng không phải người tải → không.
    assert not xoa_duoc(_tep(), _q(xoa=True, doc=False)).duoc


def test_da_gui_hoac_phien_dong_chi_con_dinh_chinh() -> None:
    da_gui = _tep(x_gui_luc=BAY_GIO)
    assert not xoa_duoc(da_gui, _q(xoa=True)).duoc
    kq = xoa_duoc(da_gui, _q(duyet=True))
    assert kq.duoc and kq.loai == LOAI_DINH_CHINH and "gửi khách" in (kq.ly_do or "")
    kq = xoa_duoc(_tep(x_phien_doc_dong=True), _q(duyet=True))
    assert kq.loai == LOAI_DINH_CHINH and "Phiên đọc" in (kq.ly_do or "")


def test_da_xoa_thi_khong_xoa_nua() -> None:
    assert not xoa_duoc(_tep(da_xoa_luc=BAY_GIO), _q(xoa=True, duyet=True)).duoc


def test_khoi_phuc_trong_30_ngay() -> None:
    tep = _tep(da_xoa_luc=BAY_GIO - timedelta(days=3), da_xoa_loai=LOAI_XOA)
    assert khoi_phuc_duoc(tep, _q(xoa=True), BAY_GIO).duoc
    # Người đã xoá khôi phục được dù không có quyền xoá.
    assert khoi_phuc_duoc({**tep, "x_da_xoa_boi": TOI}, _q(), BAY_GIO).duoc
    assert not khoi_phuc_duoc(tep, _q(), BAY_GIO).duoc
    qua = {**tep, "da_xoa_luc": BAY_GIO - timedelta(days=31)}
    assert not khoi_phuc_duoc(qua, _q(xoa=True), BAY_GIO).duoc
    don = {**tep, "da_don_tep_luc": BAY_GIO}
    kq = khoi_phuc_duoc(don, _q(xoa=True), BAY_GIO)
    assert not kq.duoc and "dọn" in (kq.ly_do or "")


def test_khoi_phuc_dinh_chinh_can_quyen_duyet() -> None:
    tep = _tep(da_xoa_luc=BAY_GIO, da_xoa_loai=LOAI_DINH_CHINH, x_da_xoa_boi=TOI)
    assert not khoi_phuc_duoc(tep, _q(xoa=True), BAY_GIO).duoc
    assert khoi_phuc_duoc(tep, _q(duyet=True), BAY_GIO).duoc


def test_han_khoi_phuc_rac_tra_rong() -> None:
    assert han_khoi_phuc(None) is None
    assert han_khoi_phuc("2026-09-30") is None
    assert han_khoi_phuc(12345) is None
    # Không múi giờ → coi như UTC, không ném.
    assert han_khoi_phuc(datetime(2026, 9, 1)) == datetime(2026, 10, 1, tzinfo=UTC)
    # Mốc xoá rác → không khôi phục (không ném).
    assert not khoi_phuc_duoc(
        _tep(da_xoa_luc="rác", da_xoa_loai=LOAI_XOA), _q(xoa=True), BAY_GIO
    ).duoc


def test_ly_do_bat_buoc() -> None:
    for rac in (None, "", "   ", "\n\t"):
        with pytest.raises(ValidationError):
            chuan_ly_do_xoa(rac)
    with pytest.raises(ValidationError):
        chuan_ly_do_xoa("x" * 501)
    assert chuan_ly_do_xoa("  Ảnh   mờ \n") == "Ảnh mờ"


def test_gan_co_xoa_bo_cot_noi_bo() -> None:
    d = gan_co_xoa({"id": "t1", **_tep(x_tai_len_boi=TOI)}, _q())
    assert d["xoa_duoc"] is True and d["xoa_loai"] == LOAI_XOA
    assert not any(k.startswith("x_") for k in d) and "da_don_tep_luc" not in d
    d = gan_co_xoa(
        {"id": "t1", **_tep(da_xoa_luc=datetime.now(UTC), da_xoa_loai=LOAI_XOA)},
        _q(xoa=True),
    )
    assert d["khoi_phuc_duoc"] is True and d["khoi_phuc_han"]


# ── job dọn ổ ──────────────────────────────────────────────────────────────


def test_kho_chua_gan_thi_khong_don(tmp_path: pathlib.Path) -> None:
    assert kho_san_sang(tmp_path, {}) == (False, "chua_dat_MEDIA_ROOT")
    assert not kho_san_sang(tmp_path / "khong-co", {"MEDIA_ROOT": "x"})[0]
    env = {"MEDIA_ROOT": str(tmp_path), "MEDIA_MARKER": ".da-gan"}
    assert kho_san_sang(tmp_path, env) == (False, "thieu_MEDIA_MARKER")
    (tmp_path / ".da-gan").write_text("1")
    assert kho_san_sang(tmp_path, env) == (True, "")


def test_duong_an_toan(tmp_path: pathlib.Path) -> None:
    c = "a0000000-0000-4000-8000-000000000001"
    assert duong_an_toan(tmp_path, c, f"{c}/p/x.pdf") is not None
    assert duong_an_toan(tmp_path, c, "khac/p/x.pdf") is None
    assert duong_an_toan(tmp_path, c, f"{c}/../../etc/passwd") is None
    assert duong_an_toan(tmp_path, c, "") is None


def test_don_tep_tam_chi_part_cu(tmp_path: pathlib.Path) -> None:
    assert don_tep_tam(tmp_path) == 0  # chưa có .tam
    tam = tmp_path / ".tam"
    tam.mkdir()
    cu = tam / "a.part"
    moi = tam / "b.part"
    khac = tam / "c.txt"
    for p in (cu, moi, khac):
        p.write_bytes(b"x")
    ts = time.time() - 3 * 86400
    os.utime(cu, (ts, ts))
    os.utime(khac, (ts, ts))
    assert don_tep_tam(tmp_path) == 1
    assert not cu.exists() and moi.exists() and khac.exists()
