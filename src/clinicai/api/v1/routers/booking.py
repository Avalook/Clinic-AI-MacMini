"""Appointment booking and lifecycle endpoints (W5, ADR-0012).
Các endpoint đặt lịch hẹn và vòng đời lịch hẹn (W5, ADR-0012).

The router admits every role that can issue *some* action; which role may issue
*which* action is part of the transition table, so it lives beside the rest of
the state machine rather than being split across a decorator.
Router cho phép mọi vai trò có thể thực hiện *một số* hành động; vai trò nào
được thực hiện *hành động nào* là một phần của bảng chuyển trạng thái, nên nó
nằm cạnh phần còn lại của state machine thay vì bị tách ra qua decorator.
"""

# Cho phép sử dụng cú pháp type hint hiện đại (Python 3.10+)
from __future__ import annotations

# Nhập lớp date từ module datetime (đổi tên thành date_cls để tránh xung đột)
from datetime import date as date_cls
# Nhập lớp datetime từ module datetime
from datetime import datetime
# Nhập kiểu Any từ typing để dùng cho các giá trị không xác định kiểu
from typing import Any
# Nhập kiểu UUID từ module uuid để xử lý ID dạng UUID
from uuid import UUID

# Nhập thư viện asyncpg để kết nối PostgreSQL bất đồng bộ
import asyncpg
# Nhập APIRouter và Depends từ FastAPI để tạo router và dependency injection
from fastapi import APIRouter, Depends
# Nhập BaseModel và Field từ Pydantic để định nghĩa schema dữ liệu
from pydantic import BaseModel, Field

# Nhập IdempotencyGuard và idempotency_guard để chống trùng lặp request
from clinicai.api.idempotency import IdempotencyGuard, idempotency_guard
# Nhập các lớp và hàm xác thực danh tính
from clinicai.api.identity import (
    ClinicRole, # Kiểu dữ liệu vai trò phòng khám
    StaffIdentity, # Kiểu dữ liệu danh tính nhân viên
    get_current_identity, # Hàm lấy danh tính hiện tại
    require_role, # Hàm yêu cầu vai trò cụ thể
)
# Nhập hàm lấy connection pool từ database
from clinicai.core.database import get_db_pool
# Nhập INTAKE_ROLES, Action, BookingService từ booking_service
from clinicai.services.booking_service import INTAKE_ROLES, Action, BookingService
# Nhập CapacityService từ capacity_service
from clinicai.services.capacity_service import CapacityService
# Nhập các hàm tải chính sách phòng khám
from clinicai.services.clinic_policy import (
    load_clinic_policy, # Hàm tải chính sách mặc định của phòng khám
    load_effective_policy, # Hàm tải chính sách hiệu lực (3-tier resolve)
)
# Nhập SlotHoldService từ slot_hold_service
from clinicai.services.slot_hold_service import SlotHoldService

# Tạo router FastAPI cho các endpoint đặt lịch
router = APIRouter()

# Booking is intake work.
# Đặt lịch là công việc tiếp nhận.
# Guard yêu cầu vai trò thuộc INTAKE_ROLES (các vai trò được phép đặt lịch)
_BOOKING_GUARD = require_role(*INTAKE_ROLES)
# Any role that appears in the transition table may reach the action endpoint;
# the table then decides. Cashiers never move an appointment.
# Mọi vai trò xuất hiện trong bảng chuyển trạng thái đều có thể truy cập endpoint
# hành động; bảng sau đó quyết định. Thu ngân không bao giờ thay đổi lịch hẹn.
# Guard yêu cầu một trong các vai trò được phép thực hiện hành động trên lịch hẹn
_ACTION_GUARD = require_role(
    ClinicRole.DOCTOR, # Bác sĩ
    ClinicRole.ULTRASOUND_DOCTOR, # Bác sĩ siêu âm
    ClinicRole.TKYK, # Thư ký y khoa
    ClinicRole.NURSE_ULTRASOUND, # Điều dưỡng siêu âm
    ClinicRole.RECEPTION, # Lễ tân
    ClinicRole.CSKH, # Chăm sóc khách hàng
    ClinicRole.TRUONG_CA, # Trưởng ca
    ClinicRole.MANAGEMENT, # Quản lý
)


