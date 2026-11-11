"""Địa chỉ của khách — MỘT luật cho mọi chỗ in / xuất (11/11/2026).

Hồ sơ khách có hai nơi giữ địa chỉ:

* ``address`` — ô chữ tự do. Form tạo khách ghép sẵn "số nhà, phường, tỉnh" vào đây,
  và đây là ô DUY NHẤT sửa được trên màn (``PatientAdminEditor``).
* ``address_detail`` / ``ward_name`` / ``province_name`` — phần có cấu trúc, chỉ ghi
  lúc tạo khách; không màn nào sửa.

Trước hôm nay mỗi chỗ tự chọn: phiếu khám in ưu tiên phần có cấu trúc, PDF hồ sơ khám
lấy riêng ``address_detail``, file MISA ưu tiên ``address``. Lễ tân sửa địa chỉ xong thì
hồ sơ và file MISA ra địa chỉ mới, phiếu in và PDF vẫn ra địa chỉ CŨ (chị Hoài rà địa
chỉ sai, 11/11). Luật chung: ô sửa được thắng; trống thì mới ghép phần có cấu trúc.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

#: Các cột ``patient`` hàm này cần — câu SQL nào lấy địa chỉ thì chọn đủ bốn cột này.
COT_DIA_CHI: tuple[str, ...] = (
    "address",
    "address_detail",
    "ward_name",
    "province_name",
)


def _chu(v: Any) -> str:
    """Chữ đã bỏ khoảng trắng hai đầu; không phải chữ (None, số, rác) → rỗng."""
    return v.strip() if isinstance(v, str) else ""


def dia_chi_khach(bn: Mapping[str, Any]) -> str | None:
    """Địa chỉ để in / xuất của một khách; không có gì → None (không ném)."""
    tu_do = _chu(bn.get("address"))
    if tu_do:
        return tu_do
    phan = [_chu(bn.get(k)) for k in COT_DIA_CHI[1:]]
    co = [x for x in phan if x]
    return ", ".join(co) if co else None


__all__ = ["COT_DIA_CHI", "dia_chi_khach"]
