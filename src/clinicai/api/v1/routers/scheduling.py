"""FastAPI endpoints for WorkSession and Appointment scheduling."""

import datetime
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, status
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


@router.get(
    "/appointments/{id}",
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
