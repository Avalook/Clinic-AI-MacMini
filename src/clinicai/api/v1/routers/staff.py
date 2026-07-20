"""FastAPI endpoints for Staff management."""

from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, status

from clinicai.api.exceptions import NotFoundError, ValidationError
from clinicai.core.database import get_db_pool
from clinicai.core.exceptions import (
    ResourceNotFoundError as CoreResourceNotFoundError,
)
from clinicai.core.exceptions import (
    ValidationError as CoreValidationError,
)
from clinicai.schemas.staff import (
    StaffCreateDTO as StaffCreate,
)
from clinicai.schemas.staff import (
    StaffDTO as StaffRead,
)
from clinicai.schemas.staff import (
    StaffUpdateDTO as StaffUpdate,
)
from clinicai.services.staff_service import StaffService

router = APIRouter()


@router.post(
    "/staff",
    response_model=StaffRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_staff(
    data: StaffCreate,
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> StaffRead:
    """Create a new staff member."""
    service = StaffService(pool)
    try:
        return await service.create_staff(data)
    except CoreValidationError as exc:
        raise ValidationError(exc.message) from exc


@router.get("/staff/{id}", response_model=StaffRead)
async def get_staff_by_id(
    id: UUID,
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> StaffRead:
    """Retrieve a staff member by ID."""
    service = StaffService(pool)
    staff = await service.get_by_id(id)
    if staff is None:
        raise NotFoundError(f"Staff {id} not found")
    return staff


@router.get("/staff", response_model=list[StaffRead])
async def list_staff(
    location_id: UUID | None = None,
    assignable: bool = False,
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> list[StaffRead]:
    """List active or assignable staff members, optionally filtered by location."""
    service = StaffService(pool)
    if assignable:
        staff_list = await service.list_assignable()
        if location_id is not None:
            staff_list = [s for s in staff_list if s.primary_location_id == location_id]
        return staff_list
    else:
        return await service.list_active(location_id)


@router.patch("/staff/{id}", response_model=StaffRead)
async def update_staff(
    id: UUID,
    data: StaffUpdate,
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> StaffRead:
    """Partially update a staff member."""
    service = StaffService(pool)
    try:
        return await service.update_staff(id, data)
    except CoreResourceNotFoundError as exc:
        raise NotFoundError(exc.message) from exc
    except CoreValidationError as exc:
        raise ValidationError(exc.message) from exc


@router.delete("/staff/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_staff(
    id: UUID,
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> None:
    """Soft delete (deactivate) a staff member."""
    service = StaffService(pool)
    try:
        await service.deactivate(id)
    except CoreResourceNotFoundError as exc:
        raise NotFoundError(exc.message) from exc
