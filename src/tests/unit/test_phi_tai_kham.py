"""Phí khám tái khám theo KiotViet (28/09/2026) — bill_service.dong_kham thuần."""

from __future__ import annotations

from clinicai.services.bill_service import dong_kham

GIA = [
    {"name": "Hiếm muộn / Vô sinh", "unit_price": 400000, "billing_owner": "CLINIC"},
    {
        "name": "Hiếm muộn / Vô sinh (tái khám)",
        "unit_price": 150000,
        "billing_owner": "CLINIC",
    },
    {"name": "Phụ khoa", "unit_price": 300000, "billing_owner": "CLINIC"},
]


def _row(ten: str, tai_kham: bool) -> dict[str, object]:
    return {"st_id": "st", "name": ten, "khong_hen": False, "tai_kham": tai_kham}


def test_lan_dau_tinh_gia_lan_dau() -> None:
    k = dong_kham(_row("Hiếm muộn / Vô sinh", False), GIA)
    assert k is not None and k["gia"] == [400000]


def test_tai_kham_co_dong_rieng_thi_tinh_gia_tai_kham() -> None:
    k = dong_kham(_row("Hiếm muộn / Vô sinh", True), GIA)
    assert k is not None and k["gia"] == [150000]
    assert k["ten"] == "Hiếm muộn / Vô sinh (tái khám)"


def test_tai_kham_khong_co_dong_rieng_thi_nhu_lan_dau() -> None:
    k = dong_kham(_row("Phụ khoa", True), GIA)
    assert k is not None and k["gia"] == [300000] and k["ten"] == "Phụ khoa"
