"""Quầy thu MỘT hoá đơn (27/09/2026) — hàm thuần, không cần DB."""

from __future__ import annotations

from typing import Any

import pytest

from clinicai.services.luot_kham_rules import CHO_THU_LAU_PHUT, cho_thu_lau
from clinicai.services.quay_thu_service import (
    csv_lich_su,
    doc_hinh_thuc,
    doc_tim,
    dung_hoa_don_quay,
    gom_theo_khach,
    loc_khach,
    ma_phieu,
    so_sanh_chi_dinh,
    tim_theo_ma,
    tong_lich_su,
    xep_vang_nhat,
)

# ---------------------------------------------------------------------------
# Phòng: vắng nhất lên đầu
# ---------------------------------------------------------------------------


def test_xep_vang_nhat_len_dau_giu_thu_tu_goi_y_khi_bang() -> None:
    ds = xep_vang_nhat(
        [
            {"id": "a", "ten": "SÂ 1", "dang_cho": 2},
            {"id": "b", "ten": "SÂ 2", "dang_cho": 0},
            {"id": "c", "ten": "SÂ 3", "dang_cho": 0},
        ]
    )
    assert [p["id"] for p in ds] == ["b", "c", "a"]
    assert [p["vang_nhat"] for p in ds] == [True, False, False]


def test_xep_vang_nhat_rong_va_so_rac() -> None:
    assert xep_vang_nhat([]) == []
    ds = xep_vang_nhat([{"id": "x", "dang_cho": "rác"}, {"id": "y", "dang_cho": 1}])
    assert ds[0]["id"] == "x" and ds[0]["vang_nhat"]


# ---------------------------------------------------------------------------
# MỘT hoá đơn
# ---------------------------------------------------------------------------


def _hd(**kw: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "tong": 350_000,
        "revision": "r1",
        "thu_duoc": True,
        "van_de": [],
        "chi_doi_tac_thu": False,
        "dong": [
            {
                "source_type": "exam",
                "source_id": "exam-v",
                "ten": "Khám PK",
                "thanh_tien": 100_000,
                "van_de": None,
            },
            {
                "source_type": "service_order",
                "source_id": "o1",
                "ten": "Soi",
                "thanh_tien": 250_000,
                "van_de": None,
            },
        ],
        "dong_doi_tac": [
            {
                "source_type": "service_order",
                "source_id": "o3",
                "ten": "HPV",
                "thanh_tien": 900_000,
                "doi_tac_da_thu": None,
            },
        ],
    }
    base.update(kw)
    return base


def _cd(id_: str, st: str, gia: int, **kw: Any) -> dict[str, Any]:
    return {"id": id_, "ten": id_.upper(), "selection_status": st, "gia": gia, **kw}


def test_mot_hoa_don_moi_dich_vu_mot_dong() -> None:
    chon = {
        "revision": 3,
        "chi_dinh": [
            _cd(
                "o1",
                "PENDING",
                250_000,
                phong_chon_duoc=[{"id": "r1", "ten": "TT", "dang_cho": 0}],
            ),
            _cd("o2", "NOT_SELECTED", 250_000),
            _cd("o3", "SELECTED", 900_000, doi_tac_thu=True),
            _cd("o4", "SELECTED", 50_000, bat_buoc=True),
        ],
    }
    qt = dung_hoa_don_quay(_hd(), chon)
    ids = [r["id"] for r in qt["phong_kham"]]
    assert ids == ["exam-v", "o1", "o2", "o4"]
    kham, o1, o2, o4 = qt["phong_kham"]
    assert kham["chon"] and not kham["sua_duoc"] and not kham["trong_lua_chon"]
    assert o1["chon"] and o1["sua_duoc"] and o1["can_xep_phong"]
    assert o1["gia"] == 250_000
    assert not o2["chon"] and o2["gia"] == 250_000  # giá bỏ vẫn hiện (gạch)
    assert o4["bat_buoc"] and not o4["sua_duoc"]
    assert [r["id"] for r in qt["doi_tac"]] == ["o3"]
    assert qt["doi_tac"][0]["doi_tac_da_thu"] is None
    # Tổng lấy nguyên hoá đơn máy chủ — không cộng lại.
    assert qt["tong"] == 350_000 and qt["revision"] == "r1"
    assert qt["lua_chon"] == {"revision": 3, "order_ids_seen": ["o1", "o2", "o3", "o4"]}


def test_mot_hoa_don_dong_cu_ngoai_lua_chon_khoa() -> None:
    qt = dung_hoa_don_quay(_hd(), {"revision": 0, "chi_dinh": []})
    o1 = qt["phong_kham"][1]
    assert o1["id"] == "o1" and o1["chon"] and not o1["sua_duoc"]
    assert qt["doi_tac"][0]["id"] == "o3" and not qt["doi_tac"][0]["sua_duoc"]


