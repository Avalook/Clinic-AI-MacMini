"""Mẫu tin Telegram — sự kiện lịch hẹn thành câu tiếng Việt cho NHÓM VẬN HÀNH.

VIẾT LẠI 15/08/2026, và đổi cả NGƯỜI NHẬN. Bản đầu (Bài 23) soạn tin cho
KHÁCH ("Xin chào Quý khách…") nhưng cấu hình chỉ có MỘT ``TELEGRAM_CHAT_ID``
— một nhóm chung. Tin xưng hô với khách mà đổ vào nhóm nội bộ thì ai đọc
cũng thấy sai vai; và payload thật trong ``event_log`` chỉ mang các ID, nên
"ngày <b></b> lúc <b></b>" render ra chuỗi rỗng — đo trên staging 15/08.

Nay: tin viết cho NGƯỜI TRỰC — ngắn, đủ để biết có việc gì vừa xảy ra và có
cần nhấc máy không. Dữ liệu tên/giờ/dịch vụ do relay LÀM GIÀU từ database
ngay trước khi gửi (xem ``notification_relay._lam_giau``) — template chỉ đọc
các khoá đã làm giàu, thiếu thì nói "—" chứ không bịa.

KHÔNG BAO GIỜ đưa số điện thoại / CCCD / địa chỉ vào tin: Telegram là máy
chủ bên thứ ba, tin nhắn sống ngoài tầm RLS. Tên + mã hồ sơ là đủ để người
trực mở đúng khách trong hệ thống — tra cứu thật diễn ra Ở TRONG hệ thống.
"""

from __future__ import annotations

from typing import Any, Callable

# Nhãn lý do huỷ — cùng danh mục với ``booking_service.LY_DO_HUY`` nhưng rút
# gọn cho một dòng tin. KHÔNG import từ booking_service: tin nhắn cần câu
# ngắn, còn danh mục gốc là câu đầy đủ cho ô chọn — hai nhu cầu khác nhau,
# và drift-test của danh mục gốc không canh bản rút gọn này.
_LY_DO_HUY_NGAN: dict[str, str] = {
    "BAO_KHI_XAC_NHAN": "khách báo khi gọi xác nhận",
    "BAO_KHI_NHAC_HEN": "khách báo khi nhắc hẹn",
    "BAO_VAO_GIO_KHAM": "khách báo vào giờ khám",
    "DAT_TRUNG": "đặt trùng, bỏ bớt",
    "BAC_SI_DOI_LICH": "bác sĩ đổi lịch làm việc",
    "KHAC": "lý do khác",
}


def _khach(payload: dict[str, Any]) -> str:
    ten = payload.get("ten_khach") or "—"
    ma = payload.get("patient_code")
    return f"{ten} ({ma})" if ma else str(ten)


def _gio(payload: dict[str, Any]) -> str:
    return str(payload.get("gio_kham") or "—")


def lich_moi(payload: dict[str, Any]) -> str:
    bs = payload.get("ten_bac_si") or "chờ xếp bác sĩ"
    dv = payload.get("dich_vu") or "—"
    return f"📅 <b>Lịch mới</b> · {_gio(payload)}\n{_khach(payload)} · {dv} · BS {bs}"


def huy_lich(payload: dict[str, Any]) -> str:
    ly_do = _LY_DO_HUY_NGAN.get(
        str(payload.get("ly_do_huy_ma") or ""), "không rõ lý do"
    )
    return f"❌ <b>Huỷ lịch</b> · {_gio(payload)}\n{_khach(payload)} · {ly_do}"


def doi_lich(payload: dict[str, Any]) -> str:
    return f"🔁 <b>Đổi lịch</b> · giờ mới {_gio(payload)}\n{_khach(payload)}"


def xoa_ca_bac_si(payload: dict[str, Any]) -> str:
    """Ca trực bị xoá kéo theo lịch của khách bị huỷ — tin ĐÁNG GỌI nhất.

    remove() huỷ lịch với vết ``bac_si_da_go_id``; người trực đọc tin này là
    biết phải gọi ai đặt lại, không cần chờ mở bảng lịch tuần."""
    bs = payload.get("bac_si_da_go") or payload.get("ten_bac_si") or "—"
    return (
        f"⚠️ <b>Xoá ca bác sĩ {bs}</b> · lịch {_gio(payload)} đã huỷ\n"
        f"{_khach(payload)} — gọi khách đặt lịch mới"
    )


# Registry: event_type → hàm soạn tin. Sự kiện KHÔNG có trong bảng này thì
# relay đánh dấu đã-xử-lý và đi tiếp (render trả None) — im lặng có chủ ý:
# nhóm nhận đủ bốn loại tin đáng nhấc máy, không nhận nhật ký hệ thống.
TEMPLATES: dict[str, Callable[[dict[str, Any]], str]] = {
    "appointment.created": lich_moi,
    "appointment.cancelled": huy_lich,
    "appointment.rescheduled": doi_lich,
    "appointment.doctor_removed": xoa_ca_bac_si,
}


def render(event_type: str, payload: dict[str, Any]) -> str | None:
    """Render a notification message for the given event type.

    Returns None if no template is registered for this event type.
    """
    template_fn = TEMPLATES.get(event_type)
    if template_fn is None:
        return None
    return template_fn(payload)
