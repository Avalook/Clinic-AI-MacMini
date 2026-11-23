"""Liên thông đơn thuốc quốc gia — phần THUẦN (không DB): công tắc, cấu hình, mã
đơn, dấu vân tay, trường thiếu. Hàng chờ: `test_don_thuoc_quoc_gia_hang_cho.py`.
Adapter thật QĐ 808: `test_don_thuoc_quoc_gia_that.py`."""

from __future__ import annotations

import json
from dataclasses import replace
from typing import Any

import pytest

from clinicai.ports.don_thuoc_quoc_gia import BacSiKe, DongThuoc, GoiDon, NguoiBenh
from clinicai.services.don_thuoc_quoc_gia.anh_xa import (
    dau_don,
    dau_van_tay_goi_don,
    goi_sang_json,
    goi_tu_json,
    thieu_truong,
)
from clinicai.services.don_thuoc_quoc_gia.cau_hinh import (
    CauHinh,
    da_bat,
    doc_cau_hinh_dtqg,
)
from clinicai.services.don_thuoc_quoc_gia.ma_don import MA_DON, sinh_ma_don

BS = "11111111-1111-4111-8111-111111111111"
ENV = {
    "DTQG_BAT": "1",
    "DTQG_CLINIC_ID": "a0000000-0000-4000-8000-000000000001",
    "DTQG_LOCATION_ID": "b0000000-0000-4000-8000-000000000002",
    "DTQG_MA_CO_SO": "79abc",
    "DTQG_GUI_TU": "2026-12-01",
}
MAT_KHAU = "mk-rat-bi-mat-123"
ENV_THAT = {
    **ENV,
    "APP_ENV": "production",
    "DTQG_NHA_CUNG_CAP": "that",
    "DTQG_MA_LIEN_THONG_CO_SO": "0179abc",
    "DTQG_BAC_SI": json.dumps(
        {BS: {"ma_lien_thong": "01000123HCM", "mat_khau": MAT_KHAU}}
    ),
}


def _goi(**doi: Any) -> GoiDon:
    g = GoiDon(
        ma_don="79abc1a2b3c4-c",
        visit_id="v1",
        ngay_ke="2026-12-02T17:30:05+07:00",
        bac_si=BacSiKe(BS, "BS A", "000123/HCM", "01000123HCM"),
        nguoi_benh=NguoiBenh(
            "BN1", "DEMO Khách", "1990-05-17", 1990, "NU", None, "DEMO", "0900000000"
        ),
        chan_doan="Viêm âm đạo",
        thuoc=[
            DongThuoc("Thuốc A", "SP000004", "Cefdinir", "2 viên", 2.0, "viên", "Uống")
        ],
    )
    return replace(g, **doi)


# ── công tắc + cấu hình ──────────────────────────────────────────────────────
@pytest.mark.parametrize("gt", ["", "0", "false", "tat", "off"])
def test_cong_tac_mac_dinh_tat(gt: str) -> None:
    assert da_bat({"DTQG_BAT": gt}) is False
    assert da_bat({}) is False


def test_cau_hinh_gia_lap_du() -> None:
    ch = doc_cau_hinh_dtqg(ENV)
    assert isinstance(ch, CauHinh)
    assert (ch.nha_cung_cap, ch.ma_co_so, ch.url) == (
        "gia_lap",
        "79abc",
        "https://api.donthuocquocgia.vn",
    )


@pytest.mark.parametrize(
    ("doi", "chu"),
    [
        ({"DTQG_MA_CO_SO": "79ab"}, "DTQG_MA_CO_SO"),
        ({"DTQG_GUI_TU": "hôm qua"}, "DTQG_GUI_TU"),
        ({"DTQG_GUI_TU": "2026-13-45"}, "DTQG_GUI_TU"),
        ({"DTQG_CLINIC_ID": "x"}, "DTQG_CLINIC_ID"),
        ({"DTQG_NHA_CUNG_CAP": "vnpt"}, "DTQG_NHA_CUNG_CAP"),
        ({"DTQG_KY_SO": "smartca"}, "DTQG_KY_SO"),
        ({"DTQG_SO_LAN_THU": "-1"}, "DTQG_SO_LAN_THU"),
        ({"DTQG_BAC_SI": "{rác"}, "DTQG_BAC_SI"),
    ],
)
def test_cau_hinh_sai_tra_loi_khong_nem(doi: dict[str, str], chu: str) -> None:
    loi = doc_cau_hinh_dtqg({**ENV, **doi})
    assert isinstance(loi, list) and any(chu in x for x in loi)