def test_mot_hoa_don_rong() -> None:
    qt = dung_hoa_don_quay(None, None)
    assert qt["phong_kham"] == [] and qt["doi_tac"] == [] and qt["tong"] == 0
    assert qt["so_sanh"]["so_chi_dinh"] == 0


def test_phu_thu_bam_dich_vu_cha_va_bo_tick_cung_cha() -> None:
    hd = _hd(
        tong=650_000,
        dong=[
            *_hd()["dong"],
            {
                "source_type": "phu_thu",
                "source_id": "pt1",
                "order_id": "o1",
                "ten": "Đầu dò",
                "thanh_tien": 300_000,
                "van_de": None,
            },
        ],
    )
    qt = dung_hoa_don_quay(
        hd,
        {"revision": 3, "chi_dinh": [_cd("o1", "NOT_SELECTED", 250_000)]},
    )
    phu_thu = next(d for d in qt["phong_kham"] if d["loai"] == "phu_thu")
    assert phu_thu["order_id"] == "o1"
    assert phu_thu["chon"] is False


def test_so_sanh_chi_dinh_bo_va_doi_tac() -> None:
    ss = so_sanh_chi_dinh(
        [
            _cd(
                "o1",
                "SELECTED",
                250_000,
                chi_dinh_luc="2026-09-27T06:00:00+00:00",
                bac_si_chi_dinh="BS A",
                lan_chi_dinh=1,
            ),
            _cd(
                "o2",
                "NOT_SELECTED",
                250_000,
                chi_dinh_luc="2026-09-27T06:22:00+00:00",
                bac_si_chi_dinh="BS B",
                lan_chi_dinh=2,
            ),
            _cd("o3", "PENDING", 900_000, doi_tac_thu=True),
            _cd("o4", "NOT_SELECTED", 900_000, doi_tac_thu=True),
        ]
    )
    assert (ss["so_chi_dinh"], ss["so_lam"], ss["so_bo"]) == (4, 2, 2)
    # Dịch vụ đối tác bỏ không trừ tiền quầy.
    assert ss["tien_bo"] == 250_000
    assert [d["khach"] for d in ss["dong"]] == ["lam", "khong", "doi_tac", "khong"]
    assert (ss["bac_si"], ss["lan"]) == ("BS B", 2)


def test_so_sanh_du_nhu_chi_dinh_va_gia_rac() -> None:
    ss = so_sanh_chi_dinh([_cd("o1", "SELECTED", 0), {"id": "o2", "gia": "rác"}])
    assert ss["so_bo"] == 0 and ss["tien_bo"] == 0
    assert ss["dong"][1]["tien"] is None and ss["bac_si"] is None


# ---------------------------------------------------------------------------
# Mã phiếu + bộ lọc (rác → bỏ qua)
# ---------------------------------------------------------------------------


def test_ma_phieu() -> None:
    uid = "3f2a1b9c-0000-4000-8000-000000000000"
    assert ma_phieu(uid) == "PT-3F2A1B9C"
    assert ma_phieu(uid, "hoan") == "PH-3F2A1B9C"
    assert ma_phieu(None) == "" and ma_phieu("") == ""


@pytest.mark.parametrize(
    ("vao", "ra"),
    [
        ("PT-3F2A", "3f2a"),
        (" ph-3f2a1b9c ", "3f2a1b9c"),
        ("pt3f2a", "3f2a"),
        ("Nguyễn", None),
        ("PT-", None),
        ("", None),
    ],
)
def test_tim_theo_ma(vao: str, ra: str | None) -> None:
    assert tim_theo_ma(vao) == ra


@pytest.mark.parametrize(
    ("vao", "ra"),
    [
        ("cash", "CASH"),
        (" QR ", "QR"),
        ("TRANSFER", "TRANSFER"),
        ("the", None),
        ("", None),
        (None, None),
        (3, None),
    ],
)
def test_doc_hinh_thuc(vao: Any, ra: str | None) -> None:
    assert doc_hinh_thuc(vao) == ra


def test_doc_tim() -> None:
    assert doc_tim("  Lê   Mai ") == "Lê Mai"
    assert doc_tim(None) == "" and doc_tim(123) == ""
    assert len(doc_tim("x" * 500)) == 80


def test_nguong_cho_thu_lau() -> None:
    assert not cho_thu_lau(None)
    assert not cho_thu_lau(CHO_THU_LAU_PHUT - 1)
    assert cho_thu_lau(CHO_THU_LAU_PHUT)


# ---------------------------------------------------------------------------
# Lịch sử gom theo khách
# ---------------------------------------------------------------------------

C1 = "11111111-0000-4000-8000-000000000001"
C2 = "22222222-0000-4000-8000-000000000002"
R1 = "33333333-0000-4000-8000-000000000003"


