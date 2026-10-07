"""Luật thuần của thẻ chỉ định điều trị + cửa tiền [Làm tại bàn khám]
(Tuyền chốt 07/10/2026) — không cần DB."""

from __future__ import annotations

import pytest

from clinicai.services import finance_gate as fg
from clinicai.services.dieu_tri_ban_kham import trang_thai_the
from clinicai.services.service_execution_service import (
    CAU_KHACH_KHONG_CHON,
    cua_tien_ban_kham,
)


def _q(state: str, *, duoc_lam: bool) -> fg.FinanceDecision:
    return fg.FinanceDecision(
        order_id="o",
        finance_state=state,
        payment_required_by_clinic=True,
        financially_ready=state in fg.READY_STATES,
        reason_code=None,
        coverage_cycle_id=None,
        needs_human_review=False,
        duoc_lam=duoc_lam,
    )


@pytest.mark.parametrize(
    ("ex", "noi", "ra"),
    [
        (None, None, "CHUA_LAM"),
        ("PENDING", None, "CHUA_LAM"),
        ("IN_PROGRESS", "BAN_KHAM", "DANG_LAM_BAN_KHAM"),
        ("IN_PROGRESS", None, "DANG_LAM_PHONG"),
        ("COMPLETED", "BAN_KHAM", "XONG"),
        ("COMPLETED", None, "XONG"),
        ("NOT_PERFORMED", None, "KHONG_LAM"),
        ("INTERRUPTED", None, "DUNG"),
        ("rác", None, "CHUA_LAM"),
    ],
)
def test_trang_thai_the(ex: str | None, noi: str | None, ra: str) -> None:
    assert trang_thai_the(ex, noi) == ra


def test_cua_tien_chua_thu_khong_tick_chan_goi_y_tick() -> None:
    assert cua_tien_ban_kham(
        _q(fg.DUE, duoc_lam=False), selection_status="SELECTED", duoc_chua_thu=False
    ) == (False, fg.CAU_CHUA_THU, False)


def test_cua_tien_da_thu_hoac_tick_thi_lam() -> None:
    assert cua_tien_ban_kham(
        _q(fg.PAID, duoc_lam=True), selection_status="SELECTED", duoc_chua_thu=False
    ) == (True, None, False)
    assert cua_tien_ban_kham(
        _q(fg.DUE, duoc_lam=True), selection_status="SELECTED", duoc_chua_thu=True
    ) == (True, None, False)


def test_cua_tien_khach_chua_chot() -> None:
    chua = _q(fg.NOT_APPLICABLE, duoc_lam=False)
    # Tick / dây tắt → làm được, chốt như lúc tick.
    assert cua_tien_ban_kham(chua, selection_status="PENDING", duoc_chua_thu=True) == (
        True,
        None,
        True,
    )
    # Không tick → chặn câu "chưa thu".
    assert cua_tien_ban_kham(chua, selection_status="PENDING", duoc_chua_thu=False) == (
        False,
        fg.CAU_CHUA_THU,
        False,
    )
    # Khách đã chọn KHÔNG làm ở quầy → chặn, không tự chốt lại.
    assert cua_tien_ban_kham(
        chua, selection_status="NOT_SELECTED", duoc_chua_thu=True
    ) == (False, CAU_KHACH_KHONG_CHON, False)


def test_cua_tien_dang_hoan_chan() -> None:
    duoc, cau, chot = cua_tien_ban_kham(
        _q(fg.REFUNDED, duoc_lam=False), selection_status="SELECTED", duoc_chua_thu=True
    )
    assert (duoc, chot) == (False, False) and cau and "hoàn" in cau
