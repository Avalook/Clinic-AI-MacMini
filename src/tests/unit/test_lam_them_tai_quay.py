"""Làm thêm tại quầy (01/10/2026) — phần thuần: đọc đầu vào rác, trạng thái nút,
nhãn trên hành trình / quầy thu."""

from __future__ import annotations

from typing import Any

import pytest

from clinicai.services.bang_hanh_trinh_service import con_cho
from clinicai.services.lam_them_tai_quay_service import (
    _doc_ma_luot,
    doc_noi,
    nhan_lam_them,
    trang_thai_nut,
)
from clinicai.services.quay_thu_service import so_sanh_chi_dinh

V1 = "11111111-1111-4111-8111-111111111111"
V2 = "22222222-2222-4222-8222-222222222222"


@pytest.mark.parametrize(
    "vao,ra",
    [
        ("tiep_don", "tiep_don"),
        (" sinh_hieu ", "sinh_hieu"),
        ("phong", None),
        ("", None),
        (None, None),
        (42, None),
        (["tiep_don"], None),
    ],
)
def test_doc_noi_rac_tra_rong_khong_nem(vao: Any, ra: str | None) -> None:
    assert doc_noi(vao) == ra


def test_doc_ma_luot_bo_rac_bo_trung() -> None:
    assert _doc_ma_luot(f"{V1},rac,{V2},{V1}, ,") == [V1, V2]
    assert _doc_ma_luot([V2, "x", None]) == [V2]
    assert _doc_ma_luot(None) == []
    assert _doc_ma_luot(123) == []


def test_nhan_lam_them() -> None:
    assert nhan_lam_them("tiep_don") == "Làm thêm tại quầy tiếp đón"
    assert nhan_lam_them("sinh_hieu") == "Làm thêm tại bàn sinh hiệu"
    assert nhan_lam_them(None) is None
    assert nhan_lam_them("") is None


def _o(**kw: Any) -> dict[str, Any]:
    goc = {
        "id": "o1",
        "nguon_lam_them": "tiep_don",
        "selection_status": "SELECTED",
        "execution_status": "PENDING",
        "exec_status": "authorized",
        "phong": None,
        "da_thu": False,
        "version": 1,
    }
    goc.update(kw)
    return goc


def test_trang_thai_nut() -> None:
    assert trang_thai_nut(None) == {
        "chon": False,
        "doi_duoc": True,
        "order_id": None,
        "order_version": None,
        "state_revision": 0,
        "ghi_chu": None,
    }
    # Tick ở quầy, chưa làm, chưa thu → bỏ được.
    tt = trang_thai_nut(_o())
    assert tt["chon"] and tt["doi_duoc"]
    # Khách bỏ ở quầy thu → nút về chưa tick, tick lại được.
    tt = trang_thai_nut(_o(selection_status="NOT_SELECTED"))
    assert not tt["chon"] and tt["doi_duoc"]
    # Đang làm → không bỏ được, nói ở phòng nào.
    tt = trang_thai_nut(
        _o(execution_status="IN_PROGRESS", exec_status="in_progress", phong="Lấy mẫu")
    )
    assert tt["chon"] and not tt["doi_duoc"]
    assert tt["ghi_chu"] == "đang làm ở Lấy mẫu"
    # Đã thu → bỏ ở quầy thu.
    tt = trang_thai_nut(_o(da_thu=True))
    assert tt["chon"] and not tt["doi_duoc"] and "quầy thu" in tt["ghi_chu"]
    # Bác sĩ đã chỉ định → quầy không chồng thêm, không bỏ hộ.
    tt = trang_thai_nut(_o(nguon_lam_them=None))
    assert tt == {
        "chon": True,
        "doi_duoc": False,
        "order_id": "o1",
        "order_version": 1,
        "state_revision": 0,
        "ghi_chu": "bác sĩ đã chỉ định",
    }


@pytest.mark.parametrize(
    "execution_status,exec_status,ghi_chu",
    [
        ("COMPLETED", "performed", "đã làm xong"),
        ("NOT_PERFORMED", "not_performed", "đã ghi không làm"),
    ],
)
def test_dich_vu_da_ket_thuc_van_hien_da_tick_va_khong_tao_lai(
    execution_status: str, exec_status: str, ghi_chu: str
) -> None:
    tt = trang_thai_nut(
        _o(execution_status=execution_status, exec_status=exec_status, version=4)
    )
    assert tt == {
        "chon": True,
        "doi_duoc": False,
        "order_id": "o1",
        "order_version": 4,
        "state_revision": 0,
        "ghi_chu": ghi_chu,
    }


def test_con_cho_ghi_ro_lam_them_tai_quay() -> None:
    ds = con_cho(
        [],
        [
            {
                "ten": "Tổng phân tích nước tiểu",
                "selection_status": "SELECTED",
                "execution_status": "PENDING",
                "routing_status": "UNASSIGNED",
                "da_tra": False,
                "duoc_lam": False,
                "nguon_lam_them": "sinh_hieu",
            }
        ],
        0,
    )
    assert ds == ["Chờ trả tiền: Tổng phân tích nước tiểu (làm thêm tại quầy)"]


def test_so_sanh_chi_dinh_chan_bang_la_lan_cua_bac_si() -> None:
    kq = so_sanh_chi_dinh(
        [
            {
                "id": "a",
                "ten": "Siêu âm",
                "selection_status": "SELECTED",
                "gia": 300000,
                "bac_si_chi_dinh": "BS Lan",
                "lan_chi_dinh": 1,
                "chi_dinh_luc": "2026-10-01T09:00:00+07:00",
            },
            {
                "id": "b",
                "ten": "Nước tiểu",
                "selection_status": "SELECTED",
                "gia": 50000,
                "bac_si_chi_dinh": None,
                "nguoi_bam_chi_dinh": "Lễ tân Hoa",
                "lam_them": "Làm thêm tại quầy tiếp đón",
                "chi_dinh_luc": "2026-10-01T09:30:00+07:00",
            },
        ]
    )
    assert kq["so_chi_dinh"] == 2
    assert kq["bac_si"] == "BS Lan" and kq["lan"] == 1
    assert kq["dong"][1]["lam_them"] == "Làm thêm tại quầy tiếp đón"
