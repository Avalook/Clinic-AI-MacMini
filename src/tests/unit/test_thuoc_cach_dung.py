"""PR E (26/11/2026): cách dùng có cấu trúc — hàm thuần (kế hoạch mục 2, 4, 5, 6, 10).

Số liệu theo trang giả lập Tuyền đã duyệt: Ecanix 1 hộp 60 viên, 2 lần × 1 viên.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from fractions import Fraction
from typing import Any

import pytest
from pydantic import ValidationError

from clinicai.services.thuoc.cach_dung import (
    CachDung,
    cau_cach_dung,
    doc_chu_ky,
    doc_ct,
    doc_ngay_kinh,
    lieu_ngay,
    so_luong_so,
    tinh_dong,
)

KE = date(2026, 11, 26)
ECANIX = CachDung(kieu="ngay", moi_lan=Decimal(1), so_lan=2, thoi_diem="sau ăn sáng")


def _tinh(
    ct: CachDung,
    sl: str,
    he_so: int | None = 60,
    lieu_moi_kho: Fraction | None = Fraction(1),
    kinh: tuple[date, int] | None = None,
) -> dict[str, Any]:
    return tinh_dong(
        ct,
        so_luong=sl,
        he_so=Fraction(he_so) if he_so is not None else None,
        lieu_moi_kho=lieu_moi_kho,
        don_vi_kho="viên",
        ngay_ke=KE,
        kinh=kinh,
    )


def test_ecanix_mot_hop_30_ngay_het_25_12() -> None:
    kq = _tinh(ECANIX, "1")
    assert kq["tinh_duoc"] and kq["so_ngay"] == 30
    assert kq["ngay_het"] == date(2026, 12, 25)
    assert kq["lieu_ngay"] == "2"


def test_ecanix_10_vien_5_ngay() -> None:
    kq = _tinh(ECANIX, "10 viên", he_so=1)
    assert kq["so_ngay"] == 5 and kq["ngay_het"] == date(2026, 11, 30)


def test_tuan_2_lan_1_vien() -> None:
    ct = CachDung(kieu="tuan", moi_lan=Decimal(1), so_lan=2)
    assert lieu_ngay(ct) == Fraction(2, 7)
    kq = _tinh(ct, "8", he_so=1)
    assert kq["so_ngay"] == 28  # 8 viên ÷ 2/7 viên/ngày
    assert cau_cach_dung(ct) == "Tuần 2 lần, mỗi lần 1 viên."


def test_cach_ngay() -> None:
    ct = CachDung(kieu="cach_ngay", moi_lan=Decimal(1))
    assert lieu_ngay(ct) == Fraction(1, 2)
    assert _tinh(ct, "10", he_so=1)["so_ngay"] == 20
    assert cau_cach_dung(ct) == "Cách ngày 1 lần, mỗi lần 1 viên."


def test_chu_ky_5_25_la_21_ngay_khong_ngay_lich() -> None:
    ct = CachDung(kieu="chu_ky", moi_lan=Decimal(1), so_lan=1, tu_ngay=5, den_ngay=25)
    kq = _tinh(ct, "1")
    assert kq["so_ngay"] == 21 and kq["so_lieu_can"] == "21"
    assert kq["ngay_het"] is None and kq["uoc_tinh"] is None
    assert kq["goi_y_so_luong"] == 1  # 21 viên → 1 hộp 60
    assert "từ ngày 5 đến ngày 25 chu kỳ kinh" in cau_cach_dung(ct)


def test_chu_ky_uoc_tinh_tu_lmp() -> None:
    ct = CachDung(kieu="chu_ky", moi_lan=Decimal(1), so_lan=1, tu_ngay=5, den_ngay=25)
    lmp = doc_ngay_kinh("10/11/2026", KE)
    assert lmp == date(2026, 11, 10)
    kq = _tinh(ct, "1", kinh=(lmp, 28))
    assert kq["uoc_tinh"] == {
        "kinh_toi": date(2026, 12, 8),
        "bat_dau": date(2026, 12, 12),
        "het": date(2027, 1, 1),
    }


@pytest.mark.parametrize(
    "rac", ["abc", "31/02/2026", "", None, "   ", 12345, "10/11/2099", "2026-13-01"]
)
def test_lmp_rac_khong_uoc_tinh_khong_nem(rac: object) -> None:
    assert doc_ngay_kinh(rac, KE) is None


@pytest.mark.parametrize("rac", ["", None, "abc", "5", "100", "-28", "28.5"])
def test_chu_ky_rac(rac: object) -> None:
    assert doc_chu_ky(rac) is None


def test_chu_ky_doc_duoc() -> None:
    assert doc_chu_ky("28") == 28 and doc_chu_ky("30 ngày") == 30


def test_khoang_chua_chon_khong_tinh() -> None:
    ct = CachDung(kieu="ngay", khoang_lan=(Decimal(1), Decimal(2)), so_lan=2)
    kq = _tinh(ct, "1")
    assert not kq["tinh_duoc"] and kq["so_ngay"] is None
    assert "chọn một số" in kq["ly_do"]
    assert cau_cach_dung(ct) == "Ngày 2 lần, mỗi lần 1–2 viên."
    chon = ct.model_copy(update={"moi_lan": Decimal(2)})
    assert _tinh(chon, "1")["so_ngay"] == 15


def test_khoang_chon_ngoai_khoang_bi_tu_choi() -> None:
    with pytest.raises(ValidationError):
        CachDung.model_validate(
            {"kieu": "ngay", "moi_lan": 3, "khoang_lan": [1, 2], "so_lan": 1}
        )


def test_thieu_so_vien_moi_hop_tra_ly_do() -> None:
    kq = _tinh(ECANIX, "1", lieu_moi_kho=None)
    assert not kq["tinh_duoc"] and kq["ly_do"].startswith("Chưa khai 1 viên")


def test_lieu_nua_vien() -> None:
    ct = CachDung(kieu="ngay", moi_lan=Decimal("0.5"), so_lan=1)
    assert _tinh(ct, "10", he_so=1)["so_ngay"] == 20
    assert cau_cach_dung(ct) == "Ngày 1 lần, mỗi lần 0,5 viên."


def test_goi_y_so_luong_lam_tron_len() -> None:
    ct = ECANIX.model_copy(update={"trong_ngay": 31})
    assert _tinh(ct, "")["goi_y_so_luong"] == 2  # 62 viên → 2 hộp
    assert _tinh(ct, "", he_so=1)["goi_y_so_luong"] == 62
    ct7 = CachDung(kieu="ngay", moi_lan=Decimal("0.5"), so_lan=1, trong_ngay=7)
    assert _tinh(ct7, "", he_so=1)["goi_y_so_luong"] == 4  # 3,5 viên → 4


def test_chi_chu_khong_tinh_giu_chu() -> None:
    ct = CachDung(kieu="chu")
    assert _tinh(ct, "1")["ly_do"].startswith("Chỉ ghi chữ")
    assert cau_cach_dung(ct, " Bôi lớp mỏng ") == "Bôi lớp mỏng"
    assert cau_cach_dung(None, "chữ cũ") == "chữ cũ"


def test_cau_co_trong_ngay_va_thoi_diem() -> None:
    ct = ECANIX.model_copy(update={"trong_ngay": 30})
    cau = "Ngày 2 lần, mỗi lần 1 viên, trong 30 ngày. Sau ăn sáng."
    assert cau_cach_dung(ct) == cau


@pytest.mark.parametrize("sl", ["9999999", "9" * 50, "1" + "0" * 30 + " hộp"])
def test_so_luong_qua_lon_khong_500(sl: str) -> None:
    kq = _tinh(ECANIX, sl)  # trước đây: OverflowError ngày vượt lịch → 500
    assert not kq["tinh_duoc"] and kq["ngay_het"] is None
    assert "quá lớn" in kq["ly_do"]


def test_so_luong_rac() -> None:
    assert so_luong_so("1/2") is None and so_luong_so("0") is None
    assert so_luong_so("abc") is None and so_luong_so(None) is None
    assert so_luong_so("1,5") == Fraction(3, 2)


def test_doc_ct_hong_tra_none() -> None:
    assert doc_ct('{"kieu": "la"}') is None
    assert doc_ct("không phải json") is None
    assert doc_ct({"kieu": "ngay", "moi_lan": 1, "so_lan": 2}) is not None
