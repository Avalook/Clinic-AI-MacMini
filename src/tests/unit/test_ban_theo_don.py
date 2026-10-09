"""Quầy thuốc bán theo đơn cũ — luật thuần (không DB): ngày rác, 2 tháng lịch,
gom dòng kê / đã mua / còn lại, lời nhắc, dòng cần thêm."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest

from clinicai.services.ban_theo_don_service import (
    chuoi_so,
    cong_thang,
    doc_ngay,
    dong_can_them,
    gom_dong,
    loi_nhac,
    qua_han_kham,
)

D = Decimal


@pytest.mark.parametrize(
    "rac", [None, "", "abc", "2026-13-45", "31/12/2026", 123, 1.5, [], {}, True]
)
def test_ngay_rac_ra_rong_khong_nem(rac: object) -> None:
    assert doc_ngay(rac) is None
    assert qua_han_kham(rac, date(2026, 10, 9)) is False
    assert qua_han_kham(date(2026, 1, 1), rac) is False
    assert loi_nhac(rac, rac, []) == []


def test_doc_ngay_nhan_date_datetime_chuoi() -> None:
    assert doc_ngay("2026-08-09") == date(2026, 8, 9)
    assert doc_ngay(" 2026-08-09T10:00:00+07:00") == date(2026, 8, 9)
    assert doc_ngay(datetime(2026, 8, 9, 23, 0)) == date(2026, 8, 9)


def test_cong_thang_lich_kep_cuoi_thang() -> None:
    assert cong_thang(date(2026, 8, 9), 2) == date(2026, 10, 9)
    assert cong_thang(date(2026, 12, 31), 2) == date(2027, 2, 28)
    assert cong_thang(date(2027, 12, 31), 2) == date(2028, 2, 29)
    assert cong_thang(date(2026, 11, 15), 2) == date(2027, 1, 15)


def test_qua_2_thang_lich_moi_nhac() -> None:
    kham = date(2026, 8, 9)
    assert qua_han_kham(kham, date(2026, 10, 9)) is False  # đúng mốc: chưa quá
    assert qua_han_kham(kham, date(2026, 10, 10)) is True
    assert qua_han_kham("9999-12-31", "9999-12-31") is False  # tràn năm: không ném
    [cau] = loi_nhac(kham, date(2026, 10, 10), [])
    assert "09/08/2026" in cau and "quá 2 tháng" in cau


def _ke(i: str, thuoc: str | None, so: object, **kw: object) -> dict[str, object]:
    return {
        "id": i,
        "drug_catalog_id": thuoc,
        "so_ke": so,
        "ten_kho": kw.get("ten_kho"),
        "drug_name_raw": kw.get("ten_bs", "thuốc bs gõ"),
        "don_vi": "viên",
        "dosage_instructions": "Sáng 1",
        "caution": None,
    }


def test_gom_dong_da_mua_con_lai_vuot() -> None:
    dong = gom_dong(
        [
            _ke("1", "A", D(10), ten_kho="Thuốc A", ten_bs="thuoc a"),
            _ke("2", "A", D(4), ten_kho="Thuốc A"),  # cùng thuốc → gộp kê
            _ke("3", None, D(5), ten_bs="tên gõ tay"),
            _ke("4", "B", None, ten_kho="Thuốc B"),  # bác sĩ để trống số
        ],
        {"A": D(12), "B": D(3)},
        {"A": D(3)},
    )
    a, gt, b = dong
    assert (a["ten"], a["ten_bac_si"], a["so_ke"]) == ("Thuốc A", "thuoc a", D(14))
    assert (a["da_mua"], a["dang_ban"], a["con_lai"], a["vuot"]) == (
        D(12),
        D(3),
        D(2),
        True,
    )
    # Chưa xác định thuốc kho: không khớp lần mua nào.
    assert (gt["ten"], gt["da_mua"], gt["con_lai"], gt["vuot"]) == (
        "tên gõ tay",
        D(0),
        D(5),
        False,
    )
    # Không số kê → không còn lại, không nhắc vượt.
    assert (b["con_lai"], b["vuot"]) == (None, False)
    nhac = loi_nhac(date(2026, 10, 1), date(2026, 10, 9), dong)
    assert nhac == ["“Thuốc A”: tổng mua 15 viên vượt số bác sĩ kê 14 viên."]


def test_con_lai_khong_am() -> None:
    [a] = gom_dong([_ke("1", "A", D(5), ten_kho="A")], {"A": D(8)}, {})
    assert a["con_lai"] == D(0) and a["vuot"] is True


def test_dong_can_them_dien_so_con_lai() -> None:
    dong = gom_dong(
        [
            _ke("1", "A", D(10), ten_kho="A"),
            _ke("2", "B", D(5), ten_kho="B"),
            _ke("3", "C", D(2), ten_kho="C"),
            _ke("4", None, D(1), ten_bs="X"),
            _ke("5", "E", None, ten_kho="E"),
        ],
        {"A": D(4), "C": D(2)},
        {},
    )
    them, bo_qua = dong_can_them(dong, co_san={"B"})
    assert them == [
        {
            "drug_catalog_id": "A",
            "quantity": "6 viên",
            "dosage": "Sáng 1",
            "caution": None,
        }
    ]
    assert bo_qua == [
        "“C”: đã mua đủ số bác sĩ kê.",
        "“X”: chưa xác định thuốc kho — thêm tay.",
        "“E”: bác sĩ chưa ghi số lượng — thêm tay.",
    ]


def test_chuoi_so() -> None:
    assert [chuoi_so(x) for x in (D("10.000"), D("0.000"), D("2.5"), None)] == [
        "10",
        "0",
        "2.5",
        None,
    ]
