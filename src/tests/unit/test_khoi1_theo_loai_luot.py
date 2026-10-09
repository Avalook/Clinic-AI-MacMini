"""Khối 1 theo loại lượt + ô "Làm trước – thu sau" tại chỗ (Tuyền 09/10/2026).

Hàm thuần: `che_do_khoi1` (khối 1 vẽ gì), `mo_ban_kham` (link ở Sắp đến cho
lượt Thủ thuật chưa có chỉ định ở phòng thủ thuật). Cờ mời tick (`nhac_tick`)
dùng `service_execution_service.chan_vi_chua_thu` của E1 — unit test ở
`test_cua_tien_chot_ho.py`, ba ca Tuyền chốt ở `test_nhac_tick_phong_db.py`.
"""

from __future__ import annotations

from typing import Any

import pytest

from clinicai.phieu_kham.che_do import (
    KHOI1_DIEU_TRI,
    KHOI1_THU_THUAT,
    che_do_khoi1,
)
from clinicai.services import nhan_tai_phong as ntp

# ---------------------------------------------------------------- khối 1


@pytest.mark.parametrize(
    ("nhom", "form_code", "ra"),
    [
        ("DIEU_TRI", None, KHOI1_DIEU_TRI),  # 6 loại DT_*
        ("DIEU_TRI", "THU_THUAT", KHOI1_DIEU_TRI),  # nhóm thắng
        ("KHAM", "THU_THUAT", KHOI1_THU_THUAT),
        ("KHAM", "PK", None),  # Phụ khoa — phiếu riêng, như cũ
        ("KHAM", "SAN_CHAU", None),  # Sàn chậu chuyên sâu — như khám thường
        ("KHAC", None, None),
        (None, None, None),  # lượt không loại khám
        (123, ["rác"], None),  # rác → như cũ, không ném
    ],
)
def test_che_do_khoi1(nhom: Any, form_code: Any, ra: str | None) -> None:
    assert che_do_khoi1(nhom, form_code) == ra


# ---------------------------------------------------------------- Sắp đến

PHONG = "phong-thu-thuat"


def _khach(**them: Any) -> dict[str, Any]:
    k: dict[str, Any] = {
        "visit_id": "v1",
        "full_name": "Khách v1",
        "patient_code": "v1",
        "so_tiep_don": None,
        "so_booking": None,
        "q_lane": None,
        "q_status": None,
        "q_room_id": None,
        "q_phong": None,
        "nhom_kham": "KHAM",
        "phieu_kham": "THU_THUAT",
        "phong_thu_thuat": True,
        "da_qua_ban_kham": False,
        "con_viec": 0,
    }
    k.update(them)
    return k


def test_luot_thu_thuat_chua_chi_dinh_o_phong_thu_thuat_co_link_mo_ban_kham() -> None:
    [o] = ntp.gom_sap_den([_khach()], [], PHONG)
    assert o["mo_ban_kham"] == f"/ban-kham/{PHONG}"
    assert o["dang_o"] == ntp.CAU_CHUA_CO_CHI_DINH


def test_khong_link_khi_da_co_chi_dinh_hoac_khong_phai_luot_thu_thuat() -> None:
    r = {"visit_id": "v1", "room_id": PHONG, "o_room_id": None, "accepting": True}
    c = {
        "trang_thai": ntp.SAP_DEN,
        "nhan_duoc": True,
        "chuyen": False,
        "huong_dan_day": False,
    }
    [o] = ntp.gom_sap_den([_khach()], [(r, c)], PHONG)
    assert o["mo_ban_kham"] is None
    for k in (
        _khach(phieu_kham="PK"),
        _khach(nhom_kham="DIEU_TRI"),
        _khach(phong_thu_thuat=False),  # phòng không làm thủ thuật
    ):
        [o] = ntp.gom_sap_den([k], [], PHONG)
        assert o["mo_ban_kham"] is None
    # Dòng cũ không có hai cột mới (bảng ngày cũ / test cũ): không ném.
    k = _khach()
    del k["phieu_kham"], k["phong_thu_thuat"]
    assert ntp.gom_sap_den([k], [], PHONG)[0]["mo_ban_kham"] is None
