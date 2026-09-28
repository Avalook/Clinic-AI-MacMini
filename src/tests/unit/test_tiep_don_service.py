"""Danh sách tiếp đón (27/09/2026, đợt 3) — hàm thuần: trễ, buổi, chip trạng thái."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from clinicai.core.shifts import CA_MAC_DINH
from clinicai.services.tiep_don_service import (
    buoi_cua,
    dung_dong,
    gom_theo_buoi,
    loai_khach,
    nhan_buoi,
    phut_tre,
    trang_thai,
)

VN = timezone(timedelta(hours=7))


def _luc(gio: int, phut: int = 0) -> datetime:
    return datetime(2026, 9, 27, gio, phut, tzinfo=VN)


def _tt(**kw: Any) -> dict[str, str]:
    base: dict[str, Any] = {
        "lich_status": "CONFIRMED",
        "vang_lai": False,
        "gio_hen": _luc(8, 30),
        "khung_phut": 15,
        "check_in": None,
        "visit_status": None,
        "ve_luc": None,
        "vitals_status": None,
        "vitals_tu_luot_truoc": False,
        "hang": [],
        "bay_gio": _luc(8, 55),
    }
    base.update(kw)
    return trang_thai(**base)


# --- phut_tre ---------------------------------------------------------------
def test_phut_tre_chi_tinh_khi_qua_het_khung() -> None:
    hen = _luc(8, 30)
    assert phut_tre(hen, _luc(8, 44), 15) is None  # còn trong khung
    assert phut_tre(hen, _luc(8, 45), 15) == 15
    assert phut_tre(hen, _luc(8, 55), 15) == 25
    # Khung 30 phút: 25 phút sau giờ hẹn vẫn chưa trễ.
    assert phut_tre(hen, _luc(8, 55), 30) is None


def test_phut_tre_vang_lai_va_dau_vao_rac() -> None:
    hen = _luc(8, 30)
    assert phut_tre(hen, _luc(10, 0), 15, vang_lai=True) is None
    assert phut_tre(None, _luc(10, 0), 15) is None
    assert phut_tre("08:30", _luc(10, 0), 15) is None
    assert phut_tre(hen, "10:00", 15) is None
    assert phut_tre(hen, _luc(10, 0), None) is None  # không có mặc định
    assert phut_tre(hen, _luc(10, 0), 0) is None
    assert phut_tre(hen, _luc(10, 0), -5) is None
    assert phut_tre(hen, _luc(10, 0), "15") is None
    assert phut_tre(hen, _luc(10, 0), True) is None
    assert phut_tre(hen, datetime(2026, 9, 27, 10, 0), 15) is None  # lệch múi giờ


# --- buoi -------------------------------------------------------------------
def test_buoi_theo_gio_ca_va_khoang_nghi_trua() -> None:
    ca = dict(CA_MAC_DINH)  # sáng 8–13, chiều 14–17:30, tối 17:30–21:30
    assert buoi_cua(_luc(7, 30), ca) == "SANG"  # sớm hơn ca đầu
    assert buoi_cua(_luc(12, 59), ca) == "SANG"
    assert buoi_cua(_luc(13, 15), ca) == "CHIEU"  # nghỉ trưa → ca sau
    assert buoi_cua(_luc(17, 30), ca) == "TOI"  # nửa mở
    assert buoi_cua(_luc(22, 0), ca) == "TOI"  # muộn hơn ca cuối
    # Mốc UTC vẫn đổi sang giờ VN trước khi so.
    assert buoi_cua(datetime(2026, 9, 27, 2, 0, tzinfo=timezone.utc), ca) == "SANG"


def test_buoi_dau_vao_rac() -> None:
    assert buoi_cua(None, CA_MAC_DINH) is None
    assert buoi_cua("08:00", CA_MAC_DINH) is None
    assert buoi_cua(datetime(2026, 9, 27, 8, 0), CA_MAC_DINH) is None
    assert buoi_cua(_luc(8), {}) is None
    assert buoi_cua(_luc(8), None) is None


def test_nhan_buoi() -> None:
    assert nhan_buoi("SANG", CA_MAC_DINH) == "Sáng · 08:00 – 13:00"
    assert nhan_buoi("CHIEU", {}) == "Chiều"


# --- loai khách ---------------------------------------------------------------
def test_loai_khach() -> None:
    assert loai_khach("WALK_IN", "Khám lần đầu") == "vãng lai"
    assert loai_khach("walk_in", "Tái khám") == "vãng lai"
    assert loai_khach("HOTLINE", "Khám lần đầu") == "khám mới"
    assert loai_khach("ONLINE", "Tái khám") == "tái khám"
    assert loai_khach(None, "") is None
    assert loai_khach(123, None) is None


# --- chip trạng thái ------------------------------------------------------------
def test_chua_den_va_tre() -> None:
    assert _tt(bay_gio=_luc(8, 40)) == {
        "loai": "cho",
        "nhan": "Chưa đến",
        "nhom": "chua_den",
    }
    assert _tt() == {"loai": "tre", "nhan": "Trễ 25′", "nhom": "chua_den"}
    assert _tt(vang_lai=True)["loai"] == "cho"
    assert _tt(lich_status="NO_SHOW")["nhom"] == "khac"


def test_da_check_in_buoc_tiep() -> None:
    ci = _luc(8, 2)
    assert _tt(check_in=ci, vitals_status="pending")["nhan"] == (
        "Đã check-in 08:02 · chờ đo"
    )
    # Đã đo ở lượt trước cùng buổi → không "chờ đo" nữa, nói hàng đang chờ.
    hang = [{"lane": "TU_VAN", "status": "waiting", "phong": None, "bac_si": None}]
    r = _tt(check_in=ci, vitals_status="pending", vitals_tu_luot_truoc=True, hang=hang)
    assert r == {
        "loai": "den",
        "nhan": "Đã check-in 08:02 · chờ bác sĩ tư vấn",
        "nhom": "da_den",
    }
    doi = [{"lane": "ROOM", "status": "blocked", "phong": "Siêu âm", "bac_si": None}]
    assert _tt(check_in=ci, vitals_status="recorded", hang=doi)["nhan"].endswith(
        "· đợi Siêu âm"
    )
    assert _tt(check_in=ci, vitals_status="recorded")["nhan"] == "Đã check-in 08:02"


def test_dang_o_va_da_ve() -> None:
    ci = _luc(8, 2)
    hang = [{"lane": "DOCTOR", "status": "serving", "phong": None, "bac_si": "An"}]
    assert _tt(check_in=ci, hang=hang) == {
        "loai": "dang_o",
        "nhan": "Đang ở: bác sĩ An",
        "nhom": "da_den",
    }
    assert _tt(check_in=ci, vitals_status="in_progress")["nhan"] == (
        "Đang ở: đo sinh hiệu"
    )
    assert _tt(check_in=ci, ve_luc=_luc(10, 12))["nhan"] == "Đã về 10:12"
    assert _tt(check_in=ci, visit_status="INCOMPLETE", ve_luc=_luc(9, 0))["nhan"] == (
        "Về giữa chừng 09:00"
    )
    # Đã về thắng mọi thứ, kể cả hàng chờ còn sót.
    assert _tt(check_in=ci, ve_luc=_luc(10, 12), hang=hang)["loai"] == "ve"


def test_trang_thai_dau_vao_rac_khong_nem() -> None:
    assert _tt(gio_hen="rác", khung_phut="x", bay_gio=None)["loai"] == "cho"
    assert _tt(check_in=_luc(8), hang=[None, "x", 3])["loai"] == "den"
    assert _tt(lich_status="CHECKED_IN")["nhan"] == "Đã check-in"


# --- dựng dòng + gom buổi ---------------------------------------------------------
def _hang_db(**kw: Any) -> dict[str, Any]:
    r: dict[str, Any] = {
        "appointment_id": "a",
        "status": "CONFIRMED",
        "booking_channel": "HOTLINE",
        "slot_start": _luc(8, 30),
        "so_booking": 5,
        "so_tiep_don": None,
        "full_name": "Chị A",
        "patient_code": "BN-1",
        "phone_primary": "0900",
        "phan_loai": "Khám lần đầu",
        "slot_minutes": 15,
    }
    r.update(kw)
    return r


def test_dung_dong_nut_theo_trang_thai() -> None:
    d = dung_dong(_hang_db(), [], _luc(8, 40))
    assert d["check_in_duoc"] is True and d["check_out_duoc"] is False
    assert d["gio_hen"] == "08:30" and d["loai_khach"] == "khám mới"
    d = dung_dong(
        _hang_db(status="CHECKED_IN", visit_id="v", checked_in_at=_luc(8, 31)),
        [],
        _luc(8, 40),
    )
    assert d["check_in_duoc"] is False and d["check_out_duoc"] is True
    d = dung_dong(
        _hang_db(visit_id="v", checked_in_at=_luc(8, 31), ve_luc=_luc(9)),
        [],
        _luc(9, 5),
    )
    assert d["check_out_duoc"] is False


def test_gom_theo_buoi_vang_lai_theo_gio_check_in() -> None:
    now = _luc(15)
    dong = [
        dung_dong(
            _hang_db(appointment_id="c", slot_start=_luc(14), so_booking=9), [], now
        ),
        dung_dong(
            _hang_db(appointment_id="b", slot_start=_luc(9), so_booking=2), [], now
        ),
        # Vãng lai tạo lịch 11:00 nhưng check-in 13:40 → buổi CHIỀU, trước 14:00.
        dung_dong(
            _hang_db(
                appointment_id="w",
                booking_channel="WALK_IN",
                slot_start=_luc(11),
                visit_id="v",
                checked_in_at=_luc(13, 40),
            ),
            [],
            now,
        ),
        dung_dong(_hang_db(appointment_id="r", slot_start="rác"), [], now),
    ]
    nhom = gom_theo_buoi(dong, CA_MAC_DINH)
    assert [n["ma"] for n in nhom] == ["SANG", "CHIEU"]
    assert [d["appointment_id"] for d in nhom[0]["dong"]] == ["b", "r"]
    assert [d["appointment_id"] for d in nhom[1]["dong"]] == ["w", "c"]
    assert all("moc_xep" not in d for n in nhom for d in n["dong"])
    assert gom_theo_buoi([], CA_MAC_DINH) == []


def test_gom_theo_buoi_nguoi_da_den_theo_gio_check_in_that() -> None:
    """Tuyền 29/09: B hẹn 18:00 ngồi chờ từ 17:40; lễ tân tạo A khung 18:00 và
    A tự check-in 17:50; C hẹn 18:00 tới 18:10; D hẹn 18:15 chưa tới.
    Thứ tự thật B → A → C → D (bản cũ: A → B → C → D vì B, C theo giờ hẹn)."""
    now = _luc(18, 12)
    dong = [
        dung_dong(
            _hang_db(
                appointment_id=ma,
                booking_channel=kenh,
                slot_start=hen,
                visit_id=f"v{ma}" if ci else None,
                status="CHECKED_IN" if ci else "CONFIRMED",
                checked_in_at=ci,
                so_booking=so,
            ),
            [],
            now,
        )
        for ma, kenh, hen, ci, so in (
            ("d", "ONLINE", _luc(18, 15), None, 1),
            ("c", "ONLINE", _luc(18), _luc(18, 10), 2),
            ("a", "WALK_IN", _luc(18), _luc(17, 50), 3),
            ("b", "HOTLINE", _luc(18), _luc(17, 40), 4),
        )
    ]
    nhom = gom_theo_buoi(dong, CA_MAC_DINH)
    assert [n["ma"] for n in nhom] == ["TOI"]
    assert [d["appointment_id"] for d in nhom[0]["dong"]] == ["b", "a", "c", "d"]
    assert all("moc_buoi" not in d for d in nhom[0]["dong"])


def test_gom_theo_buoi_keo_tay_thang_gio_check_in() -> None:
    """Mốc lễ tân kéo tay thay giờ check-in — cùng luật bảng gọi số."""
    now = _luc(9)
    som = dung_dong(
        _hang_db(appointment_id="som", visit_id="v1", checked_in_at=_luc(8, 10)),
        [],
        now,
    )
    keo = dung_dong(
        _hang_db(
            appointment_id="keo",
            visit_id="v2",
            checked_in_at=_luc(8, 20),
            thu_tu_tay_ms=_luc(8, 5).timestamp() * 1000,
        ),
        [],
        now,
    )
    [buoi] = gom_theo_buoi([som, keo], CA_MAC_DINH)
    assert [d["appointment_id"] for d in buoi["dong"]] == ["keo", "som"]


def test_moc_keo_tay_rac_khong_nem() -> None:
    """Mốc kéo tay hỏng (NaN, quá lớn) → rơi về giờ check-in, không 500."""
    for rac in (float("nan"), 1e30, float("inf")):
        d = dung_dong(
            _hang_db(visit_id="v", checked_in_at=_luc(8, 10), thu_tu_tay_ms=rac),
            [],
            _luc(9),
        )
        [buoi] = gom_theo_buoi([d], CA_MAC_DINH)
        assert [x["appointment_id"] for x in buoi["dong"]] == ["a"]
