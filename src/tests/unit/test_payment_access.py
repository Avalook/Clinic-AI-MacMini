from dataclasses import replace
from typing import Any, cast
from unittest.mock import AsyncMock

import asyncpg
import pytest

from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.core.exceptions import SafetyGateError
from clinicai.services.cashier_scope_service import CashierScope
from clinicai.services.payment_access_service import authorize_payment, head_money_grant


def staff() -> StaffIdentity:
    return StaffIdentity(
        staff_id="staff",
        auth_user_id="auth",
        full_name="Head",
        department="",
        role=ClinicRole.TRUONG_CA,
        clinic_id="clinic",
        location_id="site",
        location_name="Site",
    )


@pytest.mark.asyncio
async def test_head_grant_preserves_actor_and_is_target_bound(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = staff()
    pool = AsyncMock()
    pool.fetchrow.return_value = dict(
        visit_id="visit", kind="thuoc", location_id="site"
    )
    active = AsyncMock(return_value=CashierScope(original, [], [], None))
    monkeypatch.setattr(
        "clinicai.services.cashier_scope_service.CashierScopeService.authorize_active",
        active,
    )
    granted = await authorize_payment(
        cast(asyncpg.Pool, pool), original, cycle_id="cycle"
    )
    assert granted.staff_id == original.staff_id and granted.role == original.role
    assert head_money_grant(granted, "thuoc", "visit")
    assert not head_money_grant(granted, "dich_vu", "visit")
    assert not head_money_grant(granted, "thuoc", "other")
    assert not head_money_grant(replace(granted, location_id="other"), "thuoc", "visit")
    assert original.cashier_head_scope is None


@pytest.mark.asyncio
async def test_off_shift_and_mismatched_target_never_get_grant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pool = AsyncMock()
    pool.fetchrow.return_value = dict(
        visit_id="visit", kind="dich_vu", location_id="site"
    )
    active = AsyncMock(side_effect=SafetyGateError("Không đang trực"))
    monkeypatch.setattr(
        "clinicai.services.cashier_scope_service.CashierScopeService.authorize_active",
        active,
    )
    cases: list[dict[str, Any]] = [
        dict(cycle_id="cycle"),
        dict(cycle_id="cycle", visit_id="other"),
        dict(cycle_id="cycle", kind="thuoc"),
    ]
    for args in cases:
        with pytest.raises(SafetyGateError):
            await authorize_payment(cast(asyncpg.Pool, pool), staff(), **args)


@pytest.mark.asyncio
async def test_proof_read_checks_receipt_without_write_grant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pool = AsyncMock()
    pool.fetchval.return_value = "cycle"
    pool.fetchrow.return_value = dict(
        visit_id="visit", kind="thuoc", location_id="site"
    )
    receipt = AsyncMock()
    monkeypatch.setattr(
        "clinicai.services.cashier_scope_service.CashierScopeService.receipt", receipt
    )
    result = await authorize_payment(
        cast(asyncpg.Pool, pool), staff(), proof_id="proof", read=True
    )
    receipt.assert_awaited_once()
    assert result.cashier_head_scope is None


@pytest.mark.asyncio
async def test_pending_proof_is_visible_to_active_counter_not_paid_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pool = AsyncMock()
    pool.fetchval.return_value = "cycle"
    target = dict(visit_id="old-visit", kind="thuoc", location_id="site")
    pool.fetchrow.return_value = {**target, "status": "PENDING_VERIFICATION"}
    active = AsyncMock(return_value=CashierScope(staff(), [], [], "staff"))
    receipt = AsyncMock(side_effect=SafetyGateError("Phiếu người khác"))
    monkeypatch.setattr(
        "clinicai.services.cashier_scope_service.CashierScopeService.authorize_active",
        active,
    )
    monkeypatch.setattr(
        "clinicai.services.cashier_scope_service.CashierScopeService.receipt",
        receipt,
    )
    await authorize_payment(
        cast(asyncpg.Pool, pool), staff(), proof_id="proof", read=True
    )
    receipt.assert_not_awaited()
    pool.fetchrow.return_value = {**target, "status": "PAID"}
    with pytest.raises(SafetyGateError):
        await authorize_payment(
            cast(asyncpg.Pool, pool), staff(), proof_id="proof", read=True
        )
