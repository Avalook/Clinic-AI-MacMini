"""FastAPI endpoints for WorkSession and Appointment scheduling."""

import datetime
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel

from clinicai.api.exceptions import ConflictError, NotFoundError, ValidationError
from clinicai.core.database import get_db_pool
from clinicai.core.exceptions import (
    ResourceNotFoundError as CoreResourceNotFoundError,
)
from clinicai.core.exceptions import (
    ValidationError as CoreValidationError,
)
from clinicai.schemas.scheduling import (
    AppointmentCreateDTO as AppointmentCreate,
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


class AppointmentCancelRequest(BaseModel):
    """Input body schema for cancelling an appointment."""

    reason: str | None = None


# ---------------------------------------------------------------------------
# Work Session Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/work-sessions",
    response_model=WorkSessionDTO,
    status_code=status.HTTP_201_CREATED,
)
async def create_work_session(
    data: WorkSessionCreate,
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> WorkSessionDTO:
    """Create a new work session."""
    service = SchedulingService(pool)
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
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> WorkSessionWithStaffRead:
    """Retrieve a work session and its assigned staff list."""
    service = SchedulingService(pool)
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
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> WorkSessionWithStaffRead:
    """Assign a staff member to a work session."""
    service = SchedulingService(pool)
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


@router.post(
    "/appointments",
    response_model=AppointmentRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_appointment(
    data: AppointmentCreate,
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> AppointmentRead:
    """Book a new appointment."""
    service = SchedulingService(pool)
    try:
        return await service.create_appointment(data)
    except CoreValidationError as exc:
        if "Doctor is not assigned" in exc.message:
            raise ConflictError(exc.message) from exc
        raise ValidationError(exc.message) from exc
    except CoreResourceNotFoundError as exc:
        raise NotFoundError(exc.message) from exc


@router.get(
    "/appointments/{id}",
    response_model=AppointmentRead,
)
async def get_appointment_by_id(
    id: UUID,
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> AppointmentRead:
    """Retrieve an appointment by ID."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM appointment WHERE id = $1;", id)
    if row is None:
        raise NotFoundError(f"Appointment {id} not found")
    return AppointmentRead.model_validate(dict(row))


@router.patch(
    "/appointments/{id}/confirm",
    response_model=AppointmentRead,
)
async def confirm_appointment(
    id: UUID,
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> AppointmentRead:
    """Confirm a scheduled appointment."""
    service = SchedulingService(pool)
    try:
        return await service.confirm_appointment(id)
    except CoreResourceNotFoundError as exc:
        raise NotFoundError(exc.message) from exc
    except CoreValidationError as exc:
        raise ValidationError(exc.message) from exc


@router.patch(
    "/appointments/{id}/cancel",
    response_model=AppointmentRead,
)
async def cancel_appointment(
    id: UUID,
    body: AppointmentCancelRequest,
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> AppointmentRead:
    """Cancel a booked appointment with a reason."""
    service = SchedulingService(pool)
    reason = body.reason or "No reason provided"
    try:
        return await service.cancel_appointment(id, reason)
    except CoreResourceNotFoundError as exc:
        raise NotFoundError(exc.message) from exc
    except CoreValidationError as exc:
        raise ValidationError(exc.message) from exc