# Định nghĩa schema dữ liệu cho request đặt lịch
class BookingRequest(BaseModel):
    clinic_patient_id: UUID  # ID bệnh nhân phòng khám
    service_type_id: UUID  # ID loại dịch vụ
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
    location_id: UUID | None = None  # ID cơ sở, tùy chọn, mặc định là cơ sở của người đặt
    slot_start: datetime  # Thời gian bắt đầu khung giờ
    slot_end: datetime  # Thời gian kết thúc khung giờ
    doctor_id: UUID | None = None  # ID bác sĩ, tùy chọn
    booking_channel: str | None = Field(default=None, max_length=64)  # Kênh đặt lịch, tối đa 64 ký tự
    queue_number: str | None = Field(default=None, max_length=32)  # Số thứ tự, tối đa 32 ký tự
    # Capacity hints. CSKH may override the suggestion, so they are inputs.
    # Gợi ý sức chứa. CSKH có thể ghi đè gợi ý, nên chúng là dữ liệu đầu vào.
    patient_kind: str | None = Field(default=None, max_length=16)  # Loại bệnh nhân, tối đa 16 ký tự
    need_sono: bool | None = None  # Có cần siêu âm không
    thanh_min: int | None = Field(default=None, ge=0, le=600)  # Số phút thanh toán, từ 0-600
    sono_min: int | None = Field(default=None, ge=0, le=600)  # Số phút siêu âm, từ 0-600
    # Ghi chú vận hành của CSKH. Bounded: một ô ghi chú không phải nơi dán bệnh án.
    notes: str | None = Field(default=None, max_length=2000)  # Ghi chú, tối đa 2000 ký tự


# Định nghĩa schema dữ liệu cho request thực hiện hành động trên lịch hẹn
class ActionRequest(BaseModel):
    action: Action  # Hành động cần thực hiện (từ enum Action)
    cancellation_reason: str | None = Field(default=None, max_length=1000)  # Lý do hủy, tối đa 1000 ký tự
    # An absent doctor_id means "leave it"; an explicit null means "unassign".
    # doctor_id vắng mặt nghĩa là "giữ nguyên"; null tường minh nghĩa là "gỡ bác sĩ".
    doctor_id: UUID | None = None  # ID bác sĩ, tùy chọn
    slot_start: datetime | None = None  # Thời gian bắt đầu mới, tùy chọn
    slot_end: datetime | None = None  # Thời gian kết thúc mới, tùy chọn


# Endpoint POST để tạo lịch hẹn mới, trả về status 201 (Created)
@router.post("/appointments/bookings", status_code=201)
async def create_booking(
    body: BookingRequest,  # Dữ liệu request đặt lịch
    identity: StaffIdentity = Depends(_BOOKING_GUARD),  # Danh tính nhân viên (yêu cầu vai trò đặt lịch)
    pool: asyncpg.Pool = Depends(get_db_pool),  # Connection pool database
    idem: IdempotencyGuard = Depends(idempotency_guard),  # Guard chống trùng lặp request
) -> dict[str, Any]:
    """Book an appointment. A retried request must not become two bookings.
    Đặt lịch hẹn. Một request bị gửi lại không được tạo thành hai lịch hẹn."""
    # acquire() returns a NEW guard — IdempotencyGuard is frozen, so not
    # reassigning it silently disables replay protection and then makes
    # save() raise. Matches the payment router.
    # acquire() trả về guard MỚI — IdempotencyGuard là frozen, nên không
    # gán lại sẽ âm thầm tắt bảo vệ chống replay và sau đó làm save() báo lỗi.
    # Giống với payment router.
    idem = await idem.acquire(pool, actor_id=identity.auth_user_id)  # Lấy guard mới với actor_id
    if idem.is_replay:  # Nếu đây là request trùng lặp
        return idem.cached_response  # type: ignore[return-value]  # Trả về response đã cache

    # Gọi BookingService để tạo lịch hẹn
    result = await BookingService(pool).create(
        clinic_patient_id=str(body.clinic_patient_id),  # ID bệnh nhân (chuyển sang chuỗi)
        service_type_id=str(body.service_type_id),  # ID loại dịch vụ (chuyển sang chuỗi)
        location_id=str(body.location_id) if body.location_id else None,  # ID cơ sở hoặc None
        slot_start=body.slot_start,  # Thời gian bắt đầu
        slot_end=body.slot_end,  # Thời gian kết thúc
        identity=identity,  # Danh tính nhân viên
        doctor_id=str(body.doctor_id) if body.doctor_id else None,  # ID bác sĩ hoặc None
        booking_channel=body.booking_channel,  # Kênh đặt lịch
        queue_number=body.queue_number,  # Số thứ tự
        patient_kind=body.patient_kind,  # Loại bệnh nhân
        need_sono=body.need_sono,  # Có cần siêu âm không
        thanh_min=body.thanh_min,  # Số phút thanh toán
        sono_min=body.sono_min,  # Số phút siêu âm
        notes=body.notes,  # Ghi chú
    )
    payload = {"ok": True, **result}  # Tạo payload phản hồi với trạng thái ok
    await idem.save(pool, payload, status_code=201)  # Lưu response vào cache idempotency
    return payload  # Trả về payload


