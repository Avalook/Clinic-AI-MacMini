"""Target-bound cashier grants; the authenticated audit actor never changes."""

from dataclasses import replace
from typing import Any

import asyncpg

from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.core.exceptions import SafetyGateError
from clinicai.services.cashier_scope_service import CashierScopeService


def head_money_grant(
    identity: StaffIdentity, kind: str, visit_id: str | None = None
) -> bool:
    scope = identity.cashier_head_scope
    return bool(scope and visit_id and scope == (kind, visit_id, identity.location_id))


async def authorize_drug_line(
    pool: asyncpg.Pool,
    identity: StaffIdentity,
    prescription_id: str,
) -> StaffIdentity:
    visit_id = await pool.fetchval(
        "SELECT visit_id::text FROM prescription WHERE clinic_id=$1::uuid"
        " AND id=$2::uuid AND removed_at IS NULL",
        identity.clinic_id,
        prescription_id,
    )
    if not visit_id:
        raise SafetyGateError("Không tìm thấy dòng thuốc trong phạm vi của bạn.")
    return await authorize_payment(pool, identity, visit_id=visit_id, kind="thuoc")


async def authorize_payment(
    pool: asyncpg.Pool,
    identity: StaffIdentity,
    *,
    visit_id: str | None = None,
    kind: str | None = None,
    cycle_id: str | None = None,
    refund_id: str | None = None,
    proof_id: str | None = None,
    read: bool = False,
) -> StaffIdentity:
    """Resolve the stored target before roster authorization, including proofs."""
    if proof_id:
        cycle_id = await pool.fetchval(
            "SELECT cycle_id::text FROM anh_chuyen_khoan"
            " WHERE clinic_id=$1::uuid AND id=$2::uuid",
            identity.clinic_id,
            proof_id,
        )
        if not cycle_id:
            raise SafetyGateError("Không tìm thấy phiếu trong phạm vi của bạn.")
    if refund_id:
        row = await pool.fetchrow(
            "SELECT payment_cycle_id::text AS cycle_id FROM payment_refund"
            " WHERE clinic_id=$1::uuid AND refund_id=$2::uuid",
            identity.clinic_id,
            refund_id,
        )
        if not row:
            raise SafetyGateError("Không tìm thấy khoản hoàn trong phạm vi của bạn.")
        cycle_id = row["cycle_id"]
    target: Any = None
    if cycle_id:
        target = await pool.fetchrow(
            "SELECT visit_id::text AS visit_id, kind, status,"
            " co_so_cua_luot(clinic_id,visit_id)::text AS location_id"
            " FROM payment_cycle WHERE clinic_id=$1::uuid"
            " AND payment_cycle_id=$2::uuid",
            identity.clinic_id,
            cycle_id,
        )
        if target and (
            (visit_id and target["visit_id"] != visit_id)
            or (kind and target["kind"] != kind)
        ):
            raise SafetyGateError("Phiếu không khớp lượt hoặc loại tiền.")
    elif visit_id and kind:
        target = await pool.fetchrow(
            "SELECT visit_id::text AS visit_id, $3::text AS kind,"
            " co_so_cua_luot(clinic_id,visit_id)::text AS location_id"
            " FROM visit WHERE clinic_id=$1::uuid AND visit_id=$2::uuid",
            identity.clinic_id,
            visit_id,
            kind,
        )
    if not target or not target["location_id"]:
        raise SafetyGateError("Không tìm thấy lượt trong phạm vi của bạn.")
    service = CashierScopeService(pool)
    if read:
        if not cycle_id:
            raise SafetyGateError("Không tìm thấy phiếu trong phạm vi của bạn.")
        if target.get("status") == "PENDING_VERIFICATION":
            try:
                await service.authorize_active(
                    identity, kind=target["kind"], co_so=target["location_id"]
                )
                return replace(identity, cashier_head_scope=None)
            except SafetyGateError:
                pass  # Outside the active counter, only personal history may read it.
        await service.receipt(identity, id_=cycle_id, loai="thu")
        # Read permission does not become a write grant. Existing proof service
        # checks collect permission; the router has independently authorized read.
        return identity
    scope = await service.authorize_active(
        identity,
        kind=target["kind"],
        co_so=target["location_id"],
    )
    if scope.actor_id is None and not identity.co_vai({ClinicRole.MANAGEMENT}):
        return replace(
            scope.identity,
            cashier_head_scope=(
                target["kind"],
                target["visit_id"],
                target["location_id"],
            ),
        )
    return replace(scope.identity, cashier_head_scope=None)
