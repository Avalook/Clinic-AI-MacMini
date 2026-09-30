"""Dịch vụ đọc dữ liệu lưu lượng truy cập và xác thực mã PIN quản trị."""

from __future__ import annotations

import json
import os
from pathlib import Path


def xac_thuc_ma_pin(pin: str) -> bool:
    """Xác thực mã PIN quản trị viên.

    Mặc định lấy từ biến môi trường OPS_TRAFFIC_PIN (nếu có),
    fallback là '12345678'.
    """
    expected_pin = os.environ.get("OPS_TRAFFIC_PIN", "12345678").strip()
    return bool(pin) and pin.strip() == expected_pin


def doc_du_lieu_traffic() -> dict[str, object] | None:
    """Đọc dữ liệu tổng hợp lưu lượng JSON từ thư mục .ops-status gắn vào container."""
    summary_file = Path(
        os.environ.get("OPS_TRAFFIC_SUMMARY_FILE")
        or "/run/clinicai-ops/traffic-summary.json"
    )
    if not summary_file.is_file():
        return None
    try:
        return json.loads(summary_file.read_text(encoding="utf-8"))
    except Exception:
        return None
