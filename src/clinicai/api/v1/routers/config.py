"""Roster and price-list endpoints (W5, ADR-0012)."""

from __future__ import annotations

from datetime import date
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from clinicai.api.identity import ClinicRole, StaffIdentity, require_role
from clinicai.core.database import get_db_pool
from clinicai.services.clinic_settings_service import ClinicSettingsService
from clinicai.services.config_service import (
    PRICE_ROLES,
    ROSTER_ROLES,
    PriceGroup,
    PriceListService,
    RosterDecision,
    RosterService,
    Shift,
)

router = APIRouter()

# Everyone works a shift, so everyone may sign up for one; the service decides
# who may schedule somebody else.
_ROSTER_GUARD = require_role(*ROSTER_ROLES)
_PRICE_GUARD = require_role(*PRICE_ROLES)
# Chỉ Trưởng ca + Quản lý được đổi luật đặt lịch (khung giờ / số chỗ) của
# phòng khám. Bác sĩ/CSKH/Lễ tân thấy luật nhưng không sửa được — sửa luật
# đang chạy khi đang có lịch đặt là một quyết định vận hành.
_BOOKING_POLICY_GUARD = require_role(ClinicRole.TRUONG_CA, ClinicRole.MANAGEMENT)


class ShiftRequest(BaseModel):
    work_date: date
    station: str = Field(min_length=1, max_length=64)
    shift: Shift = "FULL"
    # Ignored unless the caller is management — see the service.
    staff_id: UUID | None = None
    staff_name: str | None = Field(default=None, max_length=200)
    sort: int = 0


class RosterDecisionRequest(BaseModel):
    decision: RosterDecision
    reason: str | None = Field(default=None, max_length=500)


class PriceCreateRequest(BaseModel):
    service_code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=300)
    group: PriceGroup
    unit_price: float | str | None = None


class PriceUpdateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=300)
    unit_price: float | str | None = None
    active: bool | None = None


class BookingPolicyUpdateRequest(BaseModel):
    """Ba con số của luật đặt lịch (C.3). CHECK constraint ở DB chặn lần cuối."""

    slot_minutes: int = Field(ge=1, le=60)
    regular_cap: int = Field(ge=1, le=100)
    walkin_cap: int = Field(ge=0, le=100)


