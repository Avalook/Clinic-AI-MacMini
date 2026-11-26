"""PR E: đề xuất cấu trúc từ câu cách dùng danh mục (chỉ đề xuất, không ghi)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from clinicai.services.thuoc.tach_cau import de_xuat


def test_ngay_2_lan_moi_lan_1_vien() -> None:
    ct = de_xuat("Ngày uống 2 lần, mỗi lần 1 viên. Uống sau ăn sáng và sau ăn trưa.")
    assert (ct.kieu, ct.so_lan, ct.moi_lan) == ("ngay", 2, Decimal(1))


def test_tuan_dat_2_lan() -> None:
    ct = de_xuat("Tuần đặt 2 lần, mỗi lần 1 viên vào buổi tối.")
    assert (ct.kieu, ct.so_lan, ct.moi_lan) == ("tuan", 2, Decimal(1))


def test_khoang_so_lan_va_lieu() -> None:
    ct = de_xuat("Ngày 1 - 2 lần, mỗi lần 1 viên. Ưu tiên đặt âm đạo buổi tối.")
    assert ct.kieu == "ngay" and ct.khoang_so_lan == (1, 2) and ct.so_lan is None
    ct2 = de_xuat("Ngày 2 lần, mỗi lần 1-2 viên")
    assert ct2.khoang_lan == (Decimal(1), Decimal(2)) and ct2.moi_lan is None


def test_chu_ky_kinh() -> None:
    ct = de_xuat("1 viên/ngày 21h từ ngày 5 tới 25 CKK")
    assert (ct.kieu, ct.tu_ngay, ct.den_ngay) == ("chu_ky", 5, 25)


def test_trong_n_ngay() -> None:
    ct = de_xuat("Ngày uống 2 lần, mỗi lần 2 viên, trong 7 ngày")
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
    assert de_xuat(cau).kieu == "chu"


def test_cach_ngay() -> None:
    assert de_xuat("Đặt cách ngày, buổi tối").kieu == "cach_ngay"