def _so_mau() -> list[dict[str, Any]]:
    lan_thu = [
        {
            "id": C1,
            "visit_id": "v1",
            "status": "PAID",
            "amount": 600_000,
            "method": "QR",
            "paid_at": "2026-09-27T11:05:00+00:00",
            "nguoi_thu": "Thu ngân Mai",
        },
        {
            "id": C2,
            "visit_id": "v2",
            "status": "VOIDED",
            "amount": 200_000,
            "method": "CASH",
            "paid_at": "2026-09-27T10:00:00+00:00",
            "closed_at": "2026-09-27T10:30:00+00:00",
            "close_reason": "thu nhầm",
            "nguoi_thu": "Lễ tân Lan",
            "nguoi_huy": "QL",
        },
    ]
    hoan = [
        {
            "refund_id": R1,
            "visit_id": "v1",
            "amount": 300_000,
            "status": "COMPLETED",
            "method": "CASH",
            "reason": "khách không làm",
            "created_at": "2026-09-27T11:10:00+00:00",
            "nguoi": "QL",
            "dich_vu": ["Siêu âm thai"],
        },
    ]
    khach = {
        "v1": {
            "ten": "Vũ Hồng Quyên",
            "ma_bn": "BN-1",
            "so_booking": 9,
            "so_tiep_don": 8,
        },
        "v2": {"ten": "Lê Mai", "ma_bn": "BN-2", "so_booking": 8, "so_tiep_don": 7},
    }
    dong = {
        C1: [
            {
                "id": "b1",
                "source_id": "o1",
                "ten": "Khám Sản",
                "so_luong": 1,
                "thanh_tien": 300_000,
            },
            {
                "id": "b2",
                "source_id": "o2",
                "ten": "Siêu âm thai",
                "so_luong": 1,
                "thanh_tien": 300_000,
            },
        ]
    }
    return gom_theo_khach(lan_thu, hoan, khach, dong)


def test_gom_theo_khach_co_hoan_va_huy() -> None:
    ds = _so_mau()
    assert [g["visit_id"] for g in ds] == ["v1", "v2"]  # mới nhất lên đầu
    v1, v2 = ds
    assert (v1["tong_goc"], v1["tong_hoan"], v1["con_lai"]) == (
        600_000,
        300_000,
        300_000,
    )
    assert v1["co_hoan"] and v1["so_phieu"] == 1 and v1["ma_phieu_dau"] == "PT-11111111"
    assert [s["loai"] for s in v1["su_kien"]] == ["thu", "hoan"]
    assert v1["su_kien"][1]["so_tien"] == -300_000
    assert v1["su_kien"][0]["dich_vu"] == ["Khám Sản", "Siêu âm thai"]
    assert v1["phieu"][0]["dong"][0]["thanh_tien"] == 300_000
    # Phiếu đã huỷ: gốc vẫn tính, hoàn/huỷ trừ hết.
    assert (v2["tong_goc"], v2["con_lai"]) == (200_000, 0)
    assert [s["loai"] for s in v2["su_kien"]] == ["thu", "huy"]


def test_tong_lich_su() -> None:
    t = tong_lich_su(_so_mau())
    assert t == {
        "tong_thu": 800_000,
        "tien_mat": 200_000,
        "chuyen_khoan": 0,
        "qr": 600_000,
        "hoan": 500_000,
    }


def test_hoan_cho_chuyen_khong_tru() -> None:
    ds = gom_theo_khach(
        [],
        [
            {
                "refund_id": R1,
                "visit_id": "v1",
                "amount": 100_000,
                "status": "PENDING",
                "method": "TRANSFER",
                "reason": "chờ",
                "created_at": "2026-09-27T11:10:00+00:00",
            }
        ],
        {},
        {},
    )
    assert ds[0]["tong_hoan"] == 0 and ds[0]["su_kien"][0]["cho"]
    assert tong_lich_su(ds)["hoan"] == 0


def test_loc_khach() -> None:
    ds = _so_mau()
    assert [g["visit_id"] for g in loc_khach(ds, tim="quyên")] == ["v1"]
    assert [g["visit_id"] for g in loc_khach(ds, tim="BN-2")] == ["v2"]
    assert [g["visit_id"] for g in loc_khach(ds, tim="pt-2222")] == ["v2"]
    assert [g["visit_id"] for g in loc_khach(ds, tim="PH-3333")] == ["v1"]
    assert [g["visit_id"] for g in loc_khach(ds, hinh_thuc="QR")] == ["v1"]
    assert [g["visit_id"] for g in loc_khach(ds, nguoi_thu="Lễ tân Lan")] == ["v2"]
    assert loc_khach(ds, tim="không ai") == []


def test_csv_co_bom_va_chan_cong_thuc() -> None:
    ds = _so_mau()
    ds[0]["ten"] = "=HYPERLINK(1)"
    out = csv_lich_su(ds)
    assert out.startswith("﻿Ngày giờ,Loại,Mã phiếu")
    dong = out.strip().split("\r\n")
    assert len(dong) == 1 + 4  # tiêu đề + thu/hoàn (v1) + thu/huỷ (v2)
    assert "'=HYPERLINK(1)" in out
    assert "Huỷ phiếu" in out and "-300000" in out
    assert "27/09/2026 18:05" in out  # giờ VN
