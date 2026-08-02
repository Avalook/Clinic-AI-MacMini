"""Appointment booking and lifecycle endpoints (W5, ADR-0012).

The router admits every role that can issue *some* action; which role may issue
*which* action is part of the transition table, so it lives beside the rest of
the state machine rather than being split across a decorator.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from clinicai.api.idempotency import IdempotencyGuard, idempotency_guard
from clinicai.api.identity import (
    ClinicRole,
    StaffIdentity,
    get_current_identity,
    require_role,
)
from clinicai.core.database import get_db_pool
from clinicai.services.booking_service import INTAKE_ROLES, Action, BookingService
from clinicai.services.capacity_service import CapacityService
from clinicai.services.clinic_policy import load_clinic_policy

router = APIRouter()

# Booking is intake work.
_BOOKING_GUARD = require_role(*INTAKE_ROLES)
# Any role that appears in the transition table may reach the action endpoint;
# the table then decides. Cashiers never move an appointment.
_ACTION_GUARD = require_role(
    ClinicRole.DOCTOR,
    ClinicRole.ULTRASOUND_DOCTOR,
    ClinicRole.TKYK,
    ClinicRole.NURSE_ULTRASOUND,
    ClinicRole.RECEPTION,
    ClinicRole.CSKH,
    ClinicRole.TRUONG_CA,
    ClinicRole.MANAGEMENT,
)


class BookingRequest(BaseModel):
    clinic_patient_id: UUID
    service_type_id: UUID
    location_id: UUID
    slot_start: datetime
    slot_end: datetime
    doctor_id: UUID | None = None
    booking_channel: str | None = Field(default=None, max_length=64)
    queue_number: str | None = Field(default=None, max_length=32)
    # Capacity hints. CSKH may override the suggestion, so they are inputs.
    patient_kind: str | None = Field(default=None, max_length=16)
    need_sono: bool | None = None
    thanh_min: int | None = Field(default=None, ge=0, le=600)
    sono_min: int | None = Field(default=None, ge=0, le=600)


class ActionRequest(BaseModel):
    action: Action
    cancellation_reason: str | None = Field(default=None, max_length=1000)
    # An absent doctor_id means "leave it"; an explicit null means "unassign".
    doctor_id: UUID | None = None
    slot_start: datetime | None = None
    slot_end: datetime | None = None


@router.post("/appointments/bookings", status_code=201)
async def create_booking(
    body: BookingRequest,
    identity: StaffIdentity = Depends(_BOOKING_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
    idem: IdempotencyGuard = Depends(idempotency_guard),
) -> dict[str, Any]:
    """Book an appointment. A retried request must not become two bookings."""
    # acquire() returns a NEW guard — IdempotencyGuard is frozen, so not
    # reassigning it silently disables replay protection and then makes
    # save() raise. Matches the payment router.
    idem = await idem.acquire(pool, actor_id=identity.auth_user_id)
    if idem.is_replay:
        return idem.cached_response  # type: ignore[return-value]

    result = await BookingService(pool).create(
        clinic_patient_id=str(body.clinic_patient_id),
        service_type_id=str(body.service_type_id),
        location_id=str(body.location_id),
        slot_start=body.slot_start,
        slot_end=body.slot_end,
        identity=identity,
        doctor_id=str(body.doctor_id) if body.doctor_id else None,
        booking_channel=body.booking_channel,
        queue_number=body.queue_number,
        patient_kind=body.patient_kind,
        need_sono=body.need_sono,
        thanh_min=body.thanh_min,
        sono_min=body.sono_min,
    )
    payload = {"ok": True, **result}
    await idem.save(pool, payload, status_code=201)
    return payload


@router.get("/appointments/quote")
async def capacity_quote(
    date: str,
    location_id: str,
    doctor_id: str | None = None,
    identity: StaffIdentity = Depends(_BOOKING_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Read-only capacity quote for the slot picker UI (CAP-01).

    Returns budget + current usage per hour so the UI can colour cells.
    Does NOT decide whether a booking is allowed — that is the DB trigger
    + the pre-check in BookingService.
    """
    svc = CapacityService(pool)
    return await svc.quote(
        date=date,
        location_id=location_id,
        doctor_id=doctor_id,
        clinic_id=identity.clinic_id,
    )


@router.get("/appointments/policy")
async def booking_policy(
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, int]:
    """Độ dài khung và số chỗ của phòng khám đang đăng nhập (C.3).

    Không dùng ``_BOOKING_GUARD``: bảng lịch tuần ở màn chủ vẽ đúng cái lưới
    này, và bác sĩ xem lịch của mình không phải người đặt lịch. Ba con số này
    không phải dữ liệu bệnh nhân — giấu chúng khỏi một nửa phòng khám chỉ làm
    lưới vẽ sai, không làm ai an toàn hơn.

    Đây là NGUỒN DUY NHẤT trình duyệt được biết luật. Frontend không đọc thẳng
    ``clinic.settings``: A.5 đã bỏ cột đó khỏi GRANT cho ``authenticated``.
    """
    async with pool.acquire() as conn:
        policy = await load_clinic_policy(conn, identity.clinic_id)
    return {
        "slot_minutes": policy.slot_minutes,
        "regular_cap": policy.regular_cap,
        "walkin_cap": policy.walkin_cap,
    }


@router.patch("/appointments/{appointment_id}")
async def apply_appointment_action(
    appointment_id: UUID,
    body: ActionRequest,
    identity: StaffIdentity = Depends(_ACTION_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Move an appointment through its lifecycle."""
    result = await BookingService(pool).apply_action(
        appointment_id=str(appointment_id),
        action=body.action,
        identity=identity,
        cancellation_reason=body.cancellation_reason,
        doctor_id=str(body.doctor_id) if body.doctor_id else None,
        doctor_id_provided="doctor_id" in body.model_fields_set,
        slot_start=body.slot_start,
        slot_end=body.slot_end,
    )
    return {"ok": True, **result}
