"""Nhãn vai cho bảng lịch (27/09/2026 đợt 3, A9) — máy chủ trả, không đoán."""

from __future__ import annotations

from typing import Any

import pytest

from clinicai.api.identity import ClinicRole
from clinicai.services.nhan_vai import NHAN_VAI, gan_nhan_vai, nhan_vai


def test_moi_vai_lam_viec_deu_co_nhan() -> None:
    """Thêm một vai mới mà quên nhãn → người ấy hiện không vai trên lịch."""
    lam_viec = {r.value for r in ClinicRole} - {"DISPLAY", "PARTNER"}
    assert sorted(lam_viec - NHAN_VAI.keys()) == []
    for day_du, ngan in NHAN_VAI.values():
        assert day_du and ngan and len(ngan) <= len(day_du)


def test_nhan_vai_thuong() -> None:
    assert nhan_vai("NURSE_ULTRASOUND") == ("Điều dưỡng", "ĐD")
    assert nhan_vai("DOCTOR") == ("Bác sĩ", "BS")
    assert nhan_vai(" reception ") == ("Lễ tân", "Lễ tân")


@pytest.mark.parametrize("rac", [None, "", "KHONG_CO", 42, ["DOCTOR"], "DISPLAY"])
def test_nhan_vai_rac_tra_rong_khong_nem(rac: Any) -> None:
    assert nhan_vai(rac) == ("", "")


def test_gan_nhan_vai_thay_cot_ma() -> None:
    d = gan_nhan_vai({"staff_name": "Hà", "vai_ma": "TKYK"})
    assert d == {"staff_name": "Hà", "vai": "Thư ký Y khoa", "vai_ngan": "TKYK"}
    # Dòng nhập tay không nối được ai → vai_ma NULL → rỗng.
    assert gan_nhan_vai({"vai_ma": None})["vai"] == ""
    assert gan_nhan_vai({})["vai_ngan"] == ""
