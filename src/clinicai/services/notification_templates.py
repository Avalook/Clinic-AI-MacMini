"""Notification message templates — map event types to Vietnamese text.

Phase 3 of the System Design completion plan (Bài 23 — Notification System).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

# Template functions: receive event payload dict → return formatted message.
# HTML formatting for Telegram (bold, italic).


def appointment_confirmed(payload: dict[str, Any]) -> str:
    """Appointment confirmed by doctor."""
    patient = payload.get("patient_name", "Quý khách")
    date = payload.get("date", "")
    time = payload.get("time", "")
    doctor = payload.get("doctor_name", "bác sĩ")
    return (
        f"✅ <b>Xác nhận lịch hẹn</b>\n\n"
        f"Xin chào {patient},\n"
        f"Lịch hẹn ngày <b>{date}</b> lúc <b>{time}</b> "
        f"với BS {doctor} đã được xác nhận.\n\n"
        f"Vui lòng đến trước giờ hẹn 10 phút. Cảm ơn!"
    )


def appointment_cancelled(payload: dict[str, Any]) -> str:
    """Appointment cancelled."""
    patient = payload.get("patient_name", "Quý khách")
    date = payload.get("date", "")
    time = payload.get("time", "")
    reason = payload.get("reason", "Không rõ lý do")
    return (
        f"❌ <b>Huỷ lịch hẹn</b>\n\n"
        f"Xin chào {patient},\n"
        f"Lịch hẹn ngày <b>{date}</b> lúc <b>{time}</b> đã bị huỷ.\n"
        f"Lý do: {reason}\n\n"
        f"Vui lòng liên hệ phòng khám để đặt lại. Xin lỗi vì sự bất tiện!"
    )


def appointment_reminder(payload: dict[str, Any]) -> str:
    """Appointment reminder (e.g. 1 day before)."""
    patient = payload.get("patient_name", "Quý khách")
    date = payload.get("date", "")
    time = payload.get("time", "")
    doctor = payload.get("doctor_name", "bác sĩ")
    return (
        f"🔔 <b>Nhắc lịch hẹn</b>\n\n"
        f"Xin chào {patient},\n"
        f"Bạn có lịch hẹn ngày <b>{date}</b> lúc <b>{time}</b> "
        f"với BS {doctor}.\n\n"
        f"Vui lòng đến trước giờ hẹn 10 phút. Hẹn gặp bạn!"
    )


def visit_completed(payload: dict[str, Any]) -> str:
    """Visit completed — doctor finished exam."""
    patient = payload.get("patient_name", "Quý khách")
    return (
        f"🏥 <b>Khám xong</b>\n\n"
        f"Xin chào {patient},\n"
        f"Lượt khám của bạn đã hoàn tất. "
        f"Vui lòng ra quầy thu ngân để thanh toán. Cảm ơn!"
    )


# Registry: event_type string → template function.
TEMPLATES: dict[str, Callable[[dict[str, Any]], str]] = {
    "appointment.confirmed": appointment_confirmed,
    "appointment.cancelled": appointment_cancelled,
    "appointment.reminder": appointment_reminder,
    "visit.completed": visit_completed,
}


def render(event_type: str, payload: dict[str, Any]) -> str | None:
    """Render a notification message for the given event type.

    Returns None if no template is registered for this event type.
    """
    template_fn = TEMPLATES.get(event_type)
    if template_fn is None:
        return None
    return template_fn(payload)
