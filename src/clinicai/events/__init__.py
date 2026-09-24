"""Nền event-driven: danh mục sự kiện + một đường phát duy nhất."""

from clinicai.events.catalogue import DANH_MUC, PayloadSuKien, SuKien, tra
from clinicai.events.emit import HE_THONG, NguoiGayRa, ai_agent, emit_event, nguoi

__all__ = [
    "DANH_MUC",
    "HE_THONG",
    "NguoiGayRa",
    "PayloadSuKien",
    "SuKien",
    "ai_agent",
    "emit_event",
    "nguoi",
    "tra",
]
