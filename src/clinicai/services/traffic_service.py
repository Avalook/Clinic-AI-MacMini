"""Dịch vụ đọc dữ liệu lưu lượng truy cập và xác thực mã PIN quản trị."""

from __future__ import annotations

import hmac
import json
import os
from pathlib import Path


def xac_thuc_ma_pin(pin: str) -> bool:
    """Xác thực mã PIN quản trị viên (biến môi trường OPS_TRAFFIC_PIN).

    KHÔNG có mã mặc định (30/09/2026): mã viết cứng trong code thì ai đọc repo
    cũng biết — chưa đặt OPS_TRAFFIC_PIN trong .env.prod là tính năng TẮT (mọi
    mã đều sai). So bằng ``hmac.compare_digest`` để thời gian so không lộ mã.
    """
    expected_pin = os.environ.get("OPS_TRAFFIC_PIN", "").strip()
    if not expected_pin or not pin:
        return False
    return hmac.compare_digest(pin.strip().encode(), expected_pin.encode())


def doc_du_lieu_traffic() -> dict[str, object] | None:
    """Đọc dữ liệu tổng hợp lưu lượng JSON từ thư mục .ops-status gắn vào container."""
    summary_file = Path(
        os.environ.get("OPS_TRAFFIC_SUMMARY_FILE")
        or "/run/clinicai-ops/traffic-summary.json"
    )
    if not summary_file.is_file():
        return None
    try:
        data = json.loads(summary_file.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None
