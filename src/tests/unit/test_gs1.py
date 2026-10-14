"""Hàm thuần tách GS1: dạng thô có GS, dạng ngoặc, tiền tố ký hiệu, rác → None."""

from __future__ import annotations

from datetime import date

import pytest

from clinicai.core.gs1 import GS, Gs1, chuan_ma, doc_han_gs1, tach_gs1

# GTIN-14 hợp lệ (số kiểm tra đúng): 0 + EAN-13 8934588012228.
GTIN = "08934588012228"


def test_tho_co_gs_doc_du_bon_truong() -> None:
    kq = tach_gs1(f"01{GTIN}17271231" + "10LOT-A1" + GS + "21SN99")
    assert kq == Gs1(gtin=GTIN, so_lo="LOT-A1", han=date(2027, 12, 31), serial="SN99")


def test_tien_to_ky_hieu_va_lo_cuoi_chuoi() -> None:
    kq = tach_gs1(f"]d201{GTIN}1726063010ABC123")
    assert kq is not None
    assert (kq.so_lo, kq.han) == ("ABC123", date(2026, 6, 30))


def test_dang_ngoac_nguoi_doc() -> None:
    kq = tach_gs1(f"(01){GTIN}(17)280115(10)L 77")
    assert kq is not None
    assert (kq.gtin, kq.han, kq.so_lo) == (GTIN, date(2028, 1, 15), "L 77")


def test_ngay_00_la_cuoi_thang() -> None:
    assert doc_han_gs1("270200") == date(2027, 2, 28)
    assert doc_han_gs1("280200") == date(2028, 2, 29)


@pytest.mark.parametrize("rac", ["000000", "271332", "270231", "27a231", "2712", ""])
def test_han_rac_la_none(rac: str) -> None:
    assert doc_han_gs1(rac) is None


def test_han_000000_khong_lam_hong_ca_ma() -> None:
    kq = tach_gs1(f"01{GTIN}17000000" + "10X1")
    assert kq is not None
    assert kq.han is None
    assert kq.so_lo == "X1"


@pytest.mark.parametrize(
    "rac",
    [
        None,
        123,
        "",
        "   ",
        "8934588012228",  # EAN-13 thường, không phải GS1
        f"10LOT{GS}17271231",  # thiếu AI 01
        "0108934588012229",  # sai số kiểm tra
        "01089345880",  # GTIN cụt
        "(10)ABC(17)271231",
        "]d2",
        "\x1d\x1d",
        "😀01" + GTIN,
    ],
)
def test_rac_tra_none(rac: object) -> None:
    assert tach_gs1(rac) is None


def test_ai_la_dung_lai_giu_phan_da_doc() -> None:
    kq = tach_gs1(f"01{GTIN}10LOT9{GS}99ZZZ")
    assert kq is not None
    assert kq.so_lo == "LOT9"


def test_chuan_ma_dem_khong_dau_cho_du_14() -> None:
    assert chuan_ma("8934588012228") == GTIN
    assert chuan_ma(GTIN) == GTIN
    assert chuan_ma("12345678") == "00000012345678"
    assert chuan_ma(" ABC-12 ") == "ABC-12"
    assert chuan_ma("1234567") == "1234567"  # quá ngắn: giữ nguyên
    assert chuan_ma("123456789012345") == "123456789012345"  # quá dài: giữ nguyên
    assert chuan_ma("") == ""
