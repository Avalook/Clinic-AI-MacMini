"""Mã ống Damm (kế hoạch 2.B, 4.5). Test chéo SQL ↔ Python ở test DB của chặng 3."""

from __future__ import annotations

import pytest

from clinicai.services.xet_nghiem.ma_mau import (
    chu_so_kiem,
    ma_hop_le,
    tao_ma,
    tim_ma_trong_ten,
)


def test_vecto_kiem_ke_hoach() -> None:
    assert chu_so_kiem("00572") == 4
    assert tao_ma(572) == "M005724"


def test_so_lon_khong_cat() -> None:
    assert tao_ma(123456).startswith("M123456")


@pytest.mark.parametrize("n", range(1, 1001))
def test_moi_ma_tu_cap_deu_hop_le(n: int) -> None:
    assert ma_hop_le(tao_ma(n))


def test_bat_moi_loi_mot_chu_so_va_dao_cap() -> None:
    for n in range(1, 1001):
        ma = tao_ma(n)
        so = ma[1:]
        for i in range(len(so)):
            for d in "0123456789":
                if d != so[i]:
                    assert not ma_hop_le("M" + so[:i] + d + so[i + 1 :])
        for i in range(len(so) - 1):
            if so[i] != so[i + 1]:
                dao = so[:i] + so[i + 1] + so[i] + so[i + 2 :]
                assert not ma_hop_le("M" + dao)


@pytest.mark.parametrize(
    "rac", ["", "   ", "M", "M12", "X005724", "M00572A", "005724", None, 123]
)
def test_rac_khong_nem(rac: object) -> None:
    assert ma_hop_le(rac) is False  # type: ignore[arg-type]


def test_chu_thuong_va_khoang_trang() -> None:
    assert ma_hop_le(" m005724 ")


def test_tim_trong_ten_tep() -> None:
    assert tim_ma_trong_ten("M005724_ket-qua.pdf") == ["M005724"]
    assert tim_ma_trong_ten("M005725.pdf") == []  # sai số kiểm
    assert tim_ma_trong_ten("ketqua.pdf") == []
    assert tim_ma_trong_ten(None) == []  # type: ignore[arg-type]
