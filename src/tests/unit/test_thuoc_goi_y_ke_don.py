"""Hàm thuần của PR B (26/11/2026): gợi ý tên thuốc, ô chọn kê đơn, chuông kho."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from clinicai.events.consumers.chuong import _chuong_kho
from clinicai.events.worker import SuKienDaNhan
from clinicai.services.don_vi_thuoc import BangDonVi, DonViBan
from clinicai.services.thuoc.goi_y import cau_khong_co_thuoc, xep_goi_y
from clinicai.services.thuoc.ke_don import chu_ton_ke_don, sap_xep_ke_don

DANH_MUC: list[dict[str, Any]] = [
    {"id": "1", "ten": "Idurat 5mg", "biet_duoc": "Indurat 5mg / Tadalafil"},
    {"id": "2", "ten": "Aktiv isoflavon", "biet_duoc": None},
    {"id": "3", "ten": "Vitcofol", "biet_duoc": "Acid folic"},
    {"id": "4", "ten": "Eulac", "biet_duoc": "Gynoflor"},
    {"id": "5", "ten": "Duphaston", "biet_duoc": "Dydrogesterone"},
    {"id": "6", "ten": "Ecanix D3", "biet_duoc": None},
]


@pytest.mark.parametrize(
    ("go", "ra"),
    [
        ("Indurate", "Idurat 5mg"),
        ("AktiveMeno", "Aktiv isoflavon"),
        ("vicofol", "Vitcofol"),
        ("gynoflor", "Eulac"),
        ("GYNOFLOR", "Eulac"),
        ("Dupaston", "Duphaston"),
    ],
)
def test_goi_y_ca_that(go: str, ra: str) -> None:
    assert xep_goi_y(go, DANH_MUC)[0]["ten"] == ra


@pytest.mark.parametrize(
    "rac", ["", "   ", "ab", "!!!@@@", "x" * 100_000, None, 12345, "\x00\x01"]
)
def test_goi_y_dau_vao_rac_khong_nem(rac: Any) -> None:
    assert xep_goi_y(rac, DANH_MUC) == []


def test_goi_y_khong_ra_thuoc_khong_lien_quan() -> None:
    assert xep_goi_y("paracetamol", DANH_MUC) == []


def test_cau_422_co_goi_y_va_loi_nho_kho() -> None:
    cau = cau_khong_co_thuoc("Indurate", [{"ten": "Idurat 5mg"}])
    assert "“Indurate” không có trong danh mục" in cau
    assert "“Idurat 5mg”" in cau and "Nhờ kho thêm thuốc" in cau


def _bang() -> BangDonVi:
    return BangDonVi(
        goc="viên",
        gia_goc=Decimal(9000),
        dong={"hộp": DonViBan("hộp", Decimal(30), Decimal(250000), True)},
    )


def test_chu_ton_cong_ve_don_vi_goc() -> None:
    b = _bang()
    ton = [{"don_vi": "hộp", "ton": 2}, {"don_vi": "viên", "ton": 5}]
    assert chu_ton_ke_don(b, ton) == "còn 65 viên"
    assert chu_ton_ke_don(b, []) == "hết hàng"
    assert chu_ton_ke_don(b, [{"don_vi": "lọ lạ", "ton": 4}]) == "hết hàng"
    # chu_ton cũ (màn Kho thuốc) vẫn ra đúng chữ sau khi tách `ton_goc`.
    assert b.chu_ton(ton) == "= 65 viên · 2 hộp 5 viên"
    assert chu_ton_ke_don(BangDonVi(), [{"don_vi": "hộp", "ton": 3}]) == "còn 3 hộp"


def test_sap_xep_bo_nhan_chua_gan_va_xep_con_hang_truoc() -> None:
    mau: list[dict[str, Any]] = [
        {"ma": "a", "drug_catalog_id": None, "gia": None},
        {"ma": "b", "drug_catalog_id": "B", "gia": None},
        {"ma": "c", "drug_catalog_id": "C", "gia": 1000},
        {"ma": "d", "drug_catalog_id": "D", "gia": 2000},
    ]
    ton = {"D": [{"don_vi": "hộp", "ton": 1}]}
    bang = {k: BangDonVi(goc="hộp") for k in "BCD"}
    ra = sap_xep_ke_don(mau, ton, bang)
    assert [m["ma"] for m in ra] == ["d", "c", "b"]
    assert [m["chon_duoc"] for m in ra] == [True, True, False]


def _su_kien(loai: str, payload: dict[str, Any]) -> SuKienDaNhan:
    return SuKienDaNhan(
        event_id="e",
        event_type=loai,
        clinic_id="c",
        aggregate_id="a1",
        aggregate_version=None,
        occurred_at=None,
        seq=1,
        actor_type="staff",
        actor_staff_id="s",
        payload=payload,
        replay_id=None,
        attempts=1,
    )


def test_chuong_kho_nho_kho_va_hai_chuong_cu_giu_nguyen() -> None:
    nho = _chuong_kho(_su_kien("pharmacy.drug_requested", {"ten_go": "Pricefil"}))
    assert nho is not None and "Pricefil" in nho[1] and nho[2] == "thuoc_nho_kho"
    han = _chuong_kho(
        _su_kien(
            "pharmacy.expiry_checked",
            {"ngay": "2026-11-26", "sap_het_han": 2, "het_han": 1},
        )
    )
    assert han == (
        "Hạn dùng lô thuốc",
        "2 lô sắp hết hạn; 1 lô đã hết hạn còn tồn.",
        "lo_thuoc_han",
        "2026-11-26",
        "/pharmacy/inventory",
    )
    assert _chuong_kho(_su_kien("result.ready", {})) is None
