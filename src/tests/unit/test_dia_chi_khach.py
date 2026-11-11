"""Địa chỉ khách — MỘT luật (11/11/2026): ô sửa được (`address`) thắng; trống thì ghép
phần có cấu trúc. Trước đó phiếu khám in và PDF hồ sơ khám ưu tiên phần có cấu trúc
(không màn nào sửa được) ⇒ lễ tân sửa địa chỉ xong, giấy in vẫn ra địa chỉ CŨ."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest

from clinicai.phieu_kham.mang_sang import dung_ho_so
from clinicai.services.dia_chi_khach import dia_chi_khach
from clinicai.services.ho_so_kham_service import _lich

CU = {
    "address_detail": "12 Kim Ngưu",
    "ward_name": "Phường Vĩnh Tuy",
    "province_name": "Hà Nội",
}


@pytest.mark.parametrize(
    ("bn", "mong"),
    [
        # Vừa sửa ở hồ sơ: ô tự do mới, phần có cấu trúc còn bản lúc tạo khách.
        ({"address": "  5 Láng Hạ, Đống Đa  ", **CU}, "5 Láng Hạ, Đống Đa"),
        # Khách cũ chỉ có phần có cấu trúc.
        ({"address": None, **CU}, "12 Kim Ngưu, Phường Vĩnh Tuy, Hà Nội"),
        ({"address": "   ", **CU}, "12 Kim Ngưu, Phường Vĩnh Tuy, Hà Nội"),
        ({"address": "", "address_detail": "", "province_name": "Hà Nội"}, "Hà Nội"),
        # Khách Notion: chỉ ô tự do.
        ({"address": "Thanh Xuân"}, "Thanh Xuân"),
        ({}, None),
        ({"address": None, "address_detail": " ", "ward_name": None}, None),
    ],
)
def test_o_sua_duoc_thang_trong_thi_ghep(bn: dict[str, Any], mong: str | None) -> None:
    assert dia_chi_khach(bn) == mong


@pytest.mark.parametrize("rac", [123, 4.5, ["x"], {"a": 1}, object(), True])
def test_rac_thanh_rong_khong_nem(rac: Any) -> None:
    assert dia_chi_khach({"address": rac, "address_detail": rac}) is None
    assert (
        dia_chi_khach({"address": rac, **CU}) == "12 Kim Ngưu, Phường Vĩnh Tuy, Hà Nội"
    )


def test_phieu_kham_in_dia_chi_vua_sua() -> None:
    """Phiếu khám (mang sang) — chỗ trước đây in địa chỉ cũ."""
    assert dung_ho_so({"address": "5 Láng Hạ", **CU})["patient.address"] == "5 Láng Hạ"


def test_pdf_ho_so_kham_in_dia_chi_vua_sua_va_khong_lo_cot_tho() -> None:
    """PDF hồ sơ khám (CSKH) — trước lấy riêng `address_detail` (cũ, thiếu phường)."""
    lich = _lich({"ten": "A", "address": "5 Láng Hạ", **CU})
    assert lich == {"ten": "A", "dia_chi": "5 Láng Hạ"}
    assert _lich({"ten": "B", "address": None, **CU}) == {
        "ten": "B",
        "dia_chi": "12 Kim Ngưu, Phường Vĩnh Tuy, Hà Nội",
    }
    assert _lich(None) is None


SRC = Path(__file__).resolve().parents[2] / "clinicai"
#: Nơi GHI các cột địa chỉ (tạo / sửa khách) — không phải nơi ghép để in.
_NOI_GHI = {
    "schemas/patient.py",
    "services/patient_service.py",
    "services/dia_chi_khach.py",
}


def test_khong_cho_nao_tu_ghep_dia_chi() -> None:
    """Đường cũ chết: tệp nào đọc cột có cấu trúc thì phải đi qua `dia_chi_khach`."""
    lech = []
    for p in SRC.rglob("*.py"):
        rel = p.relative_to(SRC).as_posix()
        if rel in _NOI_GHI:
            continue
        src = p.read_text(encoding="utf-8")
        if re.search(r"\baddress_detail\b", src) and "dia_chi_khach" not in src:
            lech.append(rel)
    assert not lech, f"Tự ghép địa chỉ, không qua dia_chi_khach: {lech}"
