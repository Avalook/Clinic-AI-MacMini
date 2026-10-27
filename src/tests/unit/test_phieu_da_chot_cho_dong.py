"""Cờ "phiếu đã chốt mà dịch vụ còn đang làm" của màn phòng (27/10/2026)."""

from __future__ import annotations

from clinicai.services.service_execution_service import phieu_da_chot_cho_dong


def test_chi_khi_dang_lam_o_phong_va_co_phieu_ready() -> None:
    assert phieu_da_chot_cho_dong("IN_PROGRESS", True, ["DRAFT", "READY"]) is True
    # Phiếu còn nháp → nút chính vẫn là [Hoàn tất] trong phiếu.
    assert phieu_da_chot_cho_dong("IN_PROGRESS", True, ["DRAFT"]) is False
    # Dịch vụ đã xong / chưa làm → không có gì để đóng.
    assert phieu_da_chot_cho_dong("COMPLETED", True, ["READY"]) is False
    assert phieu_da_chot_cho_dong(None, True, ["READY"]) is False
    # Lần làm do bàn khám mở: không phải việc của phòng.
    assert phieu_da_chot_cho_dong("IN_PROGRESS", False, ["READY"]) is False
    assert phieu_da_chot_cho_dong("IN_PROGRESS", True, []) is False
