"""V10 — làm trước, thu sau: luật thuần của FinanceGate và khối Đổi phòng."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from typing import Any

import pytest

from clinicai.services import finance_gate as fg
from clinicai.services.service_routing_service import (
    CHE_DO_DU_KIEN,
    CHE_DO_XEP,
    che_do_doi_phong,
)


def _facts(
    *,
    execution_status: str | None = None,
    exec_status: str = "authorized",
    footprints: tuple[fg.Footprint, ...] = (),
    gia: tuple[int, ...] = (300000,),
    ben_thu: tuple[str, ...] = ("CLINIC",),
) -> fg.OrderFinanceFacts:
    return fg.OrderFinanceFacts(
        order_id="o1",
        selection_status="SELECTED",
        exec_status=exec_status,
        execution_status=execution_status,
        gia=gia,
        ben_thu=ben_thu,
        footprints=footprints,
        visit_allocation_unknown=False,
    )


def _fp(*, pending: int = 0, done: int = 0) -> fg.Footprint:
    return fg.Footprint(
        line_id="l1",
        cycle_id="c1",
        cycle_status="PAID",
        paid=True,
        quantity=Decimal(1),
        refund_pending_qty=Decimal(pending),
        refund_completed_qty=Decimal(done),
    )


@pytest.mark.parametrize(
    ("execution_status", "exec_status"),
    [
        (None, "authorized"),
        ("PENDING", "assigned"),
        ("IN_PROGRESS", "in_progress"),
        ("COMPLETED", "performed"),
        (None, "performed"),  # dòng cũ chỉ có trục exec_status
    ],
)
def test_chua_thu_la_due_va_duoc_lam(
    execution_status: str | None, exec_status: str
) -> None:
    d = fg.derive_finance_state(
        _facts(execution_status=execution_status, exec_status=exec_status)
    )
    assert (d.finance_state, d.financially_ready, d.duoc_lam) == ("DUE", False, True)
    assert not d.needs_human_review


def test_cho_xac_minh_va_thieu_gia_van_duoc_lam() -> None:
    thieu = fg.derive_finance_state(_facts(gia=()))
    assert (thieu.finance_state, thieu.duoc_lam) == ("FINANCIAL_DATA_INCOMPLETE", True)
    cho = fg.derive_finance_state(
        _facts(
            footprints=(
                fg.Footprint(
                    line_id="l1",
                    cycle_id="c1",
                    cycle_status="PENDING_VERIFICATION",
                    paid=False,
                    quantity=Decimal(1),
                    refund_pending_qty=Decimal(0),
                    refund_completed_qty=Decimal(0),
                ),
            )
        )
    )
    assert (cho.finance_state, cho.duoc_lam) == ("PENDING_VERIFICATION", True)


def test_tien_dang_hoan_da_hoan_dung_giua_chung_van_chan() -> None:
    assert not fg.derive_finance_state(_facts(footprints=(_fp(pending=1),))).duoc_lam
    assert not fg.derive_finance_state(_facts(footprints=(_fp(done=1),))).duoc_lam
    dung = fg.derive_finance_state(_facts(execution_status="INTERRUPTED"))
    assert (dung.finance_state, dung.reason_code, dung.duoc_lam) == (
        "FINANCIAL_REVIEW_REQUIRED",
        "EXECUTED_WITHOUT_PAYMENT",
        False,
    )


def test_khach_chua_chot_khong_duoc_lam() -> None:
    d = fg.derive_finance_state(replace(_facts(), selection_status="PENDING"))
    assert (d.finance_state, d.duoc_lam) == ("NOT_APPLICABLE", False)


def test_cho_api_co_duoc_lam() -> None:
    assert fg.derive_finance_state(_facts()).cho_api()["duoc_lam"] is True


def test_doi_phong_da_chot_chua_thu_la_xep() -> None:
    chung: dict[str, Any] = {
        "execution_status": "PENDING",
        "exec_status": "authorized",
        "hang": None,
        "dieu_phoi": True,
        "khach_ve": False,
    }
    assert (
        che_do_doi_phong(selection_status="SELECTED", duoc_lam=True, **chung)
        == CHE_DO_XEP
    )
    assert (
        che_do_doi_phong(selection_status="PENDING", duoc_lam=False, **chung)
        == CHE_DO_DU_KIEN
    )
