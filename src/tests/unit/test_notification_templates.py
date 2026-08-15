"""Mẫu tin Telegram cho nhóm vận hành (viết lại 15/08/2026).

Ba luật đáng canh:
  · Tin đọc được khi payload ĐÃ làm giàu, và không sập khi CHƯA (thiếu khoá
    thì "—", không KeyError giữa vòng relay).
  · Sự kiện ngoài registry trả None — nhóm không nhận nhật ký hệ thống.
  · KHÔNG số điện thoại trong bất kỳ mẫu nào — Telegram là bên thứ ba.
"""

from __future__ import annotations

import inspect

from clinicai.services import notification_templates as mau


def test_bon_loai_tin_dang_nhac_may() -> None:
    assert set(mau.TEMPLATES) == {
        "appointment.created",
        "appointment.cancelled",
        "appointment.rescheduled",
        "appointment.doctor_removed",
    }


def test_lich_moi_du_du_lieu() -> None:
    tin = mau.render(
        "appointment.created",
        {
            "ten_khach": "Nguyễn Thị Lan",
            "patient_code": "BN-2026-000001",
            "gio_kham": "07:00 19/08",
            "ten_bac_si": "Phan Chí Thành",
            "dich_vu": "Phụ khoa",
        },
    )
    assert tin is not None
    assert "Nguyễn Thị Lan (BN-2026-000001)" in tin
    assert "07:00 19/08" in tin and "Phan Chí Thành" in tin


def test_payload_ngheo_khong_sap_va_khong_bia() -> None:
    """Chưa làm giàu (DB lỗi, lịch đã xoá) — tin vẫn gửi được, chỗ thiếu là
    dấu gạch, không phải chuỗi rỗng lặng lẽ như bản cũ."""
    tin = mau.render("appointment.cancelled", {"status": "CANCELLED"})
    assert tin is not None
    assert "—" in tin and "không rõ lý do" in tin


def test_huy_lich_noi_ly_do_ngan() -> None:
    tin = mau.render(
        "appointment.cancelled",
        {"ten_khach": "Lan", "ly_do_huy_ma": "BAC_SI_DOI_LICH"},
    )
    assert tin is not None and "bác sĩ đổi lịch làm việc" in tin


def test_xoa_ca_goi_ten_bac_si_bi_go() -> None:
    tin = mau.render(
        "appointment.doctor_removed",
        {
            "bac_si_da_go": "Phan Chí Thành",
            "ten_khach": "Lan",
            "gio_kham": "07:00 19/08",
        },
    )
    assert tin is not None
    assert "Xoá ca bác sĩ Phan Chí Thành" in tin
    assert "gọi khách đặt lịch mới" in tin


def test_su_kien_ngoai_danh_sach_tra_none() -> None:
    assert mau.render("slot_hold.created", {}) is None
    assert mau.render("cskh.tuong_tac", {}) is None


def test_khong_mau_nao_dua_so_dien_thoai_vao_tin() -> None:
    ma = inspect.getsource(mau)
    assert "phone" not in ma.replace("KHÔNG BAO GIỜ đưa số điện thoại", ""), (
        "mẫu tin chạm tới trường phone — Telegram là bên thứ ba, cấm"
    )
