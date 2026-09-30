"""Phòng làm theo dịch vụ (30/09/2026) — các hàm thuần.

Luật trong DB: test_phong_lam_theo_dich_vu_db.py.
"""

from __future__ import annotations

from typing import Any

from clinicai.services.clinic_config_service import (
    gom_thieu_phong,
    gom_viec_chon_duoc,
    la_nhom_chon_duoc,
)
from clinicai.services.service_routing_service import (
    KHOA_NOI_BO,
    cau_phong_khong_lam,
    phong_lam_duoc_sql,
)


def test_cau_tu_choi_neu_ten_phong_duoc_gan() -> None:
    assert cau_phong_khong_lam("Ghế điện từ trường", ["Phòng Sàn chậu"]) == (
        "Phòng này không làm dịch vụ Ghế điện từ trường — dịch vụ chỉ làm ở:"
        " Phòng Sàn chậu."
    )
    assert cau_phong_khong_lam("X", ["A", "B"]).endswith("chỉ làm ở: A, B.")


def test_cau_tu_choi_dich_vu_khong_thu_hep_va_ten_rac() -> None:
    assert cau_phong_khong_lam("Siêu âm", []) == "Phòng này không làm dịch vụ Siêu âm."
    for rac in (None, "", "   ", 12):
        assert cau_phong_khong_lam(rac, []) == "Phòng này không làm dịch vụ này."  # type: ignore[arg-type]


def test_mau_sql_chi_goi_mot_ham() -> None:
    assert phong_lam_duoc_sql("pr", "o") == (
        "phong_lam_duoc(pr.clinic_id, pr.id, o.node_code, o.service_code)"
    )
    assert {"node_code", "service_code"} == KHOA_NOI_BO


def test_chi_moi_nhom_kham_va_nhom_dich_vu() -> None:
    assert la_nhom_chon_duoc("KHAM-PHUKHOA")
    assert la_nhom_chon_duoc("DICHVU-THUTHUAT")
    for quan_tri in (
        "DATLICH-06",
        "NGUONLUC-01",
        "OPS-FINANCIAL-RESOLUTION",
        "LUOTKHAM-13",
        "THUOC-01",
        "",
        None,
        5,
    ):
        assert not la_nhom_chon_duoc(quan_tri)


def test_danh_sach_chon_duoc_bo_node_quan_tri_va_nhom_rong() -> None:
    nodes = [
        {"code": "DATLICH-06", "name": "Huỷ lịch"},
        {"code": "DICHVU-DUYET-KETQUA", "name": "Duyệt kết quả"},
        {"code": "DICHVU-THUTHUAT", "name": "Thủ thuật"},
        {"code": "KHAM-PHUKHOA", "name": "Khám Phụ khoa"},
        {"code": "LUOTKHAM-14", "name": "Thanh toán"},
    ]
    dv: list[dict[str, Any]] = [
        {
            "ma": "CLS_GHE_DTT",
            "ten": "Ghế điện từ trường",
            "ma_kv": "SP000158",
            "node": "DICHVU-THUTHUAT",
            "chi_lam_o": ["Phòng Sàn chậu"],
        },
        {"ma": "KV_A", "ten": "Đặt vòng", "ma_kv": None, "node": "DICHVU-THUTHUAT"},
    ]
    ds = gom_viec_chon_duoc(nodes, dv)
    assert [g["node"] for g in ds] == ["KHAM-PHUKHOA", "DICHVU-THUTHUAT"]
    assert ds[0]["loai"] == "KHAM" and ds[0]["dich_vu"] == []
    tt = ds[1]
    assert [d["ten"] for d in tt["dich_vu"]] == ["Ghế điện từ trường", "Đặt vòng"]
    assert tt["dich_vu"][0]["chi_lam_o"] == ["Phòng Sàn chậu"]
    assert tt["dich_vu"][1]["chi_lam_o"] == []


def test_canh_bao_gom_ca_nhom_hoac_tung_dich_vu() -> None:
    dv = [
        {
            "ma": "A1",
            "ten": "Siêu âm A",
            "node": "DICHVU-SIEUAM",
            "ten_nhom": "SA",
            "thieu": False,
        },
        {
            "ma": "A2",
            "ten": "Siêu âm B",
            "node": "DICHVU-SIEUAM",
            "ten_nhom": "SA",
            "thieu": True,
        },
        {
            "ma": "D1",
            "ten": "DXA",
            "node": "DICHVU-DXA",
            "ten_nhom": "Đo DXA",
            "thieu": True,
        },
    ]
    out = gom_thieu_phong([{"code": "KHAM-NAMKHOA", "name": "Khám Nam khoa"}], dv)
    assert [(t["code"], t["name"]) for t in out] == [
        ("KHAM-NAMKHOA", "Khám Nam khoa"),
        ("DICHVU-DXA", "Đo DXA"),
        ("A2", "Siêu âm B"),
    ]
    assert all(t["loi"] == "CONFIG_MISSING" for t in out)
    assert gom_thieu_phong([], []) == []
