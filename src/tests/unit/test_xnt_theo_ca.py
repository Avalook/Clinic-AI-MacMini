"""G6 — hàm THUẦN của kiểm kê ca: mốc giờ ca, công thức tồn cuối / lệch, số rác,
ghép khối `kho` vào dòng thuốc của báo cáo hàng hoá."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest

from clinicai.core.clock import CLINIC_TZ
from clinicai.services.kiem_ke_ca_service import (
    ca_cua_gio,
    ghep_ton_ca,
    khung_moc,
    so_hoac_none,
    tinh_xnt_dong,
)

D = Decimal
NGAY = date(2026, 10, 14)


@pytest.mark.parametrize("ca", ["SANG", "CHIEU", "TOI", "sang", " toi "])
def test_khung_moc_ba_ca_khit_nhau_phu_tron_ngay(ca: str) -> None:
    ds = [khung_moc(NGAY, c, None) for c in ("SANG", "CHIEU", "TOI")]
    assert all(k is not None for k in ds)
    assert ds[0][0] == datetime(2026, 10, 14, 0, 0, tzinfo=CLINIC_TZ)  # type: ignore[index]
    # Ca TỐI kết thúc 24:00 = 00:00 hôm sau; ba ca khít nhau không hở không chồng.
    assert ds[2][1] == datetime(2026, 10, 15, 0, 0, tzinfo=CLINIC_TZ)  # type: ignore[index]
    assert ds[0][1] == ds[1][0] and ds[1][1] == ds[2][0]  # type: ignore[index]
    assert khung_moc(NGAY, ca, None) is not None


@pytest.mark.parametrize("ca", [None, "", "KHUYA", 5, "SÁNG"])
def test_khung_moc_ca_rac_thi_none_khong_nem(ca: object) -> None:
    assert khung_moc(NGAY, ca, None) is None


def test_khung_moc_ngay_rac_thi_none() -> None:
    assert khung_moc("2026-10-14", "SANG", None) is None  # type: ignore[arg-type]


def test_ca_cua_gio_ca_toi_qua_nua_dem() -> None:
    assert ca_cua_gio(datetime(2026, 10, 14, 9, 0, tzinfo=CLINIC_TZ), None) == "SANG"
    assert ca_cua_gio(datetime(2026, 10, 14, 15, 0, tzinfo=CLINIC_TZ), None) == "CHIEU"
    assert ca_cua_gio(datetime(2026, 10, 14, 23, 30, tzinfo=CLINIC_TZ), None) == "TOI"


def test_cong_thuc_ton_cuoi_va_lech() -> None:
    t = tinh_xnt_dong(
        ton_dau=D(100), nhap=D(20), ban=D(35), tra=D(2), khac=D(-3), kiem_ke=D(83)
    )
    # 100 + 20 − 35 + 2 − 3 = 84; đếm 83 → lệch −1
    assert t["ton_cuoi"] == D(84) and t["lech"] == D(-1)


def test_chua_kiem_thi_lech_none_khong_suy_ra() -> None:
    t = tinh_xnt_dong(
        ton_dau=D(1), nhap=D(0), ban=D(0), tra=D(0), khac=D(0), kiem_ke=None
    )
    assert t["kiem_ke"] is None and t["lech"] is None


@pytest.mark.parametrize(
    "rac",
    [None, "", "abc", "-1", -3, "nan", "inf", "1e30", float("nan"), True, [], {}],
)
def test_so_dem_rac_thi_none(rac: object) -> None:
    assert so_hoac_none(rac) is None


def test_so_dem_hop_le() -> None:
    assert so_hoac_none("12,5") == D("12.500")
    assert so_hoac_none(0) == D("0.000")
    assert so_hoac_none(" 7 ") == D("7.000")


def _xnt(drug: str, **kw: Decimal) -> dict:  # type: ignore[type-arg]
    base = {
        "drug_catalog_id": drug,
        "don_vi": "viên",
        "don_vi_hien": "viên",
        "ton_dau": D(10),
        "nhap": D(0),
        "ban": D(0),
        "tra": D(0),
        "khac": D(0),
        "ton_cuoi": D(10),
    }
    return {**base, **kw}


def test_ghep_giu_nguyen_so_tien_va_them_khoi_kho() -> None:
    thuoc = {
        "tong": {"doanh_thu": 100},
        "dong": [
            {"khoa": "A", "ten": "A", "sl_ban": 5.0, "doanh_thu": 100, "sl_tra": 0.0}
        ],
    }
    kiem = {
        ("A", "viên", "CUOI"): {"dem": D(8), "phieu_id": "p1", "don_vi_hien": "viên"}
    }
    ghep_ton_ca(
        thuoc,
        [_xnt("A", ban=D(2), ton_cuoi=D(8))],
        kiem,
        {("A", "viên"): D(3)},
        {"A": D(1)},
        {},
    )
    d = thuoc["dong"][0]
    assert d["sl_ban"] == 5.0 and d["doanh_thu"] == 100  # số thu cũ KHÔNG đổi
    kho = d["kho"]["theo_don_vi"][0]
    assert kho["sl_ban"] == 2.0 and kho["ton_cuoi"] == 8.0
    assert kho["kiem_ke"] == 8.0 and kho["lech"] == 0.0
    assert kho["da_thu_chua_giao"] == 3.0 and d["kho"]["giao_chua_gan_lo"] == 1.0
    assert thuoc["co_ton"] is True


def test_thuoc_khong_ban_nhung_co_nhap_van_hien() -> None:
    thuoc: dict = {"tong": {}, "dong": []}  # type: ignore[type-arg]
    ghep_ton_ca(
        thuoc,
        [_xnt("B", nhap=D(5), ton_cuoi=D(15))],
        {},
        {},
        {},
        {"B": {"ten": "Thuốc B", "ma_hang": "TB", "don_vi_ban": "viên"}},
    )
    assert [d["ten"] for d in thuoc["dong"]] == ["Thuốc B"]
    assert thuoc["dong"][0]["doanh_thu"] == 0
    assert thuoc["dong"][0]["kho"]["theo_don_vi"][0]["nhap"] == 5.0
    assert thuoc["dong"][0]["kho"]["theo_don_vi"][0]["lech"] is None


def test_thuoc_khong_chuyen_dong_khong_chen_dong_rong() -> None:
    thuoc: dict = {"tong": {}, "dong": []}  # type: ignore[type-arg]
    ghep_ton_ca(thuoc, [_xnt("C", ton_dau=D(0), ton_cuoi=D(0))], {}, {}, {}, {})
    assert thuoc["dong"] == []


def test_kiem_ke_thuoc_khong_co_chuyen_dong_van_hien() -> None:
    thuoc: dict = {"tong": {}, "dong": []}  # type: ignore[type-arg]
    kiem = {
        ("E", "viên", "CUOI"): {"dem": D(4), "phieu_id": "p", "don_vi_hien": "viên"}
    }
    ghep_ton_ca(thuoc, [], kiem, {}, {}, {"E": {"ten": "E"}})
    k = thuoc["dong"][0]["kho"]["theo_don_vi"][0]
    assert k["kiem_ke"] == 4.0 and k["ton_cuoi"] == 0.0 and k["lech"] == 4.0
