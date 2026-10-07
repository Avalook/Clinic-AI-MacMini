"""Hành trình khách xếp theo GIỜ THẬT + nhãn "Nhận vào phòng" + lượt Điều trị
không qua bàn khám (Tuyền bấm staging 07/10/2026) — hàm thuần, không cần DB.

Lượt thật (Khách 0126, đặt lịch Laser): Nhận vào Thủ thuật ngoài giờ 15:35:01
→ làm xong 15:35:49 → bác sĩ bấm Bắt đầu khám 15:36:00 → check-out 15:36:34.
Màn cũ xếp theo khuôn nên "Khám bác sĩ chính (15:36)" đứng TRƯỚC "Làm dịch vụ
(15:35)".
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from clinicai.events.consumers.dong_thoi_gian import _nhan_rieng
from clinicai.services.audit_labels import action_label_theo_nguon
from clinicai.services.hanh_trinh_khach_service import (
    dung_hanh_trinh_khach,
    xep_theo_gio,
)
from clinicai.services.lich_su_phong import dong_lich_su

VN = timezone(timedelta(hours=7))
BS = "11111111-1111-4111-8111-111111111111"


def g(h: int, m: int, s: int = 0) -> datetime:
    return datetime(2026, 10, 7, h, m, s, tzinfo=VN)


def _laser(xong: bool = True) -> dict[str, Any]:
    return {
        "id": "cd-laser",
        "ten": "Laser trẻ hoá tiền đình",
        "lan": 1,
        "tao_luc": g(15, 30),
        "chon": True,
        "da_tra": True,
        "xong": xong,
        "phong": "Thủ thuật ngoài giờ",
        "ngoai": False,
        "tra_luc": g(15, 30),
        "bat_dau_luc": g(15, 35, 1),
        "dang_lam": not xong,
        "xong_luc": g(15, 35, 49) if xong else None,
        "doi_tac_thu": False,
        "doi_tac_da_thu": False,
        "execution_status": "COMPLETED" if xong else "IN_PROGRESS",
        "lam_xong_luc": g(15, 35, 49) if xong else None,
    }


def _luot(
    *,
    nhom: str | None,
    bac_si_bat_dau: bool,
    ve: bool,
    xong: bool = True,
) -> dict[str, Any]:
    su_kien: list[tuple[str, datetime, dict[str, Any]]] = [
        ("service.started", g(15, 35, 1), {}),
    ]
    if xong:
        su_kien.append(("service.completed", g(15, 35, 49), {}))
    phien: list[dict[str, Any]] = []
    if bac_si_bat_dau:
        su_kien.append(("consultation.started", g(15, 36), {"loai": "PRIMARY"}))
        phien.append(
            {
                "kind": "PRIMARY",
                "status": "in_progress",
                "started_at": g(15, 36),
                "completed_at": None,
                "bac_si": "BS Nam",
                "doctor_staff_id": BS,
            }
        )
    return dung_hanh_trinh_khach(
        luot={
            "visit_id": "v-0126",
            "status": "COMPLETED" if ve else "IN_PROGRESS",
            "checked_in_at": g(15, 34),
            "closed_at": g(15, 36, 34) if ve else None,
            "dat_luc": None,
            "nhom_loai_kham": nhom,
        },
        su_kien=su_kien,
        chi_dinh=[_laser(xong)],
        hang=[],
        phien=phien,
    )


def _ma(kq: dict[str, Any]) -> list[str]:
    return [b["ma"] for b in kq["buoc"]]


def _buoc(kq: dict[str, Any], ma: str) -> dict[str, Any]:
    return next(b for b in kq["buoc"] if b["ma"] == ma)


# ── 1. Thứ tự theo giờ thật ────────────────────────────────────────────────


def test_luot_laser_lam_dich_vu_truoc_kham_bac_si_theo_gio() -> None:
    kq = _luot(nhom="DIEU_TRI", bac_si_bat_dau=True, ve=True)
    ma = _ma(kq)
    # Đã xảy ra theo giờ: check-in 15:34 → làm DV 15:35 → khám 15:36; bước
    # không làm (sinh hiệu, quay lại BS) sau, theo khuôn; Check-out cuối.
    assert ma == ["CHECK_IN", "LAM_DV", "KHAM", "SINH_HIEU", "DOC_KQ", "CHECK_OUT"]
    assert _buoc(kq, "LAM_DV")["bat_dau"] == g(15, 35, 1)
    assert _buoc(kq, "KHAM")["bat_dau"] == g(15, 36)
    # Thanh đoạn dòng gọn đọc thẳng dòng thời gian — cùng thứ tự.
    assert kq["gon"]["doan"] == [b["trang_thai"] for b in kq["buoc"]]


def test_buoi_thuong_van_dung_thu_tu_khuon() -> None:
    """Lượt khám thường (khám trước, làm dịch vụ sau) — thứ tự không đổi."""
    buoc: list[dict[str, Any]] = [
        {"ma": "CHECK_IN", "bat_dau": g(9, 0), "xong": g(9, 0)},
        {"ma": "SINH_HIEU", "bat_dau": g(9, 5), "xong": g(9, 8)},
        {"ma": "KHAM", "bat_dau": g(9, 10), "xong": g(9, 20)},
        {"ma": "LAM_DV", "bat_dau": g(9, 25), "xong": None},
        {"ma": "DOC_KQ", "bat_dau": None, "xong": None},
        {"ma": "THUOC", "bat_dau": None, "xong": None},
        {"ma": "CHECK_OUT", "bat_dau": None, "xong": None},
    ]
    assert [b["ma"] for b in xep_theo_gio(buoc)] == [b["ma"] for b in buoc]


def test_xep_theo_gio_trung_gio_giu_khuon_va_gio_rac_khong_nem() -> None:
    buoc: list[dict[str, Any]] = [
        {"ma": "CHECK_IN", "bat_dau": g(9, 0)},
        {"ma": "SINH_HIEU", "bat_dau": "rác", "xong": g(9, 30)},
        {"ma": "KHAM", "bat_dau": g(9, 10)},
        {"ma": "LAM_DV", "bat_dau": g(9, 10)},
        {"ma": "THUOC"},
        {"ma": "CHECK_OUT", "bat_dau": g(9, 40)},
    ]
    assert [b["ma"] for b in xep_theo_gio(buoc)] == [
        "CHECK_IN",
        "KHAM",
        "LAM_DV",
        "SINH_HIEU",  # giờ bắt đầu rác → lấy giờ xong 9:30
        "THUOC",
        "CHECK_OUT",
    ]
    assert xep_theo_gio([]) == []


# ── 3. Lượt Điều trị / Khác không qua bàn khám ─────────────────────────────


def test_dieu_tri_khong_qua_ban_kham_khong_treo_quay_lai_bac_si() -> None:
    kq = _luot(nhom="DIEU_TRI", bac_si_bat_dau=False, ve=False)
    assert "DOC_KQ" not in _ma(kq)
    kham = _buoc(kq, "KHAM")
    assert kham["tuy_chon"] is True
    assert kham["trang_thai"] == "chua"
    # "Tiếp theo" không mời khách sang bàn khám tuỳ chọn.
    assert all(t["noi"] != kham["noi"] for t in kq["tiep_theo"])


def test_nhom_khac_cung_khong_qua_ban_kham() -> None:
    kq = _luot(nhom="KHAC", bac_si_bat_dau=False, ve=True)
    assert "DOC_KQ" not in _ma(kq)
    assert _buoc(kq, "KHAM")["tuy_chon"] is True


def test_da_qua_ban_kham_hoac_nhom_kham_giu_luat_cu() -> None:
    # Bác sĩ đã bấm Bắt đầu khám → luật cũ: có bước quay lại bác sĩ.
    kq = _luot(nhom="DIEU_TRI", bac_si_bat_dau=True, ve=False)
    assert "DOC_KQ" in _ma(kq)
    assert _buoc(kq, "KHAM")["tuy_chon"] is False
    # Loại KHÁM (hoặc DB chưa có cột nhóm → None): như cũ.
    for nhom in ("KHAM", None):
        kq = _luot(nhom=nhom, bac_si_bat_dau=False, ve=False)
        doc = _buoc(kq, "DOC_KQ")
        assert doc["ghi_chu"] == "đọc kết quả, khi dịch vụ xong"
        assert _buoc(kq, "KHAM")["tuy_chon"] is False


# ── 2. Nhãn "Nhận vào phòng" ───────────────────────────────────────────────


def test_nhan_tai_phong_la_nhan_vao_phong() -> None:
    phong = {"r1": "Thủ thuật ngoài giờ", "r0": "Phòng siêu âm 1"}

    def cau(**p: Any) -> str:
        return str(
            dong_lich_su(
                loai="service.routed",
                payload=p,
                ten_phong=phong,
                luc=None,
                ai=None,
            )["cau"]
        )

    nhan = "Nhận vào phòng · Thủ thuật ngoài giờ"
    assert cau(room_id="r1", nguon="tai_phong") == nhan
    assert cau(room_id="r1", from_room_id="r0", nguon="tai_phong") == nhan
    # Nguồn khác giữ "xếp phòng".
    assert cau(room_id="r1", nguon="quay_thu") == (
        "Quầy thu xếp phòng → Thủ thuật ngoài giờ"
    )
    assert cau(room_id="r1") == "Nhân viên xếp phòng → Thủ thuật ngoài giờ"


def test_nhan_dong_thoi_gian_va_nhat_ky() -> None:
    assert _nhan_rieng("service.routed", {"nguon": "tai_phong"}) == "Nhận vào phòng"
    assert _nhan_rieng("service.routed", {"nguon": "truong_ca"}) is None
    assert action_label_theo_nguon("service.routed", "tai_phong") == "Nhận vào phòng"
    assert action_label_theo_nguon("service.routed", None) == (
        "Xếp phòng chính thức cho dịch vụ"
    )
    assert action_label_theo_nguon("service.started", "tai_phong") == (
        "Người thực hiện nhận khách làm dịch vụ"
    )
