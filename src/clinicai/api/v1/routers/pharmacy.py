"""FastAPI endpoints cho kho thuốc (B.3 — đường ghi đầu tiên của nhà thuốc).

Router mỏng: vai do server quyết bằng ``require_role``, `clinic_id` lấy từ
identity, mọi luật nằm trong ``PharmacyService``. Database không có policy ghi
cho `authenticated` (ADR-0012), nên đây là con đường duy nhất số tồn kho thay
đổi được.

Bốn thao tác POST đều đổi tồn kho, nên đều nhận ``Idempotency-Key``: dược sĩ
bấm "Nhập" hai lần vì mạng chậm là chuyện xảy ra hàng ngày, và lần bấm thứ hai
không được biến thành một lô hàng thứ hai.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from clinicai.api.idempotency import IdempotencyGuard, idempotency_guard
from clinicai.api.identity import ClinicRole, StaffIdentity, require_role
from clinicai.core.database import get_db_pool
from clinicai.services.pharmacy_service import PharmacyService

router = APIRouter()

# Quản lý được vào cùng dược sĩ: kiểm kê cuối tháng và huỷ hàng hết hạn là việc
# của họ, và một phòng khám nhỏ có hôm không có dược sĩ nào trực.
_PHARMACY_GUARD = require_role(ClinicRole.PHARMACIST, ClinicRole.MANAGEMENT)


class ReceiveBatchRequest(BaseModel):
    """Nhập hàng vào một lô (tạo mới nếu mã lô chưa có)."""

    drug_catalog_id: UUID
    batch_code: str = Field(min_length=1, max_length=64)
    expiry_date: date
    quantity: Decimal
    unit: str = Field(default="viên", max_length=32)
    cost_price: int | None = None
    reason: str | None = None


class AdjustBatchRequest(BaseModel):
    """Điều chỉnh sau kiểm kê. Âm = giảm, dương = tăng, 0 bị từ chối."""

    quantity: Decimal
    reason: str


class DiscardBatchRequest(BaseModel):
    """Huỷ hàng. ``quantity`` bỏ trống = huỷ toàn bộ phần còn lại của lô."""

    quantity: Decimal | None = None
    reason: str


class DispenseRequest(BaseModel):
    """Cấp thuốc — trừ kho theo FEFO, có thể trải trên nhiều lô."""

    drug_catalog_id: UUID
    quantity: Decimal
    prescription_id: UUID | None = None
    reason: str | None = None


@router.post("/pharmacy/batches")
async def receive_batch(
    body: ReceiveBatchRequest,
    identity: StaffIdentity = Depends(_PHARMACY_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
    idem: IdempotencyGuard = Depends(idempotency_guard),
) -> dict[str, Any]:
    """Nhập hàng: một dòng RECEIVE, tồn do trigger cộng."""
    await idem.acquire(pool, actor_id=identity.auth_user_id)
    if idem.is_replay:
        return idem.cached_response  # type: ignore[return-value]

    service = PharmacyService(pool)
    result = await service.receive_batch(
        identity=identity,
        drug_catalog_id=str(body.drug_catalog_id),
        batch_code=body.batch_code,
        expiry_date=body.expiry_date,
        quantity=body.quantity,
        unit=body.unit,
        cost_price=body.cost_price,
        reason=body.reason,
    )
    await idem.save(pool, result, status_code=200)
    return result


@router.post("/pharmacy/batches/{batch_id}/adjust")
async def adjust_batch(
    batch_id: UUID,
    body: AdjustBatchRequest,
    identity: StaffIdentity = Depends(_PHARMACY_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
    idem: IdempotencyGuard = Depends(idempotency_guard),
) -> dict[str, Any]:
    """Điều chỉnh tồn sau kiểm kê, bắt buộc có lý do."""
    await idem.acquire(pool, actor_id=identity.auth_user_id)
    if idem.is_replay:
        return idem.cached_response  # type: ignore[return-value]

    service = PharmacyService(pool)
    result = await service.adjust_batch(
        identity=identity,
        batch_id=str(batch_id),
        quantity=body.quantity,
        reason=body.reason,
    )
    await idem.save(pool, result, status_code=200)
    return result


@router.post("/pharmacy/batches/{batch_id}/discard")
async def discard_batch(
    batch_id: UUID,
    body: DiscardBatchRequest,
    identity: StaffIdentity = Depends(_PHARMACY_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
    idem: IdempotencyGuard = Depends(idempotency_guard),
) -> dict[str, Any]:
    """Huỷ hàng hết hạn/vỡ/hỏng, bắt buộc có lý do."""
    await idem.acquire(pool, actor_id=identity.auth_user_id)
    if idem.is_replay:
        return idem.cached_response  # type: ignore[return-value]

    service = PharmacyService(pool)
    result = await service.discard_batch(
        identity=identity,
        batch_id=str(batch_id),
        quantity=body.quantity,
        reason=body.reason,
    )
    await idem.save(pool, result, status_code=200)
    return result


@router.post("/pharmacy/dispense")
async def dispense(
    body: DispenseRequest,
    identity: StaffIdentity = Depends(_PHARMACY_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
    idem: IdempotencyGuard = Depends(idempotency_guard),
) -> dict[str, Any]:
    """Cấp thuốc theo FEFO — hạn gần nhất ra trước, lô hết hạn không ra."""
    await idem.acquire(pool, actor_id=identity.auth_user_id)
    if idem.is_replay:
        return idem.cached_response  # type: ignore[return-value]

    service = PharmacyService(pool)
    result = await service.dispense(
        identity=identity,
        drug_catalog_id=str(body.drug_catalog_id),
        quantity=body.quantity,
        prescription_id=(str(body.prescription_id) if body.prescription_id else None),
        reason=body.reason,
    )
    await idem.save(pool, result, status_code=200)
    return result
