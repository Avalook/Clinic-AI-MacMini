"""FastAPI endpoints for WorkSession and Appointment scheduling."""

import datetime
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel

from clinicai.api.exceptions import ConflictError, NotFoundError, ValidationError
from clinicai.api.identity import (
    ClinicRole,
    StaffIdentity,
    get_current_identity,
    require_role,
)
from clinicai.core.database import get_db_pool
from clinicai.core.exceptions import (
    ResourceNotFoundError as CoreResourceNotFoundError,
)
from clinicai.core.exceptions import (
    ValidationError as CoreValidationError,
)
from clinicai.schemas.scheduling import (
    AppointmentDTO as AppointmentRead,
)
from clinicai.schemas.scheduling import (
    WorkSessionCreateDTO as WorkSessionCreate,
)
from clinicai.schemas.scheduling import (
    WorkSessionDTO,
    WorkSessionStaffAssignDTO,
)
from clinicai.services.scheduling_service import SchedulingService

# Work-session administration is an operations function. Self-service roster
# registration lives in config.py; this legacy surface may only be used by the
# manager or shift lead.
_WORK_SESSION_ADMIN_GUARD = require_role(
    ClinicRole.MANAGEMENT,
    ClinicRole.TRUONG_CA,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Extra Schemas
# ---------------------------------------------------------------------------


class WorkSessionStaffWithDetails(BaseModel):
    """Staff assignment with full staff details."""

    id: UUID
    work_session_id: UUID
    staff_id: UUID
    role: str
    station: str
    on_call_flag: bool
    is_training: bool
    created_at: datetime.datetime
    full_name: str
    primary_department: str


class WorkSessionWithStaffRead(BaseModel):
    """Work session details with the list of assigned staff."""

    session: WorkSessionDTO
    staff: list[WorkSessionStaffWithDetails]


class WorkSessionStaffAssign(BaseModel):
    """Input body schema for assigning staff to a work session."""

    staff_id: UUID
    role: str
    station: str
    on_call_flag: bool = False


# ---------------------------------------------------------------------------
# Work Session Endpoints
# ---------------------------------------------------------------------------


class WorkSessionListItem(BaseModel):
    """Một dòng trên màn Ca trực — chỉ những gì màn ấy vẽ.

    KHÔNG trả nguyên hàng work_session. Trang này chỉ đọc và chỉ hiện bảy cột;
    trả thừa là mở rộng bề mặt dữ liệu ra ngoài mà không ai dùng tới.
    """

    id: UUID
    location_id: UUID | None
    location_name: str | None
    session_date: datetime.date
    session_type: str
    start_time: datetime.time
    end_time: datetime.time
    max_patients: int | None
    staff_count: int


@router.get("/work-sessions", response_model=list[WorkSessionListItem])
async def list_work_sessions(
    limit: int = Query(100, ge=1, le=500),
    identity: StaffIdentity = Depends(_WORK_SESSION_ADMIN_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> list[WorkSessionListItem]:
    """Ca trực gần nhất của phòng khám đang đăng nhập.

    Trang /work-sessions vốn đọc thẳng bảng qua PostgREST — sổ bàn giao ghi nó
    như một việc còn treo ("có trang nhưng nó không gọi API này"). Endpoint này
    là nửa còn thiếu.
    """
    rows = await SchedulingService(pool, identity.clinic_id).list_work_sessions(
        limit=limit
    )
    return [WorkSessionListItem(**r) for r in rows]


@router.post(
    "/work-sessions",
    response_model=WorkSessionDTO,
    status_code=status.HTTP_201_CREATED,
)
async def create_work_session(
    data: WorkSessionCreate,
    identity: StaffIdentity = Depends(_WORK_SESSION_ADMIN_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> WorkSessionDTO:
    """Create a new work session."""
    service = SchedulingService(pool, identity.clinic_id)
    try:
        return await service.create_work_session(data)
    except CoreValidationError as exc:
        raise ConflictError(exc.message) from exc


@router.get(
    "/work-sessions/{id}",
    response_model=WorkSessionWithStaffRead,
)
async def get_work_session_by_id(
    id: UUID,
    identity: StaffIdentity = Depends(_WORK_SESSION_ADMIN_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> WorkSessionWithStaffRead:
    """Retrieve a work session and its assigned staff list."""
    service = SchedulingService(pool, identity.clinic_id)
    try:
        data = await service.get_session_with_staff(id)
        return WorkSessionWithStaffRead.model_validate(data)
    except CoreResourceNotFoundError as exc:
        raise NotFoundError(exc.message) from exc


@router.post(
    "/work-sessions/{id}/staff",
    response_model=WorkSessionWithStaffRead,
    status_code=status.HTTP_201_CREATED,
)
async def assign_staff_to_session(
    id: UUID,
    body: WorkSessionStaffAssign,
    identity: StaffIdentity = Depends(_WORK_SESSION_ADMIN_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> WorkSessionWithStaffRead:
    """Assign a staff member to a work session."""
    service = SchedulingService(pool, identity.clinic_id)
    dto = WorkSessionStaffAssignDTO(
        work_session_id=id,
        staff_id=body.staff_id,
        role=body.role,
        station=body.station,
        on_call_flag=body.on_call_flag,
    )
    try:
        await service.assign_staff_to_session(dto)
        data = await service.get_session_with_staff(id)
        return WorkSessionWithStaffRead.model_validate(data)
    except CoreResourceNotFoundError as exc:
        raise NotFoundError(exc.message) from exc
    except CoreValidationError as exc:
        raise ValidationError(exc.message) from exc
    except asyncpg.UniqueViolationError as exc:
        raise ConflictError(
            "Staff is already assigned to this work session and station"
        ) from exc


# ---------------------------------------------------------------------------
# Appointment Endpoints
# ---------------------------------------------------------------------------


# `{id:uuid}`, KHÔNG PHẢI `{id}` — và đây là một lỗi đã im lặng rất lâu.
#
# Route này đăng ký TRƯỚC booking_router (xem thứ tự include_router ở main.py),
# nên với `{id}` trần nó nuốt luôn hai đường anh em của nó:
#
#     GET /api/v1/appointments/policy   → id = "policy" → 422
#     GET /api/v1/appointments/quote    → id = "quote"  → 422
#
# Starlette so khớp theo MẪU ĐƯỜNG DẪN, không theo kiểu. `{id}` khớp mọi chuỗi,
# rồi FastAPI mới validate UUID và trả 422 — nó KHÔNG rơi xuống route kế tiếp.
# Nên hai endpoint kia chưa bao giờ chạy được, dù chúng tồn tại và có test.
#
# Không ai thấy vì phía trình duyệt có `?? 15` / `?? 3`: getBookingPolicy() trả
# null, các màn lặng lẽ dùng con số viết cứng, và lưới vẫn vẽ ra một thứ trông
# hợp lý. Bỏ mấy cái mặc định đó đi thì lỗi lộ ra ngay lập tức.
#
# Bộ chuyển đổi `:uuid` bắt Starlette chỉ khớp khi đoạn đường dẫn THẬT SỰ là
# UUID; "policy" không khớp và request đi tiếp tới đúng route của nó. Sửa bằng
# cách đổi thứ tự include_router cũng chạy, nhưng nó biến một lỗi 422 thành thứ
# phụ thuộc vào thứ tự vài dòng ở file khác — kiểu ràng buộc vô hình mà chính
# lỗi này là ví dụ.
@router.get(
    "/appointments/{id:uuid}",
    response_model=AppointmentRead,
)
async def get_appointment_by_id(
    id: UUID,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> AppointmentRead:
    """Retrieve an appointment by ID."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM appointment WHERE id = $1 AND clinic_id = $2::uuid;",
            id,
            identity.clinic_id,
        )
    if row is None:
        raise NotFoundError(f"Appointment {id} not found")
    return AppointmentRead.model_validate(dict(row))
