"""Agent giám sát — phần hàm thuần (09/10/2026)."""

from __future__ import annotations

from typing import Any

from clinicai.services.agent_giam_sat import (
    LOAI,
    che_do_hieu_luc,
    tu_dieu_phoi,
)


def _khach(**ghi: Any) -> dict[str, Any]:
    p: dict[str, Any] = {
        "visit_id": "v-1",
        "patient_name": "Chị Lan",
        "patient_code": "KH-0901234567",
        "so_tiep_don": 12,
        "current_node_code": "SIEUAM-01",
        "current_node_name": "Siêu âm",
        "room_code": "SA2",
        "wait_minutes": 35,
        "total_minutes": 50,
        "threshold_minutes": 20,
        "trang_thai": {"ma": "DANG_CHO"},
    }
    p.update(ghi)
    return p


def test_cho_qua_nguong_mo_nhan_dinh_khong_lo_ten_khach() -> None:
    ra = tu_dieu_phoi([_khach()], [], location_id="loc-1")
    assert [n.loai for n in ra] == ["khach_cho_qua_nguong"]
    n = ra[0]
    assert n.khoa == "v-1" and n.muc == "warning" and n.location_id == "loc-1"
    assert "số 12" in n.noi_dung and "35 phút" in n.noi_dung
    # Bảng nhận định là đầu vào của LLM về sau: không tên, không mã khách.
    assert "Lan" not in n.noi_dung and "0901234567" not in n.noi_dung
    assert "Lan" not in str(n.bang_chung) and "0901234567" not in str(n.bang_chung)


def test_gap_doi_nguong_la_critical() -> None:
    assert tu_dieu_phoi([_khach(wait_minutes=41)], [])[0].muc == "critical"


def test_dang_lam_hoac_da_goi_thi_khong_phai_cho() -> None:
    for ma in ("DANG_LAM", "DA_GOI", "KHACH_VE", "CHO_KQ_DOI_TAC"):
        assert tu_dieu_phoi([_khach(trang_thai={"ma": ma})], []) == []


def test_chua_xep_buoc() -> None:
    ra = tu_dieu_phoi([_khach(current_node_code=None, wait_minutes=None)], [])
    assert [n.loai for n in ra] == ["khach_chua_xep_buoc"]


def test_phong_qua_tai() -> None:
    phong = {
        "id": "r-1",
        "code": "SA2",
        "name": "Siêu âm 2",
        "state": "critical",
        "waiting": 9,
        "serving": 1,
        "max_wait": 45,
        "threshold_waiting": 8,
        "threshold_minutes": 20,
    }
    ra = tu_dieu_phoi([], [phong, {**phong, "id": "r-2", "state": "ok"}])
    assert [(n.loai, n.khoa, n.muc) for n in ra] == [
        ("phong_qua_tai", "r-1", "critical")
    ]


def test_dong_rac_khong_lam_vo_vong() -> None:
    rac: list[Any] = [
        None,
        "chuỗi",
        {},
        {"visit_id": None},
        _khach(wait_minutes="abc"),
        _khach(wait_minutes=True),
        _khach(threshold_minutes=0, wait_minutes=999),
        _khach(trang_thai="không phải dict"),
    ]
    phong_rac: list[Any] = [None, {"id": None}, {"id": "x", "state": None}]
    ra = tu_dieu_phoi(rac, phong_rac)
    # Số rác (chuỗi, bool) → bỏ; ngưỡng 0 → mặc định 20; nhãn rác → coi như
    # không có nhãn. Còn đúng hai dòng hợp lệ: ngưỡng 0 và nhãn rác.
    assert [(n.loai, n.muc) for n in ra] == [
        ("khach_cho_qua_nguong", "critical"),
        ("khach_cho_qua_nguong", "warning"),
    ]


def test_cong_tac() -> None:
    assert che_do_hieu_luc({}, "khach_lang_im") == "shadow"
    assert che_do_hieu_luc({"khach_lang_im": "tat"}, "khach_lang_im") == "tat"
    assert che_do_hieu_luc({"khach_lang_im": "tat"}, "phong_qua_tai") == "shadow"
    # Công tắc khẩn '*' tắt thắng mọi dòng riêng.
    assert (
        che_do_hieu_luc({"*": "tat", "khach_lang_im": "shadow"}, "khach_lang_im")
        == "tat"
    )


def test_moi_loai_co_ten_va_dung_mau_ten_cot() -> None:
    import re

    for loai, ten in LOAI.items():
        assert re.fullmatch(r"[a-z_]+", loai) and ten
