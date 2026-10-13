"""Phép tính giảm giá theo tổng hoá đơn (Tuyền chốt 09/10 + 13/10/2026) — thuần.

Hai bất biến quan trọng nhất, vì sai một đồng là lệch sổ + lệch hoàn tiền:
  * tổng phần giảm chia xuống dòng LUÔN đúng bằng tổng giảm;
  * không dòng nào bị giảm quá giá của nó.
Liệu trình trả trước và dòng đối tác không bao giờ nhận giảm.
"""

from __future__ import annotations

import random
from decimal import Decimal

import pytest

from clinicai.api.exceptions import ValidationError
from clinicai.services.bill_service import (
    CLINIC,
    EXTERNAL,
    DongHoaDon,
    HoaDon,
    ap_giam_gia,
    phan_bo_giam,
    tong_giam_duoc,
)


def _dong(
    gia: int,
    *,
    loai: str = "service_order",
    ben: str = CLINIC,
    van_de: str | None = None,
) -> DongHoaDon:
    return DongHoaDon(
        source_type=loai,
        source_id=f"{loai}-{gia}-{random.random()}",
        ten="dịch vụ",
        so_luong=Decimal(1),
        don_vi=None,
        don_gia=Decimal(gia),
        thanh_tien=Decimal(gia),
        ben_thu=ben,
        van_de=van_de,
    )


def _hd(*gia: int) -> HoaDon:
    return HoaDon(visit_id="v", kind="dich_vu", dong=[_dong(g) for g in gia])


def test_phan_tram_lam_tron_nua_len() -> None:
    # 12,5% của 1.003đ = 125,375đ → 125đ; 12,5% của 1.004đ = 125,5đ → 126đ.
    assert ap_giam_gia(_hd(1_003), "PERCENT", Decimal("12.5")) == (1_003, 125, 878)
    assert ap_giam_gia(_hd(1_004), "PERCENT", Decimal("12.5")) == (1_004, 126, 878)


def test_so_tien_lam_tron_nua_len() -> None:
    assert ap_giam_gia(_hd(1_000), "AMOUNT", Decimal("100.5"))[1] == 101
    assert ap_giam_gia(_hd(1_000), "AMOUNT", Decimal("100.4"))[1] == 100


def test_giam_het_duoc_va_vuot_thi_tu_choi() -> None:
    assert ap_giam_gia(_hd(150_000, 250_000), "PERCENT", Decimal(100)) == (
        400_000,
        400_000,
        0,
    )
    assert ap_giam_gia(_hd(400_000), "AMOUNT", Decimal(400_000))[2] == 0
    with pytest.raises(ValidationError, match="vượt"):
        ap_giam_gia(_hd(400_000), "AMOUNT", Decimal(400_001))


@pytest.mark.parametrize(
    ("loai", "gia_tri"),
    [
        ("PERCENT", Decimal("100.01")),
        ("PERCENT", Decimal(0)),
        ("PERCENT", Decimal(-1)),
        ("AMOUNT", Decimal(0)),
        ("AMOUNT", Decimal("0.4")),  # làm tròn còn 0đ
        ("AMOUNT", Decimal("NaN")),
        ("AMOUNT", Decimal("Infinity")),
        ("KHAC", Decimal(10)),
    ],
)
def test_rac_bi_tu_choi(loai: str, gia_tri: Decimal) -> None:
    with pytest.raises(ValidationError):
        ap_giam_gia(_hd(100_000), loai, gia_tri)


def test_lieu_trinh_khong_giam_va_phan_tram_tinh_tren_phan_giam_duoc() -> None:
    hd = HoaDon(
        visit_id="v",
        kind="dich_vu",
        dong=[_dong(150_000), _dong(3_000_000, loai="lieu_trinh")],
    )
    assert hd.tong == 3_150_000 and tong_giam_duoc(hd) == 150_000
    # 100% chỉ giảm phần 150k; liệu trình 3tr vẫn phải thu.
    assert ap_giam_gia(hd, "PERCENT", Decimal(100)) == (3_150_000, 150_000, 3_000_000)
    assert phan_bo_giam(hd.dong, 150_000) == [150_000, 0]
    with pytest.raises(ValidationError, match="vượt"):
        ap_giam_gia(hd, "AMOUNT", Decimal(150_001))


def test_hoa_don_chi_co_lieu_trinh_hoac_0d_khong_co_gi_de_giam() -> None:
    chi_lieu_trinh = HoaDon(
        visit_id="v", kind="dich_vu", dong=[_dong(3_000_000, loai="lieu_trinh")]
    )
    with pytest.raises(ValidationError, match="không có khoản nào giảm"):
        ap_giam_gia(chi_lieu_trinh, "PERCENT", Decimal(10))
    with pytest.raises(ValidationError, match="không có khoản nào giảm"):
        ap_giam_gia(_hd(0, 0), "PERCENT", Decimal(10))


def test_dong_doi_tac_va_dong_co_van_de_khong_nhan_giam() -> None:
    dong = [
        _dong(100_000),
        _dong(900_000, ben=EXTERNAL),
        _dong(50_000, van_de="thiếu giá"),
    ]
    assert phan_bo_giam(dong, 40_000) == [40_000, 0, 0]


def test_dong_0d_giu_nguyen_khi_giam() -> None:
    assert phan_bo_giam([_dong(0), _dong(250_000)], 250_000) == [0, 250_000]


def test_chia_khong_chan_dong_dung_tong_va_khong_qua_gia() -> None:
    # 100.001 chia 3 dòng 1/3 mỗi dòng: phần dư dồn đủ, không mất đồng nào.
    dong = [_dong(100_000), _dong(100_000), _dong(100_000)]
    ra = phan_bo_giam(dong, 100_001)
    assert sum(ra) == 100_001 and sorted(ra) == [33_333, 33_334, 33_334]


def test_ngau_nhien_luon_dung_tong_va_khong_qua_gia() -> None:
    rng = random.Random(1310)
    for _ in range(2_000):
        dong = [_dong(rng.choice([0, 1, 7, 999, 12_345, 250_000, 3_000_001]))]
        dong += [_dong(rng.randint(0, 900_000)) for _ in range(rng.randint(0, 6))]
        duoc = sum(int(d.thanh_tien or 0) for d in dong)
        if duoc == 0:
            assert phan_bo_giam(dong, 0) == [0] * len(dong)
            continue
        tong = rng.randint(1, duoc)
        ra = phan_bo_giam(dong, tong)
        assert sum(ra) == tong
        assert all(0 <= r <= int(d.thanh_tien or 0) for r, d in zip(ra, dong))


def test_chia_vuot_phan_giam_duoc_la_loi_lap_trinh() -> None:
    with pytest.raises(ValueError):
        phan_bo_giam([_dong(100)], 101)
