"""Appointment booking and lifecycle endpoints (W5, ADR-0012).

The router admits every role that can issue *some* action; which role may issue
*which* action is part of the transition table, so it lives beside the rest of
the state machine rather than being split across a decorator.
"""

from __future__ import annotations

from datetime import date as date_cls
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
from clinicai.services.clinic_policy import (
    load_clinic_policy,
    load_effective_policy,
)

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
    # TUỲ CHỌN, và mặc định là CƠ SỞ CỦA NGƯỜI ĐẶT.
    #
    # Bắt buộc trường này nghĩa là trình duyệt phải nghĩ ra một cơ sở, và cái nó
    # nghĩ ra là `locations[0].id` — "cơ sở đầu tiên trong danh sách", không phải
    # "nơi buổi khám diễn ra". Lịch rơi vào cơ sở A trong khi lưới sức chứa và
    # ca trực tra ở cơ sở B, không có gì trên màn hình mâu thuẫn với người dùng.
    #
    # identity.location_id là câu trả lời đúng và server đã có sẵn nó
    # (20260803000007 làm staff.primary_location_id NOT NULL). Client vẫn gửi
    # được khi đặt hộ cơ sở khác — nhưng phải NÓI RA, không phải mặc định.
    location_id: UUID | None = None
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
    # Ghi chú vận hành của CSKH. Bounded: một ô ghi chú không phải nơi dán bệnh án.
    notes: str | None = Field(default=None, max_length=2000)


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
        location_id=str(body.location_id) if body.location_id else None,
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
        notes=body.notes,
    )
    payload = {"ok": True, **result}
    await idem.save(pool, payload, status_code=201)
    return payload


@router.get("/appointments/quote")
async def capacity_quote(
    date: str,
    location_id: str | None = None,
    doctor_id: str | None = None,
    identity: StaffIdentity = Depends(_BOOKING_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Read-only capacity quote for the slot picker UI (CAP-01).

    Returns budget + current usage per hour so the UI can colour cells.
    Does NOT decide whether a booking is allowed — that is the DB trigger
    + the pre-check in BookingService.

    ``location_id`` là tuỳ chọn, và mặc định là cơ sở của người đang đăng nhập —
    cùng quy tắc mà POST /appointments dùng khi tạo lịch. Bắt buộc nó nghĩa là
    trình duyệt phải ĐOÁN cơ sở, rồi tô màu lưới theo một cơ sở khác với cơ sở
    mà lịch sẽ được ghi vào: lưới nói còn chỗ, trigger từ chối.
    """
    svc = CapacityService(pool)
    return await svc.quote(
        date=date,
        location_id=location_id or identity.location_id,
        doctor_id=doctor_id,
        clinic_id=identity.clinic_id,
    )


@router.get("/appointments/week")
async def week_appointments(
    week_start: date_cls,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Lịch hẹn 7 ngày, KÈM phân loại Tái khám / Khám lần đầu.

    Không dùng ``_BOOKING_GUARD``: bảng lịch tuần ở trang chủ hiện cho mọi vai,
    và bác sĩ xem lịch của mình không phải người đặt lịch — cùng lý do với
    ``/appointments/policy`` ngay bên dưới.

    ``week_start`` khai kiểu ``date`` để FastAPI tự phân tích và từ chối chuỗi
    hỏng bằng 422, thay vì để chuỗi đi thẳng xuống asyncpg — đúng cái đã làm
    ``/appointments/quote`` trả 500 suốt (xem capacity_service).
    """
    from clinicai.services.week_appointments_service import (
        WeekAppointmentsService,
    )

    items = await WeekAppointmentsService(pool).week(
        clinic_id=identity.clinic_id, week_start=week_start
    )
    return {"ok": True, "items": items}


@router.get("/appointments/doctor-board")
async def doctor_board(
    start: datetime,
    end: datetime,
    doctor_id: UUID | None = None,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Bảng khám: lịch hẹn trong khoảng, kèm phân loại khám và cờ chờ đọc KQ.

    ``doctor_id`` để trống = mọi bác sĩ. Ai được xem lịch của người khác là
    quyết định của màn hình gọi (Lễ tân và TKYK xem toàn phòng khám, bác sĩ chỉ
    xem của mình) — ở đây chỉ chặn theo phòng khám, đúng phạm vi mà RLS cũng
    chặn khi trình duyệt đọc thẳng.

    ``start``/``end`` khai kiểu ``datetime`` để FastAPI phân tích và từ chối
    chuỗi hỏng bằng 422, thay vì để chuỗi rơi xuống asyncpg thành 500.
    """
    from clinicai.services.doctor_board_service import DoctorBoardService

    items = await DoctorBoardService(pool).board(
        clinic_id=identity.clinic_id,
        start=start,
        end=end,
        doctor_id=str(doctor_id) if doctor_id else None,
    )
    return {"ok": True, "items": items}


@router.get("/appointments/policy")
async def booking_policy(
    doctor_id: str | None = None,
    date: str | None = None,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Độ dài khung và số chỗ, có tính override per-doctor/per-slot (C.4).

    Không dùng ``_BOOKING_GUARD``: bảng lịch tuần ở màn chủ vẽ đúng cái lưới
    này, và bác sĩ xem lịch của mình không phải người đặt lịch. Ba con số này
    không phải dữ liệu bệnh nhân — giấu chúng khỏi một nửa phòng khám chỉ làm
    lưới vẽ sai, không làm ai an toàn hơn.

    Khi ``doctor_id`` và ``date`` được truyền, trả về luật effective (3-tier
    resolve: slot → doctor → clinic). Khi không truyền, trả clinic default.
    """
    async with pool.acquire() as conn:
        if doctor_id and date:
            from datetime import datetime as dt

            from clinicai.core.clock import CLINIC_TZ

            # Build a representative slot_start at noon on the date in VN tz.
            slot_start = dt.strptime(date, "%Y-%m-%d").replace(
                hour=12, tzinfo=CLINIC_TZ
            )
            policy = await load_effective_policy(
                conn, identity.clinic_id, doctor_id, slot_start
            )
        else:
            policy = await load_clinic_policy(conn, identity.clinic_id)
        # GIỜ MỞ CỬA ĐI CÙNG LUẬT, KHÔNG NẰM TRONG BUNDLE.
        #
        # Trước đây nó là hằng số ở hai file — BookingHub (…–22:00) và
        # lib/roster.ts (…–23:00) — với hai giá trị khác nhau, nên bác sĩ đăng ký
        # được ca 22:00–23:00 mà CSKH không đặt lịch vào được. Và một hằng số
        # trong bundle nghĩa là phòng khám thứ hai không thể có giờ khác.
        hours_rows = await conn.fetch(
            """
            SELECT key::int AS weekday,
                   value ->> 'open'  AS open,
                   value ->> 'close' AS close
              FROM clinic c, jsonb_each(c.settings -> 'hours')
             WHERE c.id = $1::uuid
            """,
            identity.clinic_id,
        )

    return {
        "slot_minutes": policy.slot_minutes,
        "regular_cap": policy.regular_cap,
        "walkin_cap": policy.walkin_cap,
        # {"0": {"open": "08:00", "close": "23:00"}, …} — khoá là thứ, 0=CN.
        "hours": {
            str(r["weekday"]): {"open": r["open"], "close": r["close"]}
            for r in hours_rows
        },
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
