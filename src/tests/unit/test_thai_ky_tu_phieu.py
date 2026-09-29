"""Hai ô thai kỳ của phiếu Sản khoa v5 → thai kỳ (HÀM THUẦN, 29/09/2026).

Luật CLAUDE.md: hàm nhận ngày người dùng gõ trả rỗng thay vì ném, có test rác.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from clinicai.phieu_kham.doc_chu import chu_o, noi_dung_phieu
from clinicai.services.thai_ky_service import (
    NGAY_THAI_KY,
    doc_ngay_tu_do,
    thai_ky_tu_phieu,
)

HOM_NAY = date(2026, 9, 29)


@pytest.mark.parametrize(
    ("raw", "ra"),
    [
        ("2026-08-04", date(2026, 8, 4)),
        ("4/8/2026", date(2026, 8, 4)),
        ("04/08/2026", date(2026, 8, 4)),
        ("04-08-2026", date(2026, 8, 4)),
        ("04.08.2026", date(2026, 8, 4)),
        (" 4 / 8 / 26 ", date(2026, 8, 4)),
    ],
)
def test_doc_ngay_tu_do_nhan_cac_kieu_go(raw: str, ra: date) -> None:
    assert doc_ngay_tu_do(raw) == ra


@pytest.mark.parametrize(
    "rac",
    [
        None,
        "",
        "   ",
        "hôm qua",
        "32/13/2026",
        "31/02/2026",
        "2026-02-30",
        "12/08",
        "08/2026",
        "1/1/20260",
        12,
        ["2026-08-04"],
        {"gia_tri": "2026-08-04"},
    ],
)
def test_doc_ngay_tu_do_rac_thanh_none_khong_nem(rac: object) -> None:
    assert doc_ngay_tu_do(rac) is None


def test_chi_co_kinh_cuoi_thi_du_kien_sinh_cong_280_ngay() -> None:
    lmp = HOM_NAY - timedelta(days=56)
    tk = thai_ky_tu_phieu(lmp.strftime("%d/%m/%Y"), "", HOM_NAY)
    assert tk == {
        "lmp": lmp,
        "edd": lmp + timedelta(days=NGAY_THAI_KY),
        "nguon": "KY_KINH_CUOI",
        "edd_tu_tinh": True,
    }


def test_du_kien_sinh_go_tay_giu_nguyen_nguon_khac() -> None:
    lmp = HOM_NAY - timedelta(days=56)
    edd = lmp + timedelta(days=NGAY_THAI_KY + 5)
    tk = thai_ky_tu_phieu(lmp.isoformat(), edd.isoformat(), HOM_NAY)
    assert tk is not None
    assert tk["edd"] == edd and tk["nguon"] == "KHAC" and not tk["edd_tu_tinh"]
    # Khớp kinh cuối + 280 → nguồn "Kỳ kinh cuối".
    edd2 = lmp + timedelta(days=NGAY_THAI_KY)
    tk2 = thai_ky_tu_phieu(lmp.isoformat(), edd2.isoformat(), HOM_NAY)
    assert tk2 is not None and tk2["nguon"] == "KY_KINH_CUOI"
    # Chỉ dự kiến sinh.
    tk3 = thai_ky_tu_phieu(None, edd.isoformat(), HOM_NAY)
    assert tk3 is not None and tk3["lmp"] is None and tk3["nguon"] == "KHAC"


def test_kinh_cuoi_rac_du_kien_sinh_dung_van_dung_du_kien_sinh() -> None:
    edd = HOM_NAY + timedelta(days=200)
    tk = thai_ky_tu_phieu("không nhớ", edd.isoformat(), HOM_NAY)
    assert tk is not None and tk["lmp"] is None and tk["edd"] == edd


@pytest.mark.parametrize(
    ("lmp", "edd"),
    [
        (None, None),
        ("", ""),
        ("rác", "rác"),
        # Kinh cuối ở tương lai → tuổi thai âm.
        ((HOM_NAY + timedelta(days=3)).isoformat(), None),
        # Hơn 300 ngày trước → không phải thai đang theo dõi.
        ((HOM_NAY - timedelta(days=301)).isoformat(), None),
        # Dự kiến sinh không sau kinh cuối.
        ("2026-08-04", "2026-08-04"),
        ("2026-08-04", "2026-07-01"),
    ],
)
def test_khong_dung_duoc_thi_bo_qua(lmp: str | None, edd: str | None) -> None:
    assert thai_ky_tu_phieu(lmp, edd, HOM_NAY) is None


# ── Phiếu v5 → chữ (hồ sơ CSKH, lượt khám trước) ────────────────────────────

KHUNG = [
    {
        "ma": "B",
        "ten": "B. Khám",
        "block": [
            {"ma": "sk_edd", "ten": "Dự kiến sinh", "kieu": "ngay"},
            {
                "ma": "sk_reason",
                "ten": "Lý do khám",
                "kieu": "nhieu_chon",
                "lua_chon": [
                    {"ma": "sk_reason_1", "ten": "Khám thai"},
                    {"ma": "sk_reason_2", "ten": "Ra máu"},
                ],
            },
            {
                "ma": "sk_allergy_co",
                "ten": "Dị ứng thuốc",
                "kieu": "chon",
                "lua_chon": [{"ma": "sk_allergy_co_1", "ten": "Có"}],
            },
            {"ma": "sk_note", "ten": "Ghi chú", "kieu": "doan_van"},
        ],
    },
    {"ma": "C", "ten": "C. Chỉ định", "block": []},
]


def test_noi_dung_phieu_dich_theo_khung_bo_o_trong() -> None:
    du_lieu = {
        "sk_edd": {"gia_tri": "2027-05-11", "nguon": "USER"},
        "sk_reason": {"gia_tri": ["sk_reason_2", "sk_reason_1"], "nguon": "USER"},
        "sk_allergy_co": {"gia_tri": "sk_allergy_co_1", "nguon": "USER"},
        "sk_note": {"gia_tri": "   ", "nguon": "USER"},
    }
    assert noi_dung_phieu(KHUNG, du_lieu) == [
        {
            "ten": "B. Khám",
            "dong": [
                {"ma": "sk_edd", "nhan": "Dự kiến sinh", "chu": "11/05/2027"},
                {"ma": "sk_reason", "nhan": "Lý do khám", "chu": "Ra máu, Khám thai"},
                {"ma": "sk_allergy_co", "nhan": "Dị ứng thuốc", "chu": "Có"},
            ],
        }
    ]


@pytest.mark.parametrize("rac", [None, "", "không phải json", [], 3, {"x": 1}])
def test_noi_dung_phieu_rac_khong_nem(rac: object) -> None:
    assert noi_dung_phieu(rac, {"sk_note": {"gia_tri": "a"}}) == []
    assert noi_dung_phieu(KHUNG, rac) == []


def test_chu_o_ngay_rac_giu_nguyen_chu() -> None:
    o = {"ma": "d", "ten": "Ngày", "kieu": "ngay"}
    assert chu_o(o, {"gia_tri": "11/05/2027"}) == "11/05/2027"
    assert chu_o(o, {"gia_tri": ""}) is None
    assert chu_o(o, "không phải ô") is None
