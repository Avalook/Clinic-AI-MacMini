"""V7 — đổi hình thức thu: hàm thuần (không cần DB)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

import pytest

from clinicai.api.exceptions import ValidationError
from clinicai.services.bao_cao_cuoi_ngay_service import csv_bao_cao, gom_bao_cao
from clinicai.services.doi_hinh_thuc_service import (
    KHONG_DOI_CHUA_THU,
    KHONG_DOI_CO_HOAN,
    KHONG_DOI_DA_HUY,
    doc_ly_do,
    doc_ma_gd,
    dung_trang_thai,
    gan_vao_lich_su,
    ly_do_khong_doi,
)


@pytest.mark.parametrize(
    ("status", "co_hoan", "mong"),
    [
        ("PAID", False, None),
        ("PAID", True, KHONG_DOI_CO_HOAN),
        ("VOIDED", False, KHONG_DOI_DA_HUY),
        ("VOIDED", True, KHONG_DOI_DA_HUY),
        ("PENDING_VERIFICATION", False, KHONG_DOI_CHUA_THU),
        ("CANCELLED", False, KHONG_DOI_CHUA_THU),
        (None, None, KHONG_DOI_CHUA_THU),
    ],
)
def test_ly_do_khong_doi(status: object, co_hoan: object, mong: str | None) -> None:
    assert ly_do_khong_doi(status, co_hoan) == mong


def test_ma_gd_va_ly_do_tuy_chon() -> None:
    assert doc_ma_gd(None) is None
    assert doc_ma_gd("   ") is None
    assert doc_ma_gd(123) is None
    assert doc_ma_gd("  FT1  ") == "FT1"
    with pytest.raises(ValidationError):
        doc_ma_gd("x" * 101)
    assert doc_ly_do("") is None
    assert doc_ly_do(" nhầm ") == "nhầm"
    with pytest.raises(ValidationError):
        doc_ly_do("x" * 501)


def test_dung_trang_thai_va_gan_vao_lich_su() -> None:
    luc = datetime(2026, 9, 30, 3, 0, tzinfo=timezone.utc)
    tt = dung_trang_thai(
        [
            {"id": "a", "status": "PAID", "method": "CASH", "co_hoan": False},
            {"id": "b", "status": "VOIDED", "method": "QR", "co_hoan": False},
        ],
        [
            {
                "cycle_id": "a",
                "method_cu": "CASH",
                "method_moi": "TRANSFER",
                "reference": "FT1",
                "ly_do": None,
                "boi": "Hà",
                "luc": luc,
            },
            {
                "cycle_id": "a",
                "method_cu": "TRANSFER",
                "method_moi": "QR",
                "reference": None,
                "ly_do": "nhầm",
                "boi": "Lan",
                "luc": "rác",
            },
        ],
    )
    assert tt["a"]["duoc"] is True and tt["a"]["hinh_thuc_goc"] == "CASH"
    assert [(d["tu"], d["sang"], d["luc"]) for d in tt["a"]["lan_doi"]] == [
        ("CASH", "TRANSFER", luc.isoformat()),
        ("TRANSFER", "QR", None),
    ]
    assert tt["b"] == {
        "duoc": False,
        "ly_do_khong": KHONG_DOI_DA_HUY,
        "hinh_thuc_goc": "QR",
        "lan_doi": [],
    }
    khach: list[dict[str, Any]] = [
        {
            "phieu": [{"id": "a"}],
            "su_kien": [{"loai": "thu", "id": "a"}, {"loai": "hoan", "id": "r"}],
        }
    ]
    gan_vao_lich_su(khach, tt)
    assert khach[0]["phieu"][0]["doi_hinh_thuc"] is tt["a"]
    assert khach[0]["su_kien"][0]["doi_hinh_thuc"] is tt["a"]
    assert "doi_hinh_thuc" not in khach[0]["su_kien"][1]


def test_bao_cao_co_muc_doi_hinh_thuc_khong_tinh_la_huy() -> None:
    luc = datetime(2026, 9, 30, 3, 0, tzinfo=timezone.utc)
    bc = gom_bao_cao(
        tu=date(2026, 9, 30),
        den=date(2026, 9, 30),
        # `method` đã là hình thức HIỆU LỰC (SQL đọc qua hinh_thuc_hieu_luc).
        lan_thu=[
            {
                "id": "a",
                "visit_id": "v",
                "kind": "dich_vu",
                "status": "PAID",
                "amount": 150_000,
                "method": "TRANSFER",
                "paid_at": luc,
                "nguoi_thu": "Hà",
            }
        ],
        hoan=[],
        dong=[],
        doi_tac=[],
        so_luot_kham=1,
        doi_hinh_thuc=[
            {
                "id": "1",
                "cycle_id": "a",
                "method_cu": "CASH",
                "method_moi": "TRANSFER",
                "ly_do": "=nhầm",
                "luc": luc,
                "kind": "dich_vu",
                "amount": 150_000,
                "nguoi": "Lan",
                "ten_khach": "Chị A",
                "ma_bn": "BN1",
            }
        ],
    )
    assert bc["tong"]["huy"] == 0 and bc["tong"]["thuc_thu"] == 150_000
    ht = {o["ma"]: o["thu"] for o in bc["theo_hinh_thuc"]}
    assert (ht["CASH"], ht["TRANSFER"]) == (0, 150_000)
    assert bc["doi_hinh_thuc"] == [
        {
            "id": "1",
            "cycle_id": "a",
            "luc": luc.isoformat(),
            "khach": "Chị A",
            "ma_bn": "BN1",
            "loai_tien": "dich_vu",
            "tu": "CASH",
            "sang": "TRANSFER",
            "tien_mat": None,
            "chuyen_khoan": None,
            "nhan_sang": "Chuyển khoản",
            "so_tien": 150_000,
            "nguoi": "Lan",
            "ly_do": "=nhầm",
        }
    ]
    csv = csv_bao_cao(bc)
    assert "Đổi hình thức (không phải huỷ)" in csv
    # Ô bắt đầu bằng "=" không thành công thức Excel.
    assert "'=nhầm" in csv


def test_bao_cao_khong_truyen_doi_hinh_thuc_van_chay() -> None:
    bc = gom_bao_cao(
        tu=date(2026, 9, 30),
        den=date(2026, 9, 30),
        lan_thu=[],
        hoan=[],
        dong=[],
        doi_tac=[],
        so_luot_kham=0,
    )
    assert bc["doi_hinh_thuc"] == []
    assert "Đổi hình thức" in csv_bao_cao(bc)