# Endpoint GET để lấy báo giá sức chứa cho UI chọn khung giờ
@router.get("/appointments/quote")
async def capacity_quote(
    date: str,  # Ngày cần báo giá (dạng chuỗi)
    location_id: str | None = None,  # ID cơ sở, tùy chọn
    doctor_id: str | None = None,  # ID bác sĩ, tùy chọn
    identity: StaffIdentity = Depends(_BOOKING_GUARD),  # Danh tính nhân viên (yêu cầu vai trò đặt lịch)
    pool: asyncpg.Pool = Depends(get_db_pool),  # Connection pool database
) -> dict[str, Any]:
    """Read-only capacity quote for the slot picker UI (CAP-01).
    Báo giá sức chứa chỉ-đọc cho UI chọn khung giờ (CAP-01).

    Returns budget + current usage per hour so the UI can colour cells.
    Does NOT decide whether a booking is allowed — that is the DB trigger
    + the pre-check in BookingService.
    Trả về ngân sách + mức sử dụng hiện tại theo giờ để UI tô màu ô.
    KHÔNG quyết định lịch hẹn có được phép hay không — đó là trigger DB
    + kiểm tra trước trong BookingService.

    ``location_id`` là tuỳ chọn, và mặc định là cơ sở của người đang đăng nhập —
    cùng quy tắc mà POST /appointments dùng khi tạo lịch. Bắt buộc nó nghĩa là
    trình duyệt phải ĐOÁN cơ sở, rồi tô màu lưới theo một cơ sở khác với cơ sở
    mà lịch sẽ được ghi vào: lưới nói còn chỗ, trigger từ chối.
    """
    svc = CapacityService(pool)  # Tạo service tính sức chứa
    return await svc.quote(  # Gọi hàm quote để lấy báo giá
        date=date,  # Ngày cần báo giá
        location_id=location_id or identity.location_id,  # ID cơ sở (mặc định là cơ sở của người đăng nhập)
        doctor_id=doctor_id,  # ID bác sĩ
        clinic_id=identity.clinic_id,  # ID phòng khám
    )


# Endpoint GET để lấy lịch hẹn 7 ngày
@router.get("/appointments/week")
async def week_appointments(
    week_start: date_cls,  # Ngày bắt đầu tuần (FastAPI tự phân tích kiểu date)
    identity: StaffIdentity = Depends(get_current_identity),  # Danh tính nhân viên hiện tại
    pool: asyncpg.Pool = Depends(get_db_pool),  # Connection pool database
) -> dict[str, Any]:
    """Lịch hẹn 7 ngày, KÈM phân loại Tái khám / Khám lần đầu.

    Không dùng ``_BOOKING_GUARD``: bảng lịch tuần ở trang chủ hiện cho mọi vai,
    và bác sĩ xem lịch của mình không phải người đặt lịch — cùng lý do với
    ``/appointments/policy`` ngay bên dưới.

    ``week_start`` khai kiểu ``date`` để FastAPI tự phân tích và từ chối chuỗi
    hỏng bằng 422, thay vì để chuỗi đi thẳng xuống asyncpg — đúng cái đã làm
    ``/appointments/quote`` trả 500 suốt (xem capacity_service).
    """
    # Import service bên trong hàm để tránh import vòng
    from clinicai.services.week_appointments_service import (
        WeekAppointmentsService,
    )

    # Gọi service để lấy lịch hẹn tuần
    items = await WeekAppointmentsService(pool).week(
        clinic_id=identity.clinic_id,  # ID phòng khám
        week_start=week_start,  # Ngày bắt đầu tuần
    )
    return {"ok": True, "items": items}  # Trả về danh sách lịch hẹn


