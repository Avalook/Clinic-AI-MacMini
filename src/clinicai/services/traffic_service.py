"""Dịch vụ đọc báo cáo lưu lượng truy cập và xác thực mã PIN quản trị."""

from __future__ import annotations

import os
from pathlib import Path


def xac_thuc_ma_pin(pin: str) -> bool:
    """Xác thực mã PIN quản trị viên.

    Mặc định lấy từ biến môi trường OPS_TRAFFIC_PIN (nếu có),
    fallback là '12345678'.
    """
    expected_pin = os.environ.get("OPS_TRAFFIC_PIN", "12345678").strip()
    return bool(pin) and pin.strip() == expected_pin


def doc_bao_cao_traffic() -> str | None:
    """Đọc tệp báo cáo GoAccess HTML từ thư mục .ops-status gắn vào container."""
    report_file = Path(
        os.environ.get("OPS_TRAFFIC_REPORT_FILE")
        or "/run/clinicai-ops/traffic-report.html"
    )
    if not report_file.is_file():
        return None
    try:
        return report_file.read_text(encoding="utf-8")
    except Exception:
        return None
