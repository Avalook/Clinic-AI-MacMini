"""Màn hình TV phòng chờ: không danh tính, đúng thứ tự, đúng khu.

Bài kiểm khẳng định TÍNH CHẤT của thứ RỜI KHỎI MÁY CHỦ, không khẳng định cú
pháp SQL. Cái đắt nhất ở đây là ① — một lần thêm cột cho tiện là tên bệnh nhân
đi thẳng vào payload của một màn hình treo giữa phòng chờ.
"""

from __future__ import annotations

import datetime
import json
from typing import Any

from clinicai.core.clock import CLINIC_TZ
from clinicai.services.display_board_service import (
    CHU_THICH_DAY_LEN,
    _doc_zones,
    _khu_vuc,
    _mot_dong,
)
from clinicai.services.queue_order import (
    REASON_DAT_TRUOC_DUNG_GIO,
    REASON_DEN_TRUC_TIEP,
)
from clinicai.services.queue_rows import thu_tu_goi_theo_ngay

GIO = datetime.datetime(2026, 8, 6, 18, 0, tzinfo=CLINIC_TZ)


class _Row(dict[str, Any]):
    """Đóng vai asyncpg.Record — chỉ cần đọc bằng khoá."""


def _hang(**over: Any) -> _Row:
    base: dict[str, Any] = {
        "id": "11111111-1111-4111-8111-111111111111",
        "slot_start": GIO,
        "queue_number": "12",
        "booking_channel": "ZALO",
        "doctor_id": "22222222-2222-4222-8222-222222222222",
        "service_name": "Khám phụ khoa",
        "checked_in_at": GIO,
        "visit_status": None,
        "slot_minutes": 15,
    }
    base.update(over)
    return _Row(base)


# ── ① Không một mẩu danh tính nào rời máy chủ ────────────────────────────────
def test_khong_tra_ve_bat_ky_truong_dinh_danh_nao() -> None:
    dong = _mot_dong(_hang(), None, [])
    cam = {
        "full_name",
        "patient_code",
        "phone_primary",
        "phone_secondary",
        "date_of_birth",
        "address",
        "patient_name",
        "doctor_name",
        "clinic_patient_id",
    }
    assert cam.isdisjoint(dong.keys())


def test_khong_co_chuoi_nao_trong_payload_giong_ten_nguoi() -> None:
    """Kiểm trên GIÁ TRỊ chứ không chỉ trên tên khoá.

    Một trường tên vô hại vẫn có thể chứa tên người — ví dụ ai đó nhét
    `service_name` thành "Khám phụ khoa — Nguyễn Thị A". Bài này bắt chính hành
    vi ấy: đưa một cái tên vào hàng dữ liệu rồi kiểm nó KHÔNG xuất hiện đâu cả.
    """
    hang = _hang(service_name="Siêu âm thai — Nguyễn Thị Ánh Tuyết")
    payload = json.dumps(_mot_dong(hang, None, []), ensure_ascii=False)
    assert "Nguyễn Thị Ánh Tuyết" not in payload


# ── ② Thứ tự giống hệt bảng của nhân viên ────────────────────────────────────
def test_tivi_xep_theo_luat_goi_khong_theo_gio_hen() -> None:
    """Người có hẹn muộn hơn nhưng đến trong khung phải đứng TRƯỚC người vãng
    lai đã đến từ sớm — đúng thứ tự mà bảng của Lễ tân đưa ra."""
    vang_lai = _hang(
        id="aaaa1111-1111-4111-8111-111111111111",
        queue_number="1",
        booking_channel="WALK_IN",
        slot_start=GIO,
        checked_in_at=GIO,
    )
    co_hen = _hang(
        id="bbbb2222-2222-4222-8222-222222222222",
        queue_number="2",
        booking_channel="ZALO",
        slot_start=GIO + datetime.timedelta(minutes=5),
        checked_in_at=GIO + datetime.timedelta(minutes=5),
    )

    qd = thu_tu_goi_theo_ngay([vang_lai, co_hen])
    assert qd[str(co_hen["id"])].call_order < qd[str(vang_lai["id"])].call_order