# Endpoint GET để lấy bảng khám của bác sĩ
@router.get("/appointments/doctor-board")
async def doctor_board(
    start: datetime,  # Thời gian bắt đầu khoảng cần xem
    end: datetime,  # Thời gian kết thúc khoảng cần xem
    doctor_id: UUID | None = None,  # ID bác sĩ, tùy chọn
    identity: StaffIdentity = Depends(get_current_identity),  # Danh tính nhân viên hiện tại
    pool: asyncpg.Pool = Depends(get_db_pool),  # Connection pool database
) -> dict[str, Any]:
    """Bảng khám: lịch hẹn trong khoảng, kèm phân loại khám và cờ chờ đọc KQ.

    ``doctor_id`` để trống = mọi bác sĩ. Ai được xem lịch của người khác là
    quyết định của màn hình gọi (Lễ tân và TKYK xem toàn phòng khám, bác sĩ chỉ
    xem của mình) — ở đây chỉ chặn theo phòng khám, đúng phạm vi mà RLS cũng
    chặn khi trình duyệt đọc thẳng.

    ``start``/``end`` khai kiểu ``datetime`` để FastAPI phân tích và từ chối
    chuỗi hỏng bằng 422, thay vì để chuỗi rơi xuống asyncpg thành 500.
    """
    # Import service bên trong hàm để tránh import vòng
    from clinicai.services.doctor_board_service import DoctorBoardService

    # Gọi service để lấy bảng khám
    items = await DoctorBoardService(pool).board(
        clinic_id=identity.clinic_id,  # ID phòng khám
        start=start,  # Thời gian bắt đầu
        end=end,  # Thời gian kết thúc
        doctor_id=str(doctor_id) if doctor_id else None,  # ID bác sĩ hoặc None
    )
    return {"ok": True, "items": items}  # Trả về danh sách lịch hẹn


# Endpoint GET để lấy chính sách đặt lịch
@router.get("/appointments/policy")
async def booking_policy(
    doctor_id: str | None = None,  # ID bác sĩ, tùy chọn
    date: str | None = None,  # Ngày, tùy chọn
    identity: StaffIdentity = Depends(get_current_identity),  # Danh tính nhân viên hiện tại
    pool: asyncpg.Pool = Depends(get_db_pool),  # Connection pool database
) -> dict[str, Any]:
    """Độ dài khung và số chỗ, có tính override per-doctor/per-slot (C.4).

    Không dùng ``_BOOKING_GUARD``: bảng lịch tuần ở màn chủ vẽ đúng cái lưới
    này, và bác sĩ xem lịch của mình không phải người đặt lịch. Ba con số này
    không phải dữ liệu bệnh nhân — giấu chúng khỏi một nửa phòng khám chỉ làm
    lưới vẽ sai, không làm ai an toàn hơn.

    Khi ``doctor_id`` và ``date`` được truyền, trả về luật effective (3-tier
    resolve: slot → doctor → clinic). Khi không truyền, trả clinic default.
    """
    # Mở connection từ pool
    async with pool.acquire() as conn:
        # Nếu có doctor_id và date
        if doctor_id and date:
            # Import datetime và CLINIC_TZ
            from datetime import datetime as dt

            from clinicai.core.clock import CLINIC_TZ

            # Build a representative slot_start at noon on the date in VN tz.
            # Tạo slot_start đại diện lúc 12 giờ trưa của ngày đó theo múi giờ VN.
            slot_start = dt.strptime(date, "%Y-%m-%d").replace(
                hour=12, tzinfo=CLINIC_TZ  # Giờ 12, múi giờ phòng khám
            )
            # Tải chính sách hiệu lực (3-tier: slot → doctor → clinic)
            policy = await load_effective_policy(
                conn, identity.clinic_id, doctor_id, slot_start
            )
        else:
            # Tải chính sách mặc định của phòng khám
            policy = await load_clinic_policy(conn, identity.clinic_id)
        # GIỜ MỞ CỬA ĐI CÙNG LUẬT, KHÔNG NẰM TRONG BUNDLE.
        #
        # Trước đây nó là hằng số ở hai file — BookingHub (…–22:00) và
        # lib/roster.ts (…–23:00) — với hai giá trị khác nhau, nên bác sĩ đăng ký
        # được ca 22:00–23:00 mà CSKH không đặt lịch vào được. Và một hằng số
        # trong bundle nghĩa là phòng khám thứ hai không thể có giờ khác.
        # Truy vấn giờ mở cửa từ settings của phòng khám
        hours_rows = await conn.fetch(
            """
            SELECT key::int AS weekday,
                   value ->> 'open'  AS open,
                   value ->> 'close' AS close
              FROM clinic c, jsonb_each(c.settings -> 'hours')
             WHERE c.id = $1::uuid
            """,
            identity.clinic_id,  # ID phòng khám
        )

    return {
        "slot_minutes": policy.slot_minutes,  # Độ dài khung giờ (phút)
        "regular_cap": policy.regular_cap,  # Số chỗ đặt lịch thường
        "walkin_cap": policy.walkin_cap,  # Số chỗ khám trực tiếp
        # {"0": {"open": "08:00", "close": "23:00"}, …} — khoá là thứ, 0=CN.
        # Giờ mở cửa theo từng ngày trong tuần
        "hours": {
            str(r["weekday"]): {"open": r["open"], "close": r["close"]}  # Ngày: giờ mở/đóng
            for r in hours_rows  # Lặp qua từng dòng kết quả
        },
    }