@router.post("/roster/shifts", status_code=201)
async def add_shift(
    body: ShiftRequest,
    identity: StaffIdentity = Depends(_ROSTER_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, object]:
    """Sign up for a shift, or — as management — schedule somebody."""
    roster_id = await RosterService(pool).add_shift(
        work_date=body.work_date,
        station=body.station,
        shift=body.shift,
        identity=identity,
        staff_id=str(body.staff_id) if body.staff_id else None,
        staff_name=body.staff_name,
        sort=body.sort,
    )
    return {"ok": True, "id": roster_id}


@router.patch("/roster/shifts/{roster_id}")
async def decide_shift(
    roster_id: UUID,
    body: RosterDecisionRequest,
    identity: StaffIdentity = Depends(_ROSTER_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, object]:
    """Approve or reject a self-registered shift. Management only."""
    await RosterService(pool).decide(
        roster_id=str(roster_id),
        decision=body.decision,
        reason=body.reason,
        identity=identity,
    )
    return {"ok": True}


@router.delete("/roster/shifts/{roster_id}")
async def remove_shift(
    roster_id: UUID,
    identity: StaffIdentity = Depends(_ROSTER_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, object]:
    """Remove a shift. Non-managers may only remove their own."""
    await RosterService(pool).remove(roster_id=str(roster_id), identity=identity)
    return {"ok": True}


@router.post("/service-prices", status_code=201)
async def add_price(
    body: PriceCreateRequest,
    identity: StaffIdentity = Depends(_PRICE_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, object]:
    """Add a line to the price list."""
    price_id = await PriceListService(pool).add(
        service_code=body.service_code,
        name=body.name,
        group=body.group,
        unit_price=body.unit_price,
        identity=identity,
    )
    return {"ok": True, "id": price_id}


@router.patch("/service-prices/{price_id}")
async def update_price(
    price_id: UUID,
    body: PriceUpdateRequest,
    identity: StaffIdentity = Depends(_PRICE_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, object]:
    """Change a price, rename a line, or switch it off."""
    await PriceListService(pool).update(
        price_id=str(price_id),
        identity=identity,
        name=body.name,
        unit_price=body.unit_price,
        # Absent means "leave the price"; explicit null means "clear it".
        unit_price_provided="unit_price" in body.model_fields_set,
        active=body.active,
    )
    return {"ok": True}


@router.delete("/service-prices/{price_id}")
async def remove_price(
    price_id: UUID,
    identity: StaffIdentity = Depends(_PRICE_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, object]:
    """Remove a price-list line."""
    await PriceListService(pool).remove(price_id=str(price_id), identity=identity)
    return {"ok": True}


@router.patch("/booking-policy")
async def update_booking_policy(
    body: BookingPolicyUpdateRequest,
    identity: StaffIdentity = Depends(_BOOKING_POLICY_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, object]:
    """Thay luật đặt lịch của CHÍNH phòng khám đang đăng nhập (C.3 write path).

    Chỉ Trưởng ca + Quản lý. ``identity.clinic_id`` luôn suy từ membership —
    KHÔNG nhận clinic_id từ body, nên phòng khám A sửa không thể chạm phòng
    khám B. CHECK constraint ``clinic_booking_policy_valid`` là lưới cuối.
    """
    saved = await ClinicSettingsService(pool).update_booking_policy(
        identity=identity,
        slot_minutes=body.slot_minutes,
        regular_cap=body.regular_cap,
        walkin_cap=body.walkin_cap,
    )
    return {"ok": True, **saved}


# ── Booking capacity overrides (C.4) ──────────────────────────────────


class DoctorOverrideRequest(BaseModel):
    """Create a per-doctor booking capacity override."""

    doctor_id: UUID
    weekday: int | None = Field(default=None, ge=0, le=6)
    slot_minutes: int | None = Field(default=None, ge=1, le=60)
    regular_cap: int | None = Field(default=None, ge=1, le=100)
    walkin_cap: int | None = Field(default=None, ge=0, le=100)
    effective_from: date | None = None
    effective_to: date | None = None
    reason: str | None = Field(default=None, max_length=500)


class SlotOverrideRequest(BaseModel):
    """Create a per-slot booking capacity override (date range)."""

    doctor_id: UUID | None = None
    date_start: date
    date_end: date
    hour_start: int = Field(ge=0, le=23)
    hour_end: int = Field(ge=1, le=24)
    regular_cap: int | None = Field(default=None, ge=1, le=100)
    walkin_cap: int | None = Field(default=None, ge=0, le=100)
    reason: str = Field(min_length=1, max_length=500)


@router.post("/booking-overrides/doctor", status_code=201)
async def create_doctor_override(
    body: DoctorOverrideRequest,
    identity: StaffIdentity = Depends(_BOOKING_POLICY_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, object]:
    """Tạo override số chỗ cho một bác sĩ (C.4 Tầng 2)."""
    from clinicai.services.booking_override_service import BookingOverrideService

    return await BookingOverrideService(pool).create_doctor_override(
        identity=identity,
        doctor_id=str(body.doctor_id),
        weekday=body.weekday,
        slot_minutes=body.slot_minutes,
        regular_cap=body.regular_cap,
        walkin_cap=body.walkin_cap,
        effective_from=body.effective_from,
        effective_to=body.effective_to,
        reason=body.reason,
    )


@router.get("/booking-overrides/doctor")
async def list_doctor_overrides(
    doctor_id: UUID | None = None,
    active_only: bool = True,
    identity: StaffIdentity = Depends(_BOOKING_POLICY_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, object]:
    """Xem override per-doctor hiện tại."""
    from clinicai.services.booking_override_service import BookingOverrideService

    items = await BookingOverrideService(pool).list_doctor_overrides(
        identity=identity,
        doctor_id=str(doctor_id) if doctor_id else None,
        active_only=active_only,
    )
    return {"ok": True, "items": items}


@router.delete("/booking-overrides/doctor/{override_id}")
async def delete_doctor_override(
    override_id: UUID,
    identity: StaffIdentity = Depends(_BOOKING_POLICY_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, object]:
    """Xóa override per-doctor."""
    from clinicai.services.booking_override_service import BookingOverrideService

    await BookingOverrideService(pool).delete_doctor_override(
        identity=identity, override_id=str(override_id)
    )
    return {"ok": True}


@router.post("/booking-overrides/slot", status_code=201)
async def create_slot_override(
    body: SlotOverrideRequest,
    identity: StaffIdentity = Depends(_BOOKING_POLICY_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, object]:
    """Tạo override số chỗ cho khung giờ cụ thể (C.4 Tầng 3).

    Hỗ trợ date range: ``date_start`` đến ``date_end`` (tối đa 90 ngày).
    Dùng cho "tuần này", "tháng này", hoặc "từ ngày X đến ngày Y".
    """
    from clinicai.services.booking_override_service import BookingOverrideService

    return await BookingOverrideService(pool).create_slot_override(
        identity=identity,
        doctor_id=str(body.doctor_id) if body.doctor_id else None,
        date_start=body.date_start,
        date_end=body.date_end,
        hour_start=body.hour_start,
        hour_end=body.hour_end,
        regular_cap=body.regular_cap,
        walkin_cap=body.walkin_cap,
        reason=body.reason,
    )


@router.get("/booking-overrides/slot")
async def list_slot_overrides(
    date_from: date | None = None,
    date_to: date | None = None,
    doctor_id: UUID | None = None,
    identity: StaffIdentity = Depends(_BOOKING_POLICY_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, object]:
    """Xem slot overrides, lọc theo ngày và/hoặc bác sĩ."""
    from clinicai.services.booking_override_service import BookingOverrideService

    items = await BookingOverrideService(pool).list_slot_overrides(
        identity=identity,
        date_from=date_from,
        date_to=date_to,
        doctor_id=str(doctor_id) if doctor_id else None,
    )
    return {"ok": True, "items": items}


@router.delete("/booking-overrides/slot/{override_id}")
async def delete_slot_override(
    override_id: UUID,
    identity: StaffIdentity = Depends(_BOOKING_POLICY_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, object]:
    """Xóa slot override."""
    from clinicai.services.booking_override_service import BookingOverrideService

    await BookingOverrideService(pool).delete_slot_override(
        identity=identity, override_id=str(override_id)
    )
    return {"ok": True}


# ── Feature Mode (Phase 1 onboarding) ─────────────────────────────────

_FEATURE_MODE_READ = require_role(
    ClinicRole.MANAGEMENT, ClinicRole.TRUONG_CA,
    ClinicRole.CSKH, ClinicRole.RECEPTION,
    ClinicRole.DOCTOR, ClinicRole.ULTRASOUND_DOCTOR,
    ClinicRole.TKYK, ClinicRole.NURSE_ULTRASOUND,
    ClinicRole.CASHIER, ClinicRole.CASHIER_THUOC,
    ClinicRole.CASHIER_DV, ClinicRole.PHARMACIST,
)
_FEATURE_MODE_WRITE = require_role(ClinicRole.MANAGEMENT)


class FeatureModeUpdateRequest(BaseModel):
    mode: str = Field(min_length=1, max_length=20)


@router.get("/feature-mode")
async def get_feature_mode(
    identity: StaffIdentity = Depends(_FEATURE_MODE_READ),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, object]:
    """Trả chế độ phòng khám hiện tại (CSKH_ONLY hoặc FULL_CLINIC)."""
    mode = await ClinicSettingsService(pool).get_feature_mode(
        clinic_id=identity.clinic_id,
    )
    return {"ok": True, "mode": mode}


@router.put("/feature-mode")
async def update_feature_mode(
    body: FeatureModeUpdateRequest,
    identity: StaffIdentity = Depends(_FEATURE_MODE_WRITE),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, object]:
    """Đổi chế độ phòng khám. Chỉ MANAGEMENT."""
    result = await ClinicSettingsService(pool).update_feature_mode(
        identity=identity,
        mode=body.mode,
    )
    return {"ok": True, **result}

