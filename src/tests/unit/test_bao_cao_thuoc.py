"""Thuốc kê vs thực bán + khung chốt ca — hàm thuần, không DB (08/10/2026)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from clinicai.core.clock import CLINIC_TZ
from clinicai.core.shifts import CAC_CA, khung_chot_ca
from clinicai.services.bao_cao_cuoi_ngay_service import khung_ca
from clinicai.services.bao_cao_thuoc_service import gom_thuoc_theo_khach, so_ke

LUC = datetime(2026, 10, 8, 9, 30, tzinfo=CLINIC_TZ)


def _don(id_: str, **kw: object) -> dict[str, object]:
    d: dict[str, object] = {
        "id": id_,
        "visit_id": "v1",
        "nguon": "BAC_SI",
        "drug_name_raw": "Utrogestan",
        "unit": "viên",
        "quantity_num": Decimal(10),
        "ke_goc_num": None,
        "quay_sua": False,
        "purchased_qty": None,
        "dispensed_qty": Decimal(0),
        "refusal_reason": None,
        "removed_at": None,
        "created_at": LUC,
        "ten_kho": None,
        "gia_kho": Decimal(25000),
        "don_vi_ban": "viên",
    }
    d.update(kw)
    return d


def _bill(id_: str, rx: str, so: int, gia: int, ten: str | None) -> dict[str, object]:
    return {
        "id": id_,
        "source_id": rx,
        "quantity": Decimal(so),
        "unit": "viên",
        "unit_price": Decimal(gia),
        "line_total": Decimal(so * gia),
        "ten_kho": ten,
        "paid_at": LUC,
        "nguoi_thu": "Thu ngân A",
    }


KHACH = [{"visit_id": "v1", "ten_khach": "Chị B", "ma_bn": "BN1", "luc": LUC}]


def test_so_ke_giu_so_bac_si_khi_quay_sua() -> None:
    assert so_ke(_don("a")) == 10
    # Quầy sửa 10 → 6: số kê vẫn là số gốc của bác sĩ.
    assert so_ke(_don("a", quay_sua=True, quantity_num=6, ke_goc_num=10)) == 10
    # Bác sĩ để trống, quầy điền: không có số kê để so.
    assert so_ke(_don("a", quay_sua=True, quantity_num=6, ke_goc_num=None)) is None
    assert so_ke(_don("a", nguon="QUAY", quantity_num=3)) == 0
    assert so_ke(_don("a", quantity_num="rác")) is None


def test_doi_thuoc_sua_so_tra_hang_va_khong_lay() -> None:
    kq = gom_thuoc_theo_khach(
        khach=KHACH,
        don=[
            # Bác sĩ ghi "Utrogestan", quầy chọn thuốc kho khác, bán 6 thay vì 10.
            _don(
                "r1",
                ten_kho="Filrosy (progesteron 200mg)",
                quay_sua=True,
                quantity_num=Decimal(6),
                ke_goc_num=Decimal(10),
            ),
            # Khách không lấy.
            _don("r2", drug_name_raw="Duphaston", purchased_qty=Decimal(0)),
            # Quầy bán thêm.
            _don("r3", nguon="QUAY", drug_name_raw="Aspilet", quantity_num=2),
            # Dòng đã đính chính, chưa từng bán → không hiện.
            _don("r4", removed_at=LUC),
        ],
        bill=[
            _bill("b1", "r1", 6, 25000, "Filrosy (progesteron 200mg)"),
            _bill("b3", "r3", 2, 1000, "Aspilet"),
        ],
        hoan=[{"bill_line_id": "b1", "quantity": Decimal(1), "amount": Decimal(25000)}],
    )
    k = kq["khach"][0]
    dong = {d["id"]: d for d in k["dong"]}
    assert set(dong) == {"r1", "r2", "r3"}
    r1 = dong["r1"]
    assert (r1["ten"], r1["ten_bac_si"]) == (
        "Filrosy (progesteron 200mg)",
        "Utrogestan",
    )
    assert (r1["so_ke"], r1["so_ban"], r1["so_tra"], r1["thuc_ban"], r1["chenh"]) == (
        10,
        6,
        1,
        5,
        -5,
    )
    assert r1["thanh_tien"] == 125000 and r1["lech"]
    assert (dong["r2"]["trang_thai"], dong["r2"]["chenh"]) == ("khong_lay", -10)
    assert (dong["r3"]["so_ke"], dong["r3"]["chenh"], dong["r3"]["lech"]) == (
        0,
        2,
        True,
    )
    assert k["tien"] == 125000 + 2000 and k["so_lech"] == 3
    assert k["nguoi_thu"] == ["Thu ngân A"]
    assert kq["tong"] == {
        "so_khach": 1,
        "so_khach_lech": 1,
        "so_dong_lech": 3,
        "tien": 127000,
    }
    th = {t["ten"]: t for t in kq["tieu_hao"]}
    assert set(th) == {"Filrosy (progesteron 200mg)", "Aspilet"}  # không lấy → không
    assert (th["Filrosy (progesteron 200mg)"]["thuc_ban"], th["Aspilet"]["tien"]) == (
        5,
        2000,
    )


def test_khop_ke_khong_lech_va_khach_khong_co_dong_bi_bo() -> None:
    kq = gom_thuoc_theo_khach(
        khach=[*KHACH, {"visit_id": "v2", "ten_khach": "Không đơn"}],
        don=[_don("r1", ten_kho="Utrogestan")],
        bill=[_bill("b1", "r1", 10, 25000, "Utrogestan")],
        hoan=[],
    )
    assert [k["visit_id"] for k in kq["khach"]] == ["v1"]
    d = kq["khach"][0]["dong"][0]
    assert (d["chenh"], d["lech"], d["ten_bac_si"]) == (0, False, None)
    assert kq["tong"]["so_khach_lech"] == 0


def test_ba_ca_chot_khit_nhau_phu_ca_ngay() -> None:
    w = [khung_chot_ca(m) for m in CAC_CA]
    assert w == [(0, 14 * 60), (14 * 60, 17 * 60 + 30), (17 * 60 + 30, 24 * 60)]
    # Nghỉ trưa 13:30 thuộc ca SÁNG (ca trước khe), như ca_cua_phut.
    assert w[0] is not None and w[0][0] <= 13 * 60 + 30 < w[0][1]
    assert khung_chot_ca("ĐÊM") is None


def test_khung_ca_rac_tra_none_khong_nem() -> None:
    ngay = date(2026, 10, 8)
    for rac in (None, "", "dem", 123, "SANG; DROP"):
        assert khung_ca(ngay, rac, None) is None
    tu, den, nhan = khung_ca(ngay, "chieu", "{rác json") or (None, None, None)
    assert tu == datetime(2026, 10, 8, 14, 0, tzinfo=CLINIC_TZ)
    assert den == datetime(2026, 10, 8, 17, 30, tzinfo=CLINIC_TZ)
    assert nhan == {"ma": "CHIEU", "ten": "Chiều", "tu": "14:00", "den": "17:30"}