# Endpoint PATCH để thực hiện hành động trên lịch hẹn (chuyển trạng thái)
@router.patch("/appointments/{appointment_id}")
async def apply_appointment_action(
    appointment_id: UUID,  # ID lịch hẹn
    body: ActionRequest,  # Dữ liệu request hành động
    identity: StaffIdentity = Depends(_ACTION_GUARD),  # Danh tính nhân viên (yêu cầu vai trò được phép)
    pool: asyncpg.Pool = Depends(get_db_pool),  # Connection pool database
) -> dict[str, Any]:
    """Move an appointment through its lifecycle.
    Di chuyển lịch hẹn qua vòng đời của nó."""
    # Gọi BookingService để thực hiện hành động
    result = await BookingService(pool).apply_action(
        appointment_id=str(appointment_id),  # ID lịch hẹn (chuyển sang chuỗi)
        action=body.action,  # Hành động cần thực hiện
        identity=identity,  # Danh tính nhân viên
        cancellation_reason=body.cancellation_reason,  # Lý do hủy
        doctor_id=str(body.doctor_id) if body.doctor_id else None,  # ID bác sĩ hoặc None
        doctor_id_provided="doctor_id" in body.model_fields_set,  # Kiểm tra doctor_id có được cung cấp không
        slot_start=body.slot_start,  # Thời gian bắt đầu mới
        slot_end=body.slot_end,  # Thời gian kết thúc mới
    )
    return {"ok": True, **result}  # Trả về kết quả


# Định nghĩa schema dữ liệu cho request giữ khung giờ
class SlotHoldRequest(BaseModel):
    """Giữ một khung giờ trong lúc CSKH còn đang điền form."""

    slot_start: datetime  # Thời gian bắt đầu khung giờ
    slot_end: datetime  # Thời gian kết thúc khung giờ
    doctor_id: UUID | None = None  # ID bác sĩ, tùy chọn


# Endpoint POST để giữ khung giờ
@router.post("/appointments/slot-hold", status_code=201)
async def hold_slot(
    body: SlotHoldRequest,  # Dữ liệu request giữ khung giờ
    identity: StaffIdentity = Depends(_BOOKING_GUARD),  # Danh tính nhân viên (yêu cầu vai trò đặt lịch)
    pool: asyncpg.Pool = Depends(get_db_pool),  # Connection pool database
) -> dict[str, Any]:
    """Báo cho CSKH khác biết khung này đang có người chọn.

    Tư vấn, không phải khoá: chốt chặn sức chứa thật vẫn là trigger lúc đặt
    lịch. Hết hạn sau 10 phút mà không cần ai dọn.
    """
    # Gọi SlotHoldService để giữ khung giờ
    return await SlotHoldService(pool).hold(
        identity=identity,  # Danh tính nhân viên
        slot_start=body.slot_start,  # Thời gian bắt đầu
        slot_end=body.slot_end,  # Thời gian kết thúc
        doctor_id=str(body.doctor_id) if body.doctor_id else None,  # ID bác sĩ hoặc None
    )


# Endpoint DELETE để thả khung giờ đang giữ
@router.delete("/appointments/slot-hold")
async def release_slot(
    identity: StaffIdentity = Depends(_BOOKING_GUARD),  # Danh tính nhân viên (yêu cầu vai trò đặt lịch)
    pool: asyncpg.Pool = Depends(get_db_pool),  # Connection pool database
) -> dict[str, Any]:
    """Bỏ chọn, hoặc rời màn hình — thả mọi chỗ người này đang giữ."""
    # Gọi SlotHoldService để thả mọi khung giờ người này đang giữ
    return await SlotHoldService(pool).release(identity=identity)


# Endpoint GET để liệt kê các khung giờ đang được giữ
@router.get("/appointments/slot-hold")
async def list_slot_holds(
    date: str,  # Ngày cần xem
    identity: StaffIdentity = Depends(_BOOKING_GUARD),  # Danh tính nhân viên (yêu cầu vai trò đặt lịch)
    pool: asyncpg.Pool = Depends(get_db_pool),  # Connection pool database
) -> dict[str, Any]:
    """Chỗ NGƯỜI KHÁC đang giữ trong ngày, để lưới tô đúng ô."""
    # Gọi SlotHoldService để lấy danh sách khung giờ đang được giữ bởi người khác
    return {"items": await SlotHoldService(pool).active(identity=identity, date=date)}