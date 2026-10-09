"""Khối 1 theo loại lượt + ô "Làm trước – thu sau" tại chỗ (Tuyền 09/10/2026).

Hàm thuần: `che_do_khoi1` (khối 1 vẽ gì), `nhac_tick` (ô tick chỉ hiện khi
FinanceGate đang chặn vì chưa thu và chưa tick), `mo_ban_kham` (link ở Sắp đến
cho lượt Thủ thuật chưa có chỉ định ở phòng thủ thuật).
"""

from __future__ import annotations

from typing import Any

import pytest

from clinicai.phieu_kham.che_do import (
    KHOI1_DIEU_TRI,
    KHOI1_THU_THUAT,
    che_do_khoi1,
)
from clinicai.services import finance_gate as fg
from clinicai.services import nhan_tai_phong as ntp
from clinicai.services.lam_truoc_thu_sau import nhac_tick

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


# ---------------------------------------------------------------- ô tick


def _moi(
    state: str | None,
    *,
    duoc_chua_thu: bool = False,
    chon: str | None = "SELECTED",
    lam: str | None = "PENDING",
) -> bool:
    return nhac_tick(
        state,
        selection_status=chon,
        execution_status=lam,
        duoc_chua_thu=duoc_chua_thu,
    )


def test_ca1_khong_qua_bac_si_chinh_chua_thu_chua_tick_thi_hien() -> None:
    # Điều trị / Thủ thuật đi thẳng: chưa ai tick, chưa thu, dây bật.
    assert _moi(fg.DUE) is True
    # Khách chưa chốt ở quầy: tick = chốt luôn → vẫn mời.
    assert _moi(fg.NOT_APPLICABLE, chon="PENDING") is True


def test_ca2_bac_si_chinh_da_tick_thi_khong_hien() -> None:
    # Tick ở MỨC LƯỢT → `duoc_chua_thu` True cho mọi chỉ định của lượt.
    assert _moi(fg.DUE, duoc_chua_thu=True) is False
    assert _moi(fg.NOT_APPLICABLE, chon="PENDING", duoc_chua_thu=True) is False


def test_ca3_qua_bac_si_chinh_quen_tick_chua_thu_thi_hien() -> None:
    assert _moi(fg.DUE) is True
    assert _moi(fg.FINANCIAL_DATA_INCOMPLETE) is True  # thiếu giá: tick mở được


@pytest.mark.parametrize(
    "state",
    [
        fg.PAID,  # đã thu
        fg.NOT_REQUIRED,  # không cần qua cửa tiền
        fg.PARTNER_COLLECTS,  # đối tác thu
        fg.PENDING_VERIFICATION,  # CK chờ xác minh — cửa đã mở
        fg.REFUND_PENDING,  # đang hoàn: tick cũng không mở được
        fg.REFUNDED,
        fg.FINANCIAL_REVIEW_REQUIRED,
        None,  # chưa có trạng thái tiền
        "RÁC",
    ],
)
def test_khong_hien_khi_cua_tien_khong_chan_vi_chua_thu(state: str | None) -> None:
    assert _moi(state) is False


def test_khong_hien_khi_day_thu_truoc_tat() -> None:
    # Dây tắt → `duoc_chua_thu` True (cua_lam DUE mở).
    assert _moi(fg.DUE, duoc_chua_thu=True) is False


def test_khong_hien_khi_khach_bo_hoac_da_bat_dau() -> None:
    assert _moi(fg.NOT_APPLICABLE, chon="NOT_SELECTED") is False
    for lam in ("IN_PROGRESS", "COMPLETED", "INTERRUPTED", "NOT_PERFORMED"):
        assert _moi(fg.DUE, lam=lam) is False
    assert _moi(fg.DUE, lam=None) is True  # cột mới chưa có = chưa làm


def test_cung_luat_voi_cua_lam() -> None:
    """Mời tick ⇔ cửa đóng khi chưa tick VÀ mở khi tick (dây bật)."""
    for s in (*fg.CHO_LAM_STATES, fg.REFUNDED, fg.FINANCIAL_REVIEW_REQUIRED):
        ky_vong = not fg.cua_lam(
            s, thu_truoc_khi_lam=True, lam_truoc_thu_sau=False
        ) and fg.cua_lam(s, thu_truoc_khi_lam=True, lam_truoc_thu_sau=True)
        assert _moi(s) is ky_vong, s


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
