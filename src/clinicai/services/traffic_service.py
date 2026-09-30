"""Dịch vụ đọc dữ liệu lưu lượng truy cập và xác thực tài khoản quản trị."""

from __future__ import annotations

import hmac
import json
import os
from pathlib import Path


def xac_thuc_ma_pin(pin: str) -> bool:
    """Xác thực mã PIN quản trị viên (biến môi trường OPS_TRAFFIC_PIN)."""
    expected_pin = os.environ.get("OPS_TRAFFIC_PIN", "").strip()
    if not expected_pin or not pin:
        return False
    return hmac.compare_digest(pin.strip().encode(), expected_pin.encode())


def xac_thuc_admin(username: str, mat_khau: str) -> bool:
    """Xác thực tài khoản admin và mật khẩu quản trị."""
    expected_user = os.environ.get("OPS_TRAFFIC_USER", "admin").strip()
    expected_pass = (
        os.environ.get("OPS_TRAFFIC_PASSWORD")
        or os.environ.get("OPS_TRAFFIC_PIN")
        or "12345678"
    ).strip()
    if not username or not mat_khau or not expected_pass or not expected_user:
        return False
    return (
        hmac.compare_digest(username.strip().encode(), expected_user.encode())
        and hmac.compare_digest(mat_khau.strip().encode(), expected_pass.encode())
    )


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
