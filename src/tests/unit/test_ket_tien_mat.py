"""Kiểm kê tiền mặt két (31/10/2026) — hàm thuần, không cần DB."""

from __future__ import annotations

from typing import Any

import pytest

from clinicai.api.exceptions import ValidationError
from clinicai.services.ket_tien_mat_service import (
    doc_dem,
    tien_mat_trong_ca,
    tinh_cuoi,
    tong_ket,
)


def test_bang_dem_cong_tu_dong() -> None:
    tong, bang = doc_dem(None, {"500000": 2, "200000": 1, "1000": 3, "2000": 0})
    assert tong == 1_203_000
    assert bang == {"500000": 2, "200000": 1, "1000": 3}


def test_tong_go_tay() -> None:
    assert doc_dem(1_500_000, None) == (1_500_000, None)
    assert doc_dem(0, None) == (0, None)


def test_tong_khac_bang_dem_thi_422() -> None:
    with pytest.raises(ValidationError, match="khác tổng bảng đếm"):
        doc_dem(1_000_000, {"500000": 1})


@pytest.mark.parametrize(
    "rac",
    [
        (None, None),
        (-1, None),
        ("100000", None),
        (True, None),
        (1.5, None),
        (float("nan"), None),
        (10**12, None),
        (None, {"300000": 1}),
        (None, {"500000": -1}),
        (None, {"500000": "2"}),
        (None, {"500000": 1.5}),
        (None, ["500000"]),
        (None, {"abc": 1}),
    ],
)
def test_dau_vao_rac(rac: tuple[Any, Any]) -> None:
    with pytest.raises(ValidationError):
        doc_dem(*rac)


def test_tien_mat_trong_ca_lay_dung_dong_tien_mat() -> None:
    bc = {
        "theo_hinh_thuc": [
            {
                "ma": "CASH",
                "thu": 900_000,
                "huy": 100_000,
                "hoan": 50_000,
                "thuc_thu": 750_000,
            },
            {"ma": "TRANSFER", "thu": 5, "huy": 0, "hoan": 0, "thuc_thu": 5},
        ]
    }
    assert tien_mat_trong_ca(bc) == {
        "thu": 900_000,
        "huy": 100_000,
        "hoan": 50_000,
        "thuc_thu": 750_000,
    }
    assert tien_mat_trong_ca({}) == {"thu": 0, "huy": 0, "hoan": 0, "thuc_thu": 0}


def test_du_kien_va_lech() -> None:
    assert tinh_cuoi(1_000_000, 750_000, 1_700_000) == {
        "du_kien": 1_750_000,
        "lech": -50_000,
    }
    assert tinh_cuoi(0, 0, 0) == {"du_kien": 0, "lech": 0}


def test_tong_ket_chi_cong_ca_da_dem() -> None:
    ds = [
        {
            "da_dem": True,
            "quy_dau": 1,
            "thu_tien_mat": 2,
            "du_kien": 3,
            "dem_cuoi": 4,
            "lech": 1,
        },
        {"da_dem": False, "quy_dau": 100},
    ]
    assert tong_ket(ds) == {
        "so_ca": 1,
        "quy_dau": 1,
        "thu_tien_mat": 2,
        "du_kien": 3,
        "dem_cuoi": 4,
        "lech": 1,
    }
