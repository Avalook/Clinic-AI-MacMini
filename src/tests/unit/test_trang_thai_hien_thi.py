"""Nhãn trạng thái lịch / lượt — MỘT hàm cho mọi màn (Tuyền 30/09/2026: "đã
checkout rồi nhưng ở mấy trang chủ hay trang lịch hẹn khám vẫn ghi là đang
khám")."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from clinicai.core.trang_thai_lich import trang_thai_hien_thi

VE = datetime(2026, 9, 30, 4, 20, tzinfo=UTC)  # 11:20 giờ Việt Nam


@pytest.mark.parametrize(
    ("lich", "ma", "nhan"),
    [
        ("CONFIRMED", "DA_DAT", "Đã đặt lịch"),
        ("SCHEDULED", "CHUA_XAC_NHAN", "Chưa xác nhận"),
        ("CANCELLED", "HUY", "Đã huỷ"),
        ("NO_SHOW", "KHONG_DEN", "Không đến"),
        ("DOCTOR_DECLINED", "BS_TU_CHOI", "Bác sĩ từ chối"),
    ],
)
def test_lich_chua_toi_hoac_da_chet_theo_lich(lich: str, ma: str, nhan: str) -> None:
    tt = trang_thai_hien_thi(lich=lich)
    assert (tt["ma"], tt["nhan"]) == (ma, nhan)


def test_hoan_tac_check_in_lich_thang_luot_dang_do() -> None:
    """Hoàn tác check-in: lịch về CONFIRMED, lượt INCOMPLETE — khách CHƯA đến."""
    tt = trang_thai_hien_thi(lich="CONFIRMED", luot="INCOMPLETE")
    assert tt["ma"] == "DA_DAT"


@pytest.mark.parametrize("lich", ["CHECKED_IN", "COMPLETED", None])
def test_da_check_out_luon_la_da_ve(lich: str | None) -> None:
    tt = trang_thai_hien_thi(
        lich=lich,
        luot="IN_PROGRESS",
        ve_luc=VE,
        kham_xong=False,
        dang_o={"trang_thai": "DANG_O", "noi": "Phòng 3"},
    )
    assert tt == {"ma": "DA_VE", "nhan": "Đã về 11:20", "tone": "neutral"}


def test_ve_giua_chung() -> None:
    tt = trang_thai_hien_thi(lich="COMPLETED", luot="INCOMPLETE", ve_luc=VE)
    assert (tt["ma"], tt["nhan"]) == ("VE_GIUA_CHUNG", "Về giữa chừng 11:20")


def test_kham_xong_chua_check_out() -> None:
    assert (
        trang_thai_hien_thi(lich="CHECKED_IN", luot="IN_PROGRESS", kham_xong=True)["ma"]
        == "KHAM_XONG"
    )
    assert trang_thai_hien_thi(lich="CHECKED_IN", luot="FINALIZED")["ma"] == "KHAM_XONG"
    assert (
        trang_thai_hien_thi(lich="COMPLETED", luot="IN_PROGRESS")["ma"] == "KHAM_XONG"
    )


def test_con_o_phong_kham_noi_dang_o_dau() -> None:
    o = trang_thai_hien_thi(
        lich="CHECKED_IN",
        luot="IN_PROGRESS",
        dang_o={"trang_thai": "DANG_O", "noi": "Phòng thủ thuật 1"},
    )
    assert (o["ma"], o["nhan"]) == ("DANG_O", "Đang ở: Phòng thủ thuật 1")
    cho = trang_thai_hien_thi(
        lich="CHECKED_IN",
        luot="OPEN",
        dang_o={"trang_thai": "DANG_CHO", "noi": "Bàn tư vấn"},
    )
    assert (cho["ma"], cho["nhan"]) == ("DANG_CHO", "Đang chờ: Bàn tư vấn")
    tho = trang_thai_hien_thi(lich="CHECKED_IN", luot="OPEN")
    assert (tho["ma"], tho["nhan"]) == ("DA_CHECK_IN", "Đã check-in")


def test_da_thu_du() -> None:
    assert (
        trang_thai_hien_thi(lich="CHECKED_IN", luot="OPEN", da_thu_du=True)["ma"]
        == "DA_THU_DU"
    )


@pytest.mark.parametrize("rac", ["", "   ", "2026-13-99", 12345, object()])
def test_dau_vao_rac_khong_nem(rac: object) -> None:
    """Luật CLAUDE.md: hàm nhận ngày giờ trả rỗng thay vì ném."""
    tt = trang_thai_hien_thi(lich="CHECKED_IN", luot="IN_PROGRESS", ve_luc=rac)
    assert tt["ma"] in ("DA_VE", "DA_CHECK_IN")
    assert trang_thai_hien_thi(lich=None)["ma"] == "KHAC"
    assert trang_thai_hien_thi(lich="LA_LAM")["nhan"] == "LA_LAM"
