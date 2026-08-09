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

from clinicai.api.exceptions import ConflictError, NotFoundError
from clinicai.api.idempotency import IdempotencyGuard, idempotency_guard
from clinicai.api.identity import (
    ClinicRole,
    StaffIdentity,
    get_current_identity,
    require_role,
)
from clinicai.core.clock import CLINIC_TZ
from clinicai.core.database import get_db_pool
from clinicai.services.booking_service import INTAKE_ROLES, Action, BookingService
from clinicai.services.capacity_service import CapacityService
from clinicai.services.clinic_policy import (
    load_clinic_policy,
    load_effective_policy,
)
from clinicai.services.slot_hold_service import SlotHoldService

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
    #: Bắt buộc khi action = "cancel"; BookingService từ chối nếu thiếu. Khai
    #: Optional ở đây vì cùng một thân yêu cầu phục vụ tám hành động khác nhau.
    ly_do_huy_ma: str | None = Field(default=None, max_length=32)
    # An absent doctor_id means "leave it"; an explicit null means "unassign".
    doctor_id: UUID | None = None
    slot_start: datetime | None = None
    slot_end: datetime | None = None


@router.get("/appointments/cho-xep-bac-si")
async def cho_xep_bac_si(
    identity: StaffIdentity = Depends(_ACTION_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Lịch đã đặt mà CHƯA CÓ BÁC SĨ — hàng chờ để quản lý xếp người.

    "Đang chờ" = `doctor_id IS NULL`, không phải một trạng thái mới. Tám giá trị
    của `appointment.status` được cả hệ thống lọc theo; một giá trị thứ chín sẽ
    rơi im lặng qua mọi bộ lọc — biến mất khỏi màn này, hiện nhầm ở màn kia.
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT a.id::text,
                   a.slot_start,
                   a.status,
                   a.notes,
                   p.full_name   AS benh_nhan,
                   p.patient_code,
                   p.phone_primary,
                   st.name       AS dich_vu,
                   -- Tuần của lịch này đã được quản lý chốt chưa: xếp bác sĩ
                   -- cho một tuần chưa chốt là xếp dựa trên bản nháp.
                   EXISTS (
                     SELECT 1
                       FROM roster_week rw,
                            LATERAL (
                              SELECT (a.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh')
                                     ::date AS d
                            ) v
                      WHERE rw.clinic_id = a.clinic_id
                        AND rw.week_start =
                            v.d - (extract(isodow FROM v.d)::int - 1)
                   ) AS tuan_da_chot
              FROM appointment a
              LEFT JOIN patient p ON p.clinic_patient_id = a.clinic_patient_id
              LEFT JOIN service_type st ON st.id = a.service_type_id
             WHERE a.clinic_id = $1::uuid
               AND a.doctor_id IS NULL
               AND a.status NOT IN ('CANCELLED', 'NO_SHOW', 'DOCTOR_DECLINED',
                                    'COMPLETED')
             ORDER BY a.slot_start
             LIMIT 500
            """,
            identity.clinic_id,
        )
    return {"items": [dict(r) for r in rows]}


class BaoXepBacSiRequest(BaseModel):
    ghi_chu: str | None = Field(default=None, max_length=500)


@router.post("/appointments/{appointment_id}/bao-xep-bac-si", status_code=201)
async def bao_xep_bac_si(
    appointment_id: UUID,
    body: BaoXepBacSiRequest,
    identity: StaffIdentity = Depends(_BOOKING_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """CSKH báo quản lý rằng lịch này cần xếp bác sĩ.

    Cửa RIÊNG chứ không mở rộng `/dispatch/alerts/call`: cửa ấy gác bằng vai
    điều phối, và nới nó ra cho CSKH nghĩa là CSKH gọi được mọi bộ phận. Ở đây
    chỉ có đúng một việc, gửi tới đúng một vai.
    """
    from clinicai.services.thong_bao_service import ThongBaoService

    async with pool.acquire() as conn:
        appt = await conn.fetchrow(
            """
            SELECT a.slot_start, a.doctor_id, p.full_name, p.patient_code
              FROM appointment a
              LEFT JOIN patient p ON p.clinic_patient_id = a.clinic_patient_id
             WHERE a.id = $1::uuid AND a.clinic_id = $2::uuid
            """,
            str(appointment_id),
            identity.clinic_id,
        )
    if appt is None:
        raise NotFoundError("Không tìm thấy lịch hẹn này.")
    if appt["doctor_id"] is not None:
        # Báo một lịch đã có bác sĩ là làm phiền quản lý vì việc đã xong.
        raise ConflictError("Lịch này đã có bác sĩ rồi.")

    ghi_chu = (body.ghi_chu or "").strip()
    luc = appt["slot_start"].astimezone(CLINIC_TZ).strftime("%H:%M %d/%m/%Y")
    ten = appt["full_name"] or appt["patient_code"] or "Khách"
    return await ThongBaoService(pool).goi(
        identity=identity,
        vai_nhan=ClinicRole.MANAGEMENT.value,
        tieu_de=f"Cần xếp bác sĩ: {ten}",
        noi_dung=(
            f"{ten} đã đặt lịch {luc} nhưng chưa có bác sĩ."
            + (f" Ghi chú: {ghi_chu}" if ghi_chu else "")
        ),
        # Cùng lịch hẹn + chưa ai xử lý → không tạo thông báo thứ hai. CSKH bấm
        # lại vì sốt ruột là chuyện thường; nhân đôi thông báo thì không.
        nguon_id=str(appointment_id),
        muc_do="THUONG",
        duong_dan="/appointments/cho-xep-bac-si",
    )


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
    statuses: str | None = None,
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

    ``statuses`` (danh sách ngăn cách dấu phẩy) để trống = MỌI trạng thái, kể
    cả lịch đã huỷ. Mặc định đó là CỐ Ý và phải giữ: bảng bác sĩ hiện cả lịch
    huỷ để bác sĩ biết ai đã rút — đặt một mặc định khác ở đây là làm biến mất
    những dòng đó mà không một thông báo nào.
    """
    from clinicai.services.doctor_board_service import DoctorBoardService

    loc = [s.strip() for s in (statuses or "").split(",") if s.strip()] or None
    items = await DoctorBoardService(pool).board(
        clinic_id=identity.clinic_id,
        start=start,
        end=end,
        doctor_id=str(doctor_id) if doctor_id else None,
        statuses=loc,
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
        ly_do_huy_ma=body.ly_do_huy_ma,
        doctor_id=str(body.doctor_id) if body.doctor_id else None,
        doctor_id_provided="doctor_id" in body.model_fields_set,
        slot_start=body.slot_start,
        slot_end=body.slot_end,
    )
    return {"ok": True, **result}


class SlotHoldRequest(BaseModel):
    """Giữ một khung giờ trong lúc CSKH còn đang điền form."""

    slot_start: datetime
    slot_end: datetime
    doctor_id: UUID | None = None
    # KHÁCH ĐANG ĐƯỢC CHỌN, để nhật ký thao tác gọi được tên người.
    #
    # Chỗ giữ bản thân nó là cặp (bác sĩ, khung giờ) — nó KHÔNG cần biết khách
    # là ai và không lưu vào bảng. Nhưng dòng nhật ký sinh ra từ nó thì cần:
    # thiếu trường này, `/audit-log` không tra được ai và in ra
    # "slot_hold · 938d4f94". Tuỳ chọn: giữ chỗ vẫn chạy khi chưa chọn khách.
    clinic_patient_id: UUID | None = None


@router.post("/appointments/slot-hold", status_code=201)
async def hold_slot(
    body: SlotHoldRequest,
    identity: StaffIdentity = Depends(_BOOKING_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Báo cho CSKH khác biết khung này đang có người chọn.

    Tư vấn, không phải khoá: chốt chặn sức chứa thật vẫn là trigger lúc đặt
    lịch. Hết hạn sau 10 phút mà không cần ai dọn.
    """
    return await SlotHoldService(pool).hold(
        identity=identity,
        slot_start=body.slot_start,
        slot_end=body.slot_end,
        doctor_id=str(body.doctor_id) if body.doctor_id else None,
        clinic_patient_id=(
            str(body.clinic_patient_id) if body.clinic_patient_id else None
        ),
    )


@router.delete("/appointments/slot-hold")
async def release_slot(
    identity: StaffIdentity = Depends(_BOOKING_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Bỏ chọn, hoặc rời màn hình — thả mọi chỗ người này đang giữ."""
    return await SlotHoldService(pool).release(identity=identity)


@router.get("/appointments/slot-hold")
async def list_slot_holds(
    date: str,
    identity: StaffIdentity = Depends(_BOOKING_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Chỗ NGƯỜI KHÁC đang giữ trong ngày, để lưới tô đúng ô."""
    return {"items": await SlotHoldService(pool).active(identity=identity, date=date)}


@router.get("/appointments/ly-do-huy")
async def ly_do_huy(
    identity: StaffIdentity = Depends(_ACTION_GUARD),
) -> dict[str, Any]:
    """Danh mục lý do huỷ. Một nguồn cho mọi màn có nút huỷ."""
    from clinicai.services.booking_service import LY_DO_HUY

    return {"items": [{"ma": k, "nhan": v} for k, v in LY_DO_HUY.items()]}