def test_cau_hinh_that_doi_tai_khoan_va_khong_lo_mat_khau() -> None:
    ch = doc_cau_hinh_dtqg(ENV_THAT)
    assert isinstance(ch, CauHinh) and ch.bac_si[BS].mat_khau == MAT_KHAU
    thieu_mk = json.dumps({BS: {"ma_lien_thong": "01000123HCM", "mat_khau": ""}})
    for doi in (
        # Staging (bản sao prod) không bao giờ được gửi lên hệ thống thật.
        {"APP_ENV": "staging"},
        {"APP_ENV": ""},
        {"DTQG_MA_LIEN_THONG_CO_SO": ""},
        {"DTQG_BAC_SI": thieu_mk},
        {"DTQG_URL": "http://api.donthuocquocgia.vn"},
    ):
        loi = doc_cau_hinh_dtqg({**ENV_THAT, **doi})
        assert isinstance(loi, list) and loi
        assert not any(MAT_KHAU in x for x in loi)


# ── mã đơn, trạng thái, thử lại ──────────────────────────────────────────────
def test_ma_don_14_ky_tu_dung_dang() -> None:
    ma = {sinh_ma_don("79abc") for _ in range(200)}
    assert len(ma) == 200
    for m in ma:
        assert len(m) == 14 and MA_DON.match(m) and m.startswith("79abc")
    with pytest.raises(ValueError):
        sinh_ma_don("79ab")


# ── ánh xạ ───────────────────────────────────────────────────────────────────
def test_dau_van_tay_bo_qua_ma_don_bat_noi_dung() -> None:
    g = _goi()
    assert dau_van_tay_goi_don(g) == dau_van_tay_goi_don(
        replace(g, ma_don="79abczzzzzzz-c")
    )
    assert dau_van_tay_goi_don(g) != dau_van_tay_goi_don(replace(g, chan_doan="Khác"))
    assert goi_tu_json(goi_sang_json(g)) == g


def test_dau_don_chi_phan_don() -> None:
    """Đổi SĐT / địa chỉ / CCCD / mã liên thông → dấu đơn giữ nguyên (đơn đã gửi
    không thành đơn thay thế); đổi thuốc / chẩn đoán / họ tên → đổi."""
    g = _goi()
    nb = g.nguoi_benh
    assert g.bac_si is not None
    for khac in (
        replace(g, nguoi_benh=replace(nb, dien_thoai="0911111111", dia_chi="Khác")),
        replace(g, nguoi_benh=replace(nb, so_dinh_danh="001190000000")),
        replace(g, bac_si=replace(g.bac_si, ma_lien_thong="01999")),
        replace(g, ma_don="79abczzzzzzz-c"),
    ):
        assert dau_don(khac) == dau_don(g)
    for khac in (
        replace(g, chan_doan="Khác"),
        replace(g, nguoi_benh=replace(nb, ho_ten="Tên khác")),
        replace(g, thuoc=[replace(g.thuoc[0], so_luong_so=3.0)]),
    ):
        assert dau_don(khac) != dau_don(g)


def test_thieu_truong_toi_thieu() -> None:
    assert thieu_truong(_goi()) == []
    g = _goi(
        bac_si=BacSiKe(BS, "BS A", None),
        chan_doan=" ",
        thuoc=[DongThuoc("", None, None, None, None, None, None)],
    )
    assert thieu_truong(g) == [
        "số chứng chỉ hành nghề của bác sĩ",
        "chẩn đoán",
        "tên thuốc dòng 1",
        "số lượng dòng 1",
        "cách dùng dòng 1",
    ]
    assert "bác sĩ đứng tên đơn" in thieu_truong(_goi(bac_si=None))
