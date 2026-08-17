"""Gỡ ca trực khám thì gỡ luôn bác sĩ khỏi lịch hẹn ngày ấy.

Tuyền chốt 14/08/2026: *"chỗ bác sĩ Thành đó thì xoá bác sĩ luôn đi còn để lại
làm gì"*. Lịch rơi về hàng "Chờ xếp bác sĩ" để có người xếp lại.

Đọc mã nguồn thay vì dựng cả một ca trực thật: thứ cần canh là bốn ranh giới
dưới đây có còn nguyên không, và chúng đọc được.
"""

from __future__ import annotations

import inspect


def _nguon() -> str:
    from clinicai.services.config_service import RosterService

    return inspect.getsource(RosterService.remove)


def test_go_trong_cung_giao_dich_voi_viec_xoa_ca() -> None:
    """Tách hai bước thì có khoảnh khắc ca đã mất mà lịch vẫn mang tên người ấy.

    Và nếu bước hai hỏng thì khoảnh khắc ấy kéo dài mãi mãi, không ai biết.
    """
    src = _nguon()
    assert "conn.transaction()" in src
    assert "DELETE FROM work_roster" in src
    assert "UPDATE public.appointment" in src
    assert src.index("DELETE FROM work_roster") < src.index("UPDATE public.appointment")


def test_chi_ca_kham_moi_dung_toi_lich_hen() -> None:
    """Gỡ ca thủ thuật ngoài giờ KHÔNG đụng lịch hẹn khám — hai việc khác nhau."""
    src = _nguon()
    assert 'row["station"] != "LICH_KHAM"' in src


def test_huy_theo_khung_phu_con_lai_khong_theo_ngay() -> None:
    """VIẾT LẠI 17/08/2026 (Luật 12.5 — quyết định đổi thì test đổi kèm lý do).

    Bản cũ canh phép kiểm `con_ca` mức NGÀY: "còn ca nào trong ngày thì không
    gỡ gì". Tuyền bắt được nó sai cả hai chiều — xoá SÁNG còn CHIỀU thì lịch
    sáng sống sót mồ côi; xoá SÁNG rồi thêm CẢ NGÀY thì lịch sáng bị huỷ oan
    trước khi ca mới kịp vào. Nay huỷ theo HỢP KHUNG các ca còn lại
    (core/shifts — cùng thước với đường đặt lịch); hành vi đầy đủ nằm ở
    test_huy_theo_khung_gio.py, đây chỉ khoá việc phép đo mức-ngày không
    lặng lẽ quay lại."""
    src = _nguon()
    assert "merge_windows" in src and "covers(" in src
    assert "con_ca" not in src, "phép kiểm mức-ngày đã bị thay, không được về"


def test_chi_go_lich_con_cuu_duoc_va_nho_nguoi_bi_go() -> None:
    """Không viết lại quá khứ, và không lấy bác sĩ ra khỏi phòng đang khám."""
    src = _nguon()
    assert "slot_start > now()" in src
    assert "'SCHEDULED', 'CSKH_CONFIRMED', 'CONFIRMED'" in src
    assert "bac_si_da_go_id = doctor_id" in src, (
        "đặt doctor_id = NULL rồi thôi là xoá mất một sự thật: khách đã được "
        "hẹn với một người cụ thể và CSKH sắp phải gọi giải thích"
    )
    assert "appointment.doctor_removed" in src, "phải ghi vào sổ sự kiện"