def test_co_chu_thich_thi_phai_co_ly_do_dat_truoc() -> None:
    """Chỉ dán câu "được ưu tiên vì đã đặt lịch" cho ĐÚNG người đặt lịch.

    Vé ƯT và người quay lại sau khi có kết quả cũng vượt lên — dán nhầm câu này
    lên họ là nói dối với cả phòng chờ.
    """
    vang_lai = _hang(
        id="aaaa1111-1111-4111-8111-111111111111",
        booking_channel="WALK_IN",
        checked_in_at=GIO,
    )
    co_hen = _hang(
        id="bbbb2222-2222-4222-8222-222222222222",
        booking_channel="ZALO",
        slot_start=GIO + datetime.timedelta(minutes=5),
        checked_in_at=GIO + datetime.timedelta(minutes=5),
    )
    qd = thu_tu_goi_theo_ngay([vang_lai, co_hen])

    dong_co_hen = _mot_dong(co_hen, qd[str(co_hen["id"])], [])
    dong_vang_lai = _mot_dong(vang_lai, qd[str(vang_lai["id"])], [])

    assert dong_co_hen["promoted"] is True
    assert dong_co_hen["promoted_note"] == CHU_THICH_DAY_LEN
    assert dong_co_hen["call_reason"] == REASON_DAT_TRUOC_DUNG_GIO

    assert dong_vang_lai["promoted"] is False
    assert dong_vang_lai["promoted_note"] is None
    assert dong_vang_lai["call_reason"] == REASON_DEN_TRUC_TIEP


# ── Khu vực ─────────────────────────────────────────────────────────────────
def test_cau_hinh_khong_khai_tu_khoa_thi_van_doan_duoc_khu() -> None:
    """Cấu hình THẬT trên máy chủ chỉ có key/label/prefix.

    Nếu chỉ đọc cấu hình thì mọi dòng thành "không thuộc khu nào" và tivi trắng
    trơn — nên phải rơi về đúng luật mà màn hình vẫn dùng từ trước.
    """
    zones = [{"key": "kham", "label": "Khám bác sĩ"}, {"key": "sa", "label": "SA"}]
    assert _khu_vuc("Siêu âm thai", zones) == "sa"
    assert _khu_vuc("Xét nghiệm máu", zones) == "xn"
    assert _khu_vuc("Khám phụ khoa", zones) == "kham"


def test_sieu_am_phai_roi_vao_mot_khu_co_that() -> None:
    """LỖI ĐÃ SỬA: luật đoán trả "sa" còn cấu hình khai sa1/sa2/sa3.

    Phép so cũ ở màn hình là `"sa".startsWith("sa1")` — luôn sai — nên bệnh nhân
    siêu âm chưa bao giờ hiện trên bảng gọi số, và ba ô SA chỉ hiện dấu gạch
    ngang y như lúc thật sự chưa có ai.
    """
    zones_that = [
        {"key": "kham", "label": "Khám bác sĩ"},
        {"key": "sa1", "label": "SA1"},
        {"key": "sa2", "label": "SA2"},
        {"key": "sa3", "label": "SA3"},
        {"key": "xn", "label": "Xét nghiệm"},
    ]
    khoa_co_that = {z["key"] for z in zones_that}
    for dich_vu in ("Siêu âm thai", "Xét nghiệm máu", "Khám phụ khoa"):
        assert _khu_vuc(dich_vu, zones_that) in khoa_co_that, dich_vu


def test_cau_hinh_co_khai_tu_khoa_thi_theo_cau_hinh() -> None:
    zones = [{"key": "tt", "label": "Thủ thuật", "match": ["thủ thuật"]}]
    assert _khu_vuc("Thủ thuật nhỏ", zones) == "tt"
    # Đã khai thì KHÔNG lén rơi về luật mặc định: phòng khám tự chịu trách
    # nhiệm về danh sách của mình, và một khu "tự nhiên xuất hiện" khó lần hơn
    # một khu bị bỏ trống.
    assert _khu_vuc("Siêu âm thai", zones) is None


def test_zones_thieu_thi_tra_rong_chu_khong_doan() -> None:
    assert _doc_zones(None) == []
    assert _doc_zones(_Row({"zones": None})) == []
    assert _doc_zones(_Row({"zones": '[{"key": "a"}]'})) == [{"key": "a"}]


def test_dang_goi_doc_tu_trang_thai_luot_kham() -> None:
    """`IN_PROGRESS` là giá trị của visit.status. Ràng buộc CHECK trên
    appointment.status KHÔNG cho phép nó tồn tại — nhánh cũ lọc trên lịch hẹn
    nên chưa bao giờ khớp dòng nào."""
    assert _mot_dong(_hang(visit_status="IN_PROGRESS"), None, [])["is_current"] is True
    assert _mot_dong(_hang(visit_status="OPEN"), None, [])["is_current"] is False
