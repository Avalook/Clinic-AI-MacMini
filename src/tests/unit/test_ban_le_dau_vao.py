"""V8 lượt Bán lẻ: đầu vào người dùng gõ (năm sinh, từ khoá tìm) — rác trả rỗng,
không ném (luật CLAUDE.md) — và báo cáo cuối ngày đếm lượt bán lẻ riêng."""

from __future__ import annotations

from datetime import date

from clinicai.services.ban_le_service import chuan_tu_khoa, nam_sinh
from clinicai.services.bao_cao_cuoi_ngay_service import gom_bao_cao


def test_nam_sinh_rac_thanh_rong() -> None:
    assert [nam_sinh(v) for v in ("1990", 1985, " 2001 ", "abc", None, "", 1800)] == [
        1990,
        1985,
        2001,
        None,
        None,
        None,
        None,
    ]
    assert nam_sinh(True) is None
    assert nam_sinh(["1990"]) is None


def test_tu_khoa_rac_thanh_rong() -> None:
    assert chuan_tu_khoa(None) == ""
    assert chuan_tu_khoa(123) == ""
    assert chuan_tu_khoa("  0912   345 ") == "0912 345"
    assert len(chuan_tu_khoa("x" * 500)) == 100


def test_bao_cao_dem_ban_le_rieng_tien_van_cong() -> None:
    ngay = date(2026, 9, 30)
    bc = gom_bao_cao(
        tu=ngay,
        den=ngay,
        lan_thu=[
            {
                "id": "c1",
                "visit_id": "v1",
                "kind": "dich_vu",
                "status": "PAID",
                "amount": 100_000,
                "method": "CASH",
                "khach_id": "k1",
            },
            {
                "id": "c2",
                "visit_id": "v2",
                "kind": "thuoc",
                "status": "PAID",
                "amount": 30_000,
                "method": "CASH",
                "khach_id": "k2",
                "ban_le": True,
            },
        ],
        hoan=[],
        dong=[],
        doi_tac=[],
        so_luot_kham=1,
    )
    assert bc["tong"]["thuc_thu"] == 130_000
    assert {x["ma"]: x["thu"] for x in bc["theo_loai"]}["thuoc"] == 30_000
    assert bc["khach"]["so_luot_da_thu"] == 1
    assert bc["khach"]["so_luot_ban_le"] == 1
