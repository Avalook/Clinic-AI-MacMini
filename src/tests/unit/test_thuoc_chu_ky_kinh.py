"""Thuốc dùng theo chu kỳ kinh (Tuyền 26/11): đọc câu, chọn kỳ, mốc sửa tay.

Ngày 1 của chu kỳ = ngày đầu ra máu kinh; chu kỳ trung bình 28 ngày (Cleveland Clinic).
"""

from __future__ import annotations

from datetime import date

import pytest

from clinicai.services.thuoc.cach_dung import CachDung, tinh_dong, uoc_tinh_chu_ky
from clinicai.services.thuoc.cach_dung_db import _ghi_de_moc_chu_ky
from clinicai.services.thuoc.tach_cau import de_xuat_cach_dung


@pytest.mark.parametrize(
    ("cau", "moc"),
    [
        ("Uống từ ngày thứ 14 đến ngày 25 của chu kỳ kinh.", (14, 25)),
        (
            "Uống 1 viên/ngày bắt đầu từ ngày 1 chu kỳ kinh trong 21 ngày liên tiếp",
            (1, 21),
        ),
        ("Ngày 1 lần, mỗi lần 1 viên từ ngày 5 - 25 vòng kinh.", (5, 25)),
    ],
)
def test_doc_cau_chu_ky(cau: str, moc: tuple[int, int]) -> None:
    ct = de_xuat_cach_dung(cau)
    assert (ct.kieu, ct.tu_ngay, ct.den_ngay) == ("chu_ky", *moc)


def test_dung_ky_hien_tai_neu_chua_qua_ngay_bat_dau() -> None:
    # Kinh 24/11, khám 26/11 (ngày 3), uống ngày 5–25 → ngay kỳ này: 28/11 → 18/12.
    u = uoc_tinh_chu_ky(date(2026, 11, 24), 28, 5, 25, date(2026, 11, 26))
    assert (u["bat_dau"], u["het"]) == (date(2026, 11, 28), date(2026, 12, 18))
    # Ngày 1 của kỳ này đã qua → kỳ sau.
    u = uoc_tinh_chu_ky(date(2026, 11, 24), 28, 1, 21, date(2026, 11, 26))
    assert u["bat_dau"] == date(2026, 12, 22)


def test_lieu_khoang_van_ra_ngay() -> None:
    """Duphaston "2–4 viên" + ngày 14–25: ngày uống không phụ thuộc liều."""
    ct = de_xuat_cach_dung(
        "Ngày uống 2 - 4 viên chia 2 lần sau ăn. "
        "Uống từ ngày thứ 14 đến ngày 25 của chu kỳ kinh."
    )
    kq = tinh_dong(
        ct,
        so_luong="1",
        he_so=None,
        lieu_moi_kho=None,
        don_vi_kho="hộp",
        ngay_ke=date(2026, 11, 26),
        kinh=(date(2026, 11, 24), 28),
    )
    assert kq["theo_chu_ky"] and kq["so_ngay"] == 12
    assert kq["uoc_tinh"]["bat_dau"] == date(2026, 12, 7)


def test_bac_si_sua_moc_tay() -> None:
    ct = _ghi_de_moc_chu_ky(de_xuat_cach_dung("Ngày uống 1 viên"), 10, 20)
    assert (ct.kieu, ct.tu_ngay, ct.den_ngay) == ("chu_ky", 10, 20)
    goc = CachDung(kieu="chu_ky", tu_ngay=14, den_ngay=25)
    assert _ghi_de_moc_chu_ky(goc, None, None) is goc
    assert _ghi_de_moc_chu_ky(goc, 20, 10) is goc  # ngược thứ tự → giữ nguyên
