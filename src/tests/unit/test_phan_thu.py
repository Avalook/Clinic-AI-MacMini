"""Một lần thu = nhiều phần theo hình thức (01/10/2026) — hàm thuần."""

from __future__ import annotations

from typing import Any

import pytest

from clinicai.api.exceptions import ValidationError
from clinicai.services.payment_service import (
    LY_DO_HOAN_TAC_MAC_DINH,
    ly_do_hoan_tac,
    ly_do_khong_hoan_tac,
)
from clinicai.services.phan_thu import (
    PhanThu,
    ap_phan,
    cac_hinh_thuc,
    chuan_hinh_thuc,
    doc_phan,
    doc_phan_db,
    hinh_thuc_chinh,
    nhan_phan,
    tra_lai,
)


def test_chia_700k_dung_tong() -> None:
    phan = doc_phan(
        [
            {"hinh_thuc": "TRANSFER", "so_tien": 200_000},
            {"hinh_thuc": "cash", "so_tien": 500_000, "khach_dua": 600_000},
        ]
    )
    assert phan == [
        PhanThu("CASH", 500_000, 600_000),
        PhanThu("TRANSFER", 200_000),
    ]
    ghi = ap_phan(phan, "CASH", 700_000)
    assert sum(p.so_tien for p in ghi) == 700_000
    # Có phần chuyển khoản → lần thu là chuyển khoản (chờ xác minh).
    assert hinh_thuc_chinh(ghi) == "TRANSFER"
    assert tra_lai([p.ra_dict() for p in ghi]) == 100_000


def test_tong_lech_bi_chan() -> None:
    phan = doc_phan(
        [
            {"hinh_thuc": "CASH", "so_tien": 500_000},
            {"hinh_thuc": "TRANSFER", "so_tien": 100_000},
        ]
    )
    with pytest.raises(ValidationError, match="khác số cần thu"):
        ap_phan(phan, "CASH", 700_000)


def test_khong_gui_phan_la_mot_hinh_thuc_qr_cu_thanh_chuyen_khoan() -> None:
    assert ap_phan(None, "CASH", 150_000) == [PhanThu("CASH", 150_000)]
    assert ap_phan(None, "QR", 150_000) == [PhanThu("TRANSFER", 150_000)]
    assert chuan_hinh_thuc(" qr ") == "TRANSFER"
    with pytest.raises(ValidationError):
        ap_phan(None, "THE", 150_000)


@pytest.mark.parametrize(
    "rac",
    [
        [],
        "CASH",
        [1],
        [{"hinh_thuc": "THE", "so_tien": 1}],
        [{"hinh_thuc": "CASH", "so_tien": 0}],
        [{"hinh_thuc": "CASH", "so_tien": "500k"}],
        [{"hinh_thuc": "CASH", "so_tien": True}],
        [{"hinh_thuc": "CASH", "so_tien": float("nan")}],
        [{"hinh_thuc": "CASH", "so_tien": 1}, {"hinh_thuc": "cash", "so_tien": 2}],
        [{"hinh_thuc": "CASH", "so_tien": 500, "khach_dua": 400}],
        [
            {"hinh_thuc": "CASH", "so_tien": 1},
            {"hinh_thuc": "TRANSFER", "so_tien": 1},
            {"hinh_thuc": "QR", "so_tien": 1},
        ],
    ],
)
def test_doc_phan_rac_la_422(rac: Any) -> None:
    with pytest.raises(ValidationError):
        doc_phan(rac)


def test_doc_phan_khach_dua_bang_so_thu_bo_qua() -> None:
    assert doc_phan([{"hinh_thuc": "CASH", "so_tien": 5, "khach_dua": 5}]) == [
        PhanThu("CASH", 5)
    ]
    assert doc_phan(None) is None


def test_doc_phan_db_rac_ra_rong() -> None:
    assert doc_phan_db(None) == []
    assert doc_phan_db("không phải json") == []
    assert doc_phan_db('{"a": 1}') == []
    ds = doc_phan_db('[{"hinh_thuc": "CASH", "so_tien": "500000"}, 3]')
    assert [(p["hinh_thuc"], p["so_tien"]) for p in ds] == [("CASH", 500_000)]


def test_nhan_va_loc_hinh_thuc() -> None:
    hai = [
        {"hinh_thuc": "CASH", "so_tien": 500_000},
        {"hinh_thuc": "TRANSFER", "so_tien": 200_000},
    ]
    assert nhan_phan(hai) == "Tiền mặt 500.000đ + Chuyển khoản 200.000đ"
    assert nhan_phan([{"hinh_thuc": "QR", "so_tien": 1}]) == "Chuyển khoản"
    assert nhan_phan([]) == ""
    assert cac_hinh_thuc(reversed(hai)) == ["CASH", "TRANSFER"]
    assert tra_lai(hai) is None


def test_ly_do_hoan_tac_tuy_chon() -> None:
    assert ly_do_hoan_tac(None) == LY_DO_HOAN_TAC_MAC_DINH
    assert ly_do_hoan_tac("   ") == LY_DO_HOAN_TAC_MAC_DINH
    assert ly_do_hoan_tac("sai") == "Hoàn tác: sai"
    assert ly_do_hoan_tac("Thu nhầm khách  khác") == "Thu nhầm khách khác"
    assert len(ly_do_hoan_tac("x" * 900)) == 500


def test_ly_do_khong_hoan_tac() -> None:
    assert ly_do_khong_hoan_tac("PAID", "dich_vu", False) is None
    assert ly_do_khong_hoan_tac("PENDING_VERIFICATION", "thuoc", True) is None
    assert ly_do_khong_hoan_tac("VOIDED", "dich_vu", False)
    assert ly_do_khong_hoan_tac("PAID", "dich_vu", True)
    # Thuốc có hoàn vẫn hoàn tác được (void thuốc tự xử lý phần đã hoàn).
    assert ly_do_khong_hoan_tac("PAID", "thuoc", True) is None
    assert ly_do_khong_hoan_tac("OPEN", "dich_vu", False)
