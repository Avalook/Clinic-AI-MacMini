"""Nhãn tiếng Việt của VAI tài khoản (`clinic_membership.role`) cho bảng lịch.

Góp ý phòng khám 27/09/2026 (đợt 3, A9): *"Cần lịch trực + tên nhân sự kèm vai
trò của mỗi người"*. Bảng Lịch làm việc chỉ in tên — "Thư", "Hà Vũ" — và người
mới không biết ai là điều dưỡng, ai là lễ tân.

NHÃN DO MÁY CHỦ TRẢ, không để giao diện tự dịch mã vai: cùng một mã vai đã có
lúc được hai màn gọi hai tên. Hai cỡ:

  * ``day_du`` — tab "Theo người" (một dòng một người, có chỗ);
  * ``ngan``   — chip cạnh tên trong ô lịch (ô hẹp, 11 cột một tuần).

Mã lạ / rỗng → hai chuỗi rỗng: không đoán vai cho một người mình không biết —
đoán sai chức danh y tế là in sai trước mặt bệnh nhân.
"""

from __future__ import annotations

from typing import Any

#: mã vai → (đầy đủ, ngắn). Đầy đủ khớp ROLE_LABEL của giao diện.
NHAN_VAI: dict[str, tuple[str, str]] = {
    "DOCTOR": ("Bác sĩ", "BS"),
    "ULTRASOUND_DOCTOR": ("Bác sĩ Siêu âm", "BS siêu âm"),
    "NURSE_ULTRASOUND": ("Điều dưỡng", "ĐD"),
    "TKYK": ("Thư ký Y khoa", "TKYK"),
    "CSKH": ("CSKH", "CSKH"),
    "MANAGEMENT": ("Quản lý", "Quản lý"),
    "RECEPTION": ("Lễ tân", "Lễ tân"),
    "CASHIER": ("Thu ngân", "Thu ngân"),
    "CASHIER_THUOC": ("Thu ngân thuốc", "TN thuốc"),
    "CASHIER_DV": ("Thu ngân dịch vụ", "TN dịch vụ"),
    "TRUONG_CA": ("Trưởng ca", "Trưởng ca"),
    "PHARMACIST": ("Dược sĩ", "Dược sĩ"),
}


def nhan_vai(ma: object) -> tuple[str, str]:
    """(đầy đủ, ngắn) của một mã vai. Không phải chuỗi / mã lạ → ("", "")."""
    if not isinstance(ma, str):
        return ("", "")
    return NHAN_VAI.get(ma.strip().upper(), ("", ""))


def gan_nhan_vai(dong: dict[str, Any], *, khoa_ma: str = "vai_ma") -> dict[str, Any]:
    """Thay cột mã vai (``vai_ma``) của một dòng lịch bằng ``vai`` + ``vai_ngan``."""
    day_du, ngan = nhan_vai(dong.pop(khoa_ma, None))
    dong["vai"] = day_du
    dong["vai_ngan"] = ngan
    return dong
