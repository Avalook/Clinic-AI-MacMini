"""Bàn khám: cột ĐVT ghi "hộp (60 viên)" từ khối đơn vị con (Tuyền 26/11)."""

from __future__ import annotations

from decimal import Decimal

from clinicai.services.thuoc.ke_don import chu_quy_cach


def test_chu_quy_cach() -> None:
    r = {"don_vi_con": "viên", "so_con": Decimal("60.00")}
    assert chu_quy_cach(r) == "60 viên"
    assert chu_quy_cach({**r, "so_con": Decimal(1)}) is None  # hộp 1 viên: thừa
    assert chu_quy_cach({**r, "don_vi_con": None}) is None
