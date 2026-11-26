"""PR E: đề xuất cấu trúc từ câu cách dùng danh mục (chỉ đề xuất, không ghi)."""

from __future__ import annotations

from decimal import Decimal
from fractions import Fraction

import pytest

from clinicai.services.thuoc.cach_dung import lieu_ngay
from clinicai.services.thuoc.tach_cau import de_xuat_cach_dung


def test_ngay_2_lan_moi_lan_1_vien() -> None:
    ct = de_xuat_cach_dung(
        "Ngày uống 2 lần, mỗi lần 1 viên. Uống sau ăn sáng và sau ăn trưa."
    )
    assert (ct.kieu, ct.so_lan, ct.moi_lan) == ("ngay", 2, Decimal(1))


def test_tuan_dat_2_lan() -> None:
    ct = de_xuat_cach_dung("Tuần đặt 2 lần, mỗi lần 1 viên vào buổi tối.")
    assert (ct.kieu, ct.so_lan, ct.moi_lan) == ("tuan", 2, Decimal(1))


def test_khoang_so_lan_va_lieu() -> None:
    ct = de_xuat_cach_dung(
        "Ngày 1 - 2 lần, mỗi lần 1 viên. Ưu tiên đặt âm đạo buổi tối."
    )
    assert ct.kieu == "ngay" and ct.khoang_so_lan == (1, 2) and ct.so_lan is None
    ct2 = de_xuat_cach_dung("Ngày 2 lần, mỗi lần 1-2 viên")
    assert ct2.khoang_lan == (Decimal(1), Decimal(2)) and ct2.moi_lan is None


def test_chu_ky_kinh() -> None:
    ct = de_xuat_cach_dung("1 viên/ngày 21h từ ngày 5 tới 25 CKK")
    assert (ct.kieu, ct.tu_ngay, ct.den_ngay) == ("chu_ky", 5, 25)


def test_trong_n_ngay() -> None:
    ct = de_xuat_cach_dung("Ngày uống 2 lần, mỗi lần 2 viên, trong 7 ngày")
    assert ct.trong_ngay == 7 and ct.moi_lan == Decimal(2)


@pytest.mark.parametrize(
    "cau",
    [
        "Bôi lớp mỏng lên vùng da",
        "Xịt 1 nhát mỗi tối",
        "Dùng theo chỉ định của bác sĩ",
        "Uống một lần duy nhất",
        "mỗi lần 1/3 gói",
        "",
        None,
        "abc xyz",
    ],
)
def test_khong_chac_thi_chi_chu(cau: str | None) -> None:
    assert de_xuat_cach_dung(cau).kieu == "chu"


def test_cach_ngay() -> None:
    assert de_xuat_cach_dung("Đặt cách ngày, buổi tối").kieu == "cach_ngay"


@pytest.mark.parametrize(
    ("cau", "lieu_moi_ngay"),
    [
        ("Ngày 2 viên, sáng 1, tối 1, sau ăn", Fraction(2)),
        ("Ngày uống 2 lần, mỗi lần 1 viên. Đợt dùng 7 ngày.", Fraction(2)),
        ("Cách ngày uống 1 viên", Fraction(1, 2)),
        ("2 ngày uống 1 viên", Fraction(1, 2)),
        ("3 ngày uống 1 lần, mỗi lần 1 viên", Fraction(1, 3)),
        ("Tuần 03 viên, mỗi lần 01 viên - uống cách ngày sau ăn tối.", Fraction(3, 7)),
        ("Mỗi tuần uống duy nhất 1 viên vào 1 ngày cố định.", Fraction(1, 7)),
        ("Tháng uống 1 lần, mỗi lần 1 viên", Fraction(1, 30)),
        ("Ngày uống 4 viên chia 2 lần (sáng - tối) sau ăn", Fraction(4)),
    ],
)
def test_lieu_moi_ngay_theo_ngay_tuan_thang_moi_n_ngay(
    cau: str, lieu_moi_ngay: Fraction
) -> None:
    """Tuyền 26/11: gõ chữ ở danh mục, máy tự hiểu ngày / N ngày / tuần / tháng."""
    assert lieu_ngay(de_xuat_cach_dung(cau)) == lieu_moi_ngay
