"""Trưởng ca điều phối (Tuyền 29/09/2026) — các hàm thuần máy chủ dùng để quyết
lối đổi phòng, nhãn trạng thái và câu lịch sử. Màn chỉ vẽ theo kết quả này."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from clinicai.services.lenh_kham_core import LuotKhamValidationError
from clinicai.services.lich_su_phong import dong_lich_su
from clinicai.services.nhan_trang_thai_dieu_phoi import (
    trang_thai_dich_vu,
    trang_thai_khach,
)
from clinicai.services.service_routing_service import (
    che_do_doi_phong,
    ly_do_chuyen_phong,
)

LUC = datetime(2026, 9, 29, 3, 15, tzinfo=UTC)


# ── che_do_doi_phong ──────────────────────────────────────────────────────


def _che_do(**kw: Any) -> str:
    mac_dinh: dict[str, Any] = {
        "execution_status": "PENDING",
        "exec_status": "authorized",
        "selection_status": "SELECTED",
        "tai_chinh_xong": True,
        "hang": None,
        "dieu_phoi": False,
        "khach_ve": False,
    }
    return che_do_doi_phong(**{**mac_dinh, **kw})


@pytest.mark.parametrize(
    ("kw", "mong"),
    [
        ({}, "XEP"),
        ({"dieu_phoi": True}, "XEP"),
        # Chưa thu tiền: chỉ trưởng ca có lối phòng dự kiến.
        ({"tai_chinh_xong": False}, "KHONG"),
        ({"tai_chinh_xong": False, "dieu_phoi": True}, "DU_KIEN"),
        ({"selection_status": "PENDING", "dieu_phoi": True}, "DU_KIEN"),
        ({"selection_status": "NOT_SELECTED", "dieu_phoi": True}, "KHONG"),
        # Đang làm: chỉ trưởng ca chuyển.
        ({"execution_status": "IN_PROGRESS"}, "KHONG"),
        ({"execution_status": "IN_PROGRESS", "dieu_phoi": True}, "CHUYEN_DANG_LAM"),
        ({"exec_status": "in_progress", "dieu_phoi": True}, "CHUYEN_DANG_LAM"),
        # Đã gọi vào: không đổi.
        ({"hang": "called", "dieu_phoi": True}, "KHONG"),
        # Xong / huỷ / khách về: chặn với mọi người.
        ({"execution_status": "COMPLETED", "dieu_phoi": True}, "KHONG"),
        ({"exec_status": "performed", "dieu_phoi": True}, "KHONG"),
        ({"exec_status": "cancelled", "dieu_phoi": True}, "KHONG"),
        ({"khach_ve": True, "dieu_phoi": True}, "KHONG"),
        # INTERRUPTED không phải kết thúc — xếp lại là một bước làm lại.
        ({"execution_status": "INTERRUPTED"}, "XEP"),
        # Rác → không đổi được thay vì ném.
        (
            {"execution_status": None, "exec_status": None, "selection_status": None},
            "KHONG",
        ),
    ],
)
def test_che_do_doi_phong(kw: dict[str, Any], mong: str) -> None:
    assert _che_do(**kw) == mong


# ── ly_do_chuyen_phong ────────────────────────────────────────────────────


@pytest.mark.parametrize("rac", [None, "", "   ", "ab", 12, ["máy hỏng"], {"x": 1}])
def test_ly_do_chuyen_rong_hoac_rac_bi_chan(rac: object) -> None:
    with pytest.raises(LuotKhamValidationError) as loi:
        ly_do_chuyen_phong(rac)
    assert loi.value.error_code == "TRANSFER_REASON_REQUIRED"


def test_ly_do_chuyen_gon_khoang_trang_va_gioi_han_do_dai() -> None:
    assert ly_do_chuyen_phong("  máy   hỏng\n đầu dò ") == "máy hỏng đầu dò"
    with pytest.raises(LuotKhamValidationError) as loi:
        ly_do_chuyen_phong("x" * 301)
    assert loi.value.error_code == "TRANSFER_REASON_TOO_LONG"


# ── Nhãn trạng thái dịch vụ ────────────────────────────────────────────────


def _dv(**kw: Any) -> dict[str, Any]:
    mac_dinh: dict[str, Any] = {
        "exec_status": "assigned",
        "execution_status": "PENDING",
        "doi_tac": False,
        "ket_qua_luc": None,
        "xong_luc": None,
        "khach_ve": False,
        "hang": None,
        "vao_hang_luc": None,
        "goi_luc": None,
        "lam_tu": None,
        "so_truoc": None,
        "tai_chinh_xong": True,
    }
    return trang_thai_dich_vu(**{**mac_dinh, **kw})


def test_nhan_dich_vu_dang_cho_co_stt_va_so_nguoi_truoc() -> None:
    t = _dv(hang="waiting", vao_hang_luc=LUC, so_truoc=2)
    assert (t["ma"], t["nhan"], t["stt"], t["so_truoc"]) == (
        "DANG_CHO",
        "Đang chờ",
        3,
        2,
    )
    assert t["tu_luc"] == LUC and t["chuyen_duoc"] is True


@pytest.mark.parametrize(
    ("kw", "ma", "nhan", "chuyen"),
    [
        ({"hang": "called", "goi_luc": LUC}, "DA_GOI", "Đã gọi", False),
        (
            {"execution_status": "IN_PROGRESS", "lam_tu": LUC},
            "DANG_LAM",
            "Đang làm",
            True,
        ),
        ({"hang": "serving"}, "DANG_LAM", "Đang làm", True),
        ({"execution_status": "COMPLETED", "xong_luc": LUC}, "XONG", "Xong", False),
        (
            {"execution_status": "COMPLETED", "doi_tac": True},
            "CHO_KQ_DOI_TAC",
            "Chờ kết quả đối tác",
            False,
        ),
        (
            {"execution_status": "COMPLETED", "doi_tac": True, "ket_qua_luc": LUC},
            "XONG",
            "Xong",
            False,
        ),
        ({"khach_ve": True, "hang": "waiting"}, "KHACH_VE", "Khách về", False),
        ({"tai_chinh_xong": False}, "CHUA_THU", "Chưa thu tiền", False),
        ({}, "CHO_XEP", "Chờ xếp phòng", False),
        ({"execution_status": "INTERRUPTED"}, "DA_DUNG", "Đã dừng giữa chừng", False),
        ({"execution_status": "NOT_PERFORMED"}, "KHONG_LAM", "Không làm", False),
        ({"exec_status": "cancelled"}, "KHONG_LAM", "Đã huỷ", False),
    ],
)
def test_nhan_dich_vu(kw: dict[str, Any], ma: str, nhan: str, chuyen: bool) -> None:
    t = _dv(**kw)
    assert (t["ma"], t["nhan"], t["chuyen_duoc"]) == (ma, nhan, chuyen)
    assert t["stt"] is None  # chỉ "Đang chờ" có số thứ tự


def test_nhan_dich_vu_dau_vao_rac_khong_nem() -> None:
    t = _dv(hang="waiting", vao_hang_luc="10:00", so_truoc="ba")
    assert t["ma"] == "DANG_CHO" and t["tu_luc"] is None and t["stt"] is None
    assert _dv(so_truoc=-1, hang="waiting")["stt"] is None
    assert _dv(so_truoc=True, hang="waiting")["stt"] is None


# ── Nhãn trạng thái khách ──────────────────────────────────────────────────


def _khach(**kw: Any) -> dict[str, Any]:
    mac_dinh: dict[str, Any] = {
        "khach_ve": False,
        "lane": "ROOM",
        "hang": None,
        "vao_hang_luc": None,
        "goi_luc": None,
        "lam_tu": None,
        "so_truoc": None,
        "cho_kq_doi_tac": False,
    }
    return trang_thai_khach(**{**mac_dinh, **kw})


@pytest.mark.parametrize(
    ("kw", "ma", "nhan"),
    [
        ({"hang": "waiting", "so_truoc": 0}, "DANG_CHO", "Đang chờ"),
        ({"hang": "called"}, "DA_GOI", "Đã gọi"),
        ({"hang": "serving"}, "DANG_LAM", "Đang làm"),
        ({"hang": "serving", "lane": "DOCTOR"}, "DANG_LAM", "Đang khám"),
        ({"hang": "serving", "lane": "TU_VAN"}, "DANG_LAM", "Đang khám"),
        ({"hang": "blocked"}, "CHO_BUOC_KHAC", "Chờ bước khác"),
        ({"cho_kq_doi_tac": True}, "CHO_KQ_DOI_TAC", "Chờ kết quả đối tác"),
        ({"khach_ve": True, "hang": "serving"}, "KHACH_VE", "Khách về"),
        ({}, "CHUA_VAO_HANG", "Chưa vào hàng"),
    ],
)
def test_nhan_khach(kw: dict[str, Any], ma: str, nhan: str) -> None:
    t = _khach(**kw)
    assert (t["ma"], t["nhan"]) == (ma, nhan)


def test_nhan_khach_dang_cho_stt() -> None:
    t = _khach(hang="waiting", so_truoc=4, vao_hang_luc=LUC)
    assert t["stt"] == 5 and t["so_truoc"] == 4 and t["tu_luc"] == LUC


# ── Câu lịch sử xếp / đổi phòng ────────────────────────────────────────────

TEN = {"a": "Siêu âm 1", "b": "Siêu âm 2"}


def _ls(loai: str, **p: Any) -> dict[str, Any]:
    return dong_lich_su(loai=loai, payload=p, ten_phong=TEN, luc=LUC, ai="Chị Hà")


def test_lich_su_quay_thu_doi_phong() -> None:
    d = _ls(
        "service.routed",
        from_room_id="a",
        room_id="b",
        nguon="quay_thu",
        ly_do="MANUAL_CORRECTION",
    )
    assert d["cau"] == "Quầy thu đổi phòng Siêu âm 1 → Siêu âm 2"
    assert (d["ten_nguon"], d["tu_phong"], d["den_phong"]) == (
        "Quầy thu",
        "Siêu âm 1",
        "Siêu âm 2",
    )
    assert d["luc"] == LUC and d["ai"] == "Chị Hà"


def test_lich_su_truong_ca_xep_co_ly_do_ma() -> None:
    d = _ls("service.routed", room_id="b", nguon="truong_ca", ly_do="LOAD_BALANCE")
    assert d["cau"] == "Trưởng ca xếp phòng → Siêu âm 2: cân tải"


def test_lich_su_tu_dong_theo_phong_du_kien() -> None:
    d = _ls(
        "service.routed",
        room_id="a",
        tu_dong=True,
        nguon="tu_dong",
        ly_do="INITIAL_ASSIGNMENT",
        du_kien_nguon="truong_ca",
    )
    assert d["cau"] == (
        "Tự động xếp phòng → Siêu âm 1: theo phòng trưởng ca chọn trước khi thu"
    )
    # Sự kiện cũ không có `nguon` mà có tu_dong → vẫn nói "Tự động".
    assert _ls("service.routed", room_id="a", tu_dong=True)["nguon"] == "tu_dong"


def test_lich_su_truong_ca_chuyen_khi_dang_lam() -> None:
    d = _ls(
        "service.room_transferred",
        from_room_id="a",
        room_id="b",
        ly_do="máy hỏng",
        nguon="truong_ca",
    )
    assert (
        d["cau"]
        == "Trưởng ca chuyển phòng khi đang làm Siêu âm 1 → Siêu âm 2: máy hỏng"
    )


def test_lich_su_payload_rac_van_ra_mot_dong() -> None:
    rac: Any = "rac"
    d = dong_lich_su(
        loai="service.routed", payload=rac, ten_phong={}, luc=None, ai=None
    )
    assert d["cau"] == "Nhân viên xếp phòng → —"
    d = _ls("service.routed", from_room_id="zz", room_id="b", nguon="la_hoac")
    assert d["cau"] == "Nhân viên đổi phòng — → Siêu âm 2"
