"""Hoàn tất phiếu thì dịch vụ phải làm gì — luật thuần (29/10/2026)."""

from __future__ import annotations

import pytest

from clinicai.services.hoan_tat_dong_dich_vu import viec_can_lam


@pytest.mark.parametrize(
    ("execution_status", "exec_status", "lam_them", "dang_chay", "mong"),
    [
        # Ca HPV 28/10: chưa ai bấm Bắt đầu → một lần bấm là bắt đầu + xong.
        (None, "authorized", False, False, "bat_dau_va_xong"),
        ("PENDING", "assigned", False, False, "bat_dau_va_xong"),
        ("IN_PROGRESS", "in_progress", False, True, "xong"),
        # Đã xong / không làm / dừng / đã huỷ: phiếu chốt, không đụng dịch vụ.
        ("COMPLETED", "performed", False, False, None),
        ("NOT_PERFORMED", "authorized", False, False, None),
        ("INTERRUPTED", "assigned", False, False, None),
        ("PENDING", "cancelled", False, False, None),
        # Nháp chưa bác sĩ duyệt: chưa có việc để làm.
        (None, "draft", False, False, None),
        # Lần làm do nơi khác mở mà không còn chạy: không đoán.
        ("IN_PROGRESS", "in_progress", False, False, None),
        # Làm thêm tại quầy: đường riêng (`lam_them_dong_dich_vu`).
        ("PENDING", "assigned", True, False, None),
    ],
)
def test_viec_can_lam(
    execution_status: str | None,
    exec_status: str,
    lam_them: bool,
    dang_chay: bool,
    mong: str | None,
) -> None:
    assert (
        viec_can_lam(
            execution_status=execution_status,
            exec_status=exec_status,
            nguon_lam_them=lam_them,
            co_lan_dang_chay=dang_chay,
        )
        == mong
    )
