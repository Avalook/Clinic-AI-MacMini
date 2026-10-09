"""Cửa tiền CHUNG khi bắt đầu làm — phòng dịch vụ + bàn khám (Tuyền chốt
09/10/2026) — luật thuần, không cần DB."""

from __future__ import annotations

import pytest

from clinicai.services import finance_gate as fg
from clinicai.services.service_execution_service import (
    CAU_KHACH_KHONG_CHON,
    chan_vi_chua_thu,
    cua_tien_chot_ho,
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


@pytest.mark.parametrize("sel", ["PENDING", None])
def test_cho_quyet_cua_mo_thi_chot_ho(sel: str | None) -> None:
    # Đã tick / dây tắt (DUE mà duoc_lam), đã thu (liệu trình trả trước), 0đ.
    for q in (
        _q(fg.DUE, duoc_lam=True),
        _q(fg.PAID, duoc_lam=True),
        _q(fg.NOT_REQUIRED, duoc_lam=True),
    ):
        assert cua_tien_chot_ho(q, selection_status=sel) == (True, None, True)
        assert chan_vi_chua_thu(q, selection_status=sel) is False


def test_cho_quyet_chua_thu_chua_tick_chan_cau_chua_thu() -> None:
    q = _q(fg.DUE, duoc_lam=False)
    assert cua_tien_chot_ho(q, selection_status="PENDING") == (
        False,
        fg.CAU_CHUA_THU,
        False,
    )
    assert chan_vi_chua_thu(q, selection_status="PENDING") is True


def test_da_chon_di_nhu_cu_khong_chot() -> None:
    assert cua_tien_chot_ho(
        _q(fg.PAID, duoc_lam=True), selection_status="SELECTED"
    ) == (True, None, False)
    assert cua_tien_chot_ho(_q(fg.DUE, duoc_lam=False), selection_status="SELECTED")[
        :2
    ] == (False, fg.CAU_CHUA_THU)
    assert chan_vi_chua_thu(_q(fg.DUE, duoc_lam=False), selection_status="SELECTED")


def test_khach_chon_khong_lam_chan_khong_moi_tick() -> None:
    q = _q(fg.NOT_APPLICABLE, duoc_lam=False)
    assert cua_tien_chot_ho(q, selection_status="NOT_SELECTED") == (
        False,
        CAU_KHACH_KHONG_CHON,
        False,
    )
    assert chan_vi_chua_thu(q, selection_status="NOT_SELECTED") is False


@pytest.mark.parametrize(
    "st", [fg.REFUNDED, fg.REFUND_PENDING, fg.FINANCIAL_REVIEW_REQUIRED]
)
def test_tien_dang_hoan_chan_tick_khong_go(st: str) -> None:
    duoc, cau, chot = cua_tien_chot_ho(
        _q(st, duoc_lam=False), selection_status="PENDING"
    )
    assert (duoc, chot) == (False, False) and cau != fg.CAU_CHUA_THU
    assert chan_vi_chua_thu(_q(st, duoc_lam=False), selection_status="PENDING") is False


def test_khong_co_quyet_dinh_tien_thi_chan() -> None:
    assert cua_tien_chot_ho(None, selection_status="PENDING")[0] is False
    assert chan_vi_chua_thu(None, selection_status="PENDING") is False


def test_gia_su_chon_chi_doi_cho_quyet() -> None:
    assert fg._lua_chon("PENDING", gia_su_chon=True) == "SELECTED"
    assert fg._lua_chon(None, gia_su_chon=True) == "SELECTED"
    assert fg._lua_chon("NOT_SELECTED", gia_su_chon=True) == "NOT_SELECTED"
    assert fg._lua_chon("PENDING", gia_su_chon=False) == "PENDING"
