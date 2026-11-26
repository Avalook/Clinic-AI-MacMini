"""Hàm thuần của PR B (26/11/2026): tồn ở ô chọn kê đơn, lý do xoá thuốc."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from clinicai.api.exceptions import ValidationError
from clinicai.services.don_vi_thuoc import BangDonVi, DonViBan
from clinicai.services.thuoc.ke_don import chu_ton_ke_don, sap_xep_ke_don
from clinicai.services.thuoc.xoa_thuoc import doc_ly_do_xoa


def _bang() -> BangDonVi:
    return BangDonVi(
        goc="viên",
        gia_goc=Decimal(9000),
        dong={"hộp": DonViBan("hộp", Decimal(30), Decimal(250000), True)},
    )


def test_chu_ton_cong_ve_don_vi_goc() -> None:
    b = _bang()
    ton = [{"don_vi": "hộp", "ton": 2}, {"don_vi": "viên", "ton": 5}]
    assert chu_ton_ke_don(b, ton) == "còn 65 viên"
    assert chu_ton_ke_don(b, []) == "hết hàng"
    assert chu_ton_ke_don(b, [{"don_vi": "lọ lạ", "ton": 4}]) == "hết hàng"
    # chu_ton cũ (màn Kho thuốc) vẫn ra đúng chữ sau khi tách `ton_goc`.
    assert b.chu_ton(ton) == "= 65 viên · 2 hộp 5 viên"
    assert chu_ton_ke_don(BangDonVi(), [{"don_vi": "hộp", "ton": 3}]) == "còn 3 hộp"


def test_sap_xep_con_hang_truoc_giu_moi_muc_ke_ca_chua_gan_kho_chua_gia() -> None:
    mau: list[dict[str, Any]] = [
        {"ma": "a", "drug_catalog_id": None, "gia": None},
        {"ma": "b", "drug_catalog_id": "B", "gia": None},
        {"ma": "c", "drug_catalog_id": "C", "gia": 1000},
        {"ma": "d", "drug_catalog_id": "D", "gia": 2000},
    ]
    ton = {"D": [{"don_vi": "hộp", "ton": 1}], "B": [{"don_vi": "hộp", "ton": 2}]}
    bang = {k: BangDonVi(goc="hộp") for k in "BCD"}
    ra = sap_xep_ke_don(mau, ton, bang)
    assert [m["ma"] for m in ra] == ["b", "d", "a", "c"], "còn hàng trước, ổn định"
    assert [m["ton_chu"] for m in ra] == ["còn 2 hộp", "còn 1 hộp", None, "hết hàng"]


@pytest.mark.parametrize("rac", ["", "   ", None, "x" * 501, "\n\t"])
def test_ly_do_xoa_rac_thanh_422(rac: Any) -> None:
    with pytest.raises(ValidationError):
        doc_ly_do_xoa(rac)


def test_ly_do_xoa_gon_dau_cach() -> None:
    assert doc_ly_do_xoa("  nhập   trùng ") == "nhập trùng"
