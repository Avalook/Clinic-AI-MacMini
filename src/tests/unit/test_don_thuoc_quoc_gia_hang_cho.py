"""Liên thông đơn thuốc quốc gia — phần THUẦN của hàng chờ: trạng thái tính ra,
lùi thời gian thử lại, đánh giá canh gác."""

from __future__ import annotations

from datetime import timedelta

import pytest

from clinicai.services.don_thuoc_quoc_gia.gui import tre_lan_sau
from clinicai.services.don_thuoc_quoc_gia.hang_cho import trang_thai_dong
from clinicai.services.don_thuoc_quoc_gia.vong import danh_gia


@pytest.mark.parametrize(
    ("vao", "ra"),
    [
        ({"da_gui": True, "co_ban_moi_hon": True}, "DA_GUI"),
        ({"co_ban_moi_hon": True, "het_luot": True}, "BI_THAY"),
        ({"la_huy": True}, "KHONG_CAN"),
        ({"la_huy": True, "da_tung_gui": True, "het_luot": True}, "LOI"),
        ({"het_luot": True}, "LOI"),
        ({}, "CHO_GUI"),
    ],
)
def test_trang_thai_tinh_ra(vao: dict[str, bool], ra: str) -> None:
    mac_dinh = dict.fromkeys(
        ("da_gui", "co_ban_moi_hon", "het_luot", "la_huy", "da_tung_gui"), False
    )
    assert trang_thai_dong(**{**mac_dinh, **vao}) == ra


def test_tre_lan_sau_cap_so() -> None:
    assert [tre_lan_sau(n) for n in (1, 2, 3)] == [
        timedelta(minutes=1),
        timedelta(minutes=5),
        timedelta(minutes=25),
    ]


def test_danh_gia_canh_gac() -> None:
    ma = {k.ma: k.co_chuyen for k in danh_gia({"ton_dong": 0, "loi": 2})}
    assert ma == {"DTQG_CAU_HINH_SAI": False, "DTQG_TON_DONG": False, "DTQG_LOI": True}
    (k,) = danh_gia({"loi_cau_hinh": ["DTQG_MA_CO_SO …"]})
    assert (k.ma, k.co_chuyen, k.muc) == ("DTQG_CAU_HINH_SAI", True, "critical")
