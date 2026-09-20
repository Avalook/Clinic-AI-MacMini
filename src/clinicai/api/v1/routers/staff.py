"""FastAPI endpoints for Staff management."""

from typing import Literal
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from clinicai.api.exceptions import NotFoundError, ValidationError
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
from clinicai.schemas.staff import (
    CapabilityRequest,
    StaffCapabilitiesResponse,
    StaffCapabilityDTO,
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
from clinicai.services.audit import record_event
from clinicai.services.staff_service import (
    StaffService,
    add_capability,
    get_staff_capabilities,
    revoke_capability,
)

router = APIRouter()
_STAFF_MANAGEMENT_GUARD = require_role(ClinicRole.MANAGEMENT)


@router.post(
    "/staff",
    response_model=StaffRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_staff(
    data: StaffCreate,
    identity: StaffIdentity = Depends(_STAFF_MANAGEMENT_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> StaffRead:
    """Create a new staff member."""
    service = StaffService(pool, identity.clinic_id, actor=identity)
    try:
        return await service.create_staff(data)
    except CoreValidationError as exc:
        raise ValidationError(exc.message) from exc


@router.get("/staff/{id}", response_model=StaffRead)
async def get_staff_by_id(
    id: UUID,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> StaffRead:
    """Retrieve a staff member by ID."""
    service = StaffService(pool, identity.clinic_id, actor=identity)
    staff = await service.get_by_id(id)
    if staff is None:
        raise NotFoundError(f"Staff {id} not found")
    return staff


@router.get("/staff", response_model=list[StaffRead])
async def list_staff(
    location_id: UUID | None = None,
    assignable: bool = False,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> list[StaffRead]:
    """List active or assignable staff members, optionally filtered by location."""
    service = StaffService(pool, identity.clinic_id, actor=identity)
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
    identity: StaffIdentity = Depends(_STAFF_MANAGEMENT_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> StaffRead:
    """Partially update a staff member."""
    service = StaffService(pool, identity.clinic_id, actor=identity)
    try:
        return await service.update_staff(id, data)
    except CoreResourceNotFoundError as exc:
        raise NotFoundError(exc.message) from exc
    except CoreValidationError as exc:
        raise ValidationError(exc.message) from exc


@router.delete("/staff/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_staff(
    id: UUID,
    identity: StaffIdentity = Depends(_STAFF_MANAGEMENT_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> None:
    """Soft delete (deactivate) a staff member."""
    service = StaffService(pool, identity.clinic_id, actor=identity)
    try:
        await service.deactivate(id)
    except CoreResourceNotFoundError as exc:
        raise NotFoundError(exc.message) from exc


class NhatKyTaiKhoanRequest(BaseModel):
    hanh_dong: Literal["tao", "doi_mat_khau", "doi_ten_dang_nhap", "thu_hoi"]


@router.post("/staff/{id}/nhat-ky-tai-khoan", status_code=201)
async def ghi_nhat_ky_tai_khoan(
    id: UUID,
    body: NhatKyTaiKhoanRequest,
    identity: StaffIdentity = Depends(_STAFF_MANAGEMENT_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, object]:
    """Ghi nhật ký thao tác TÀI KHOẢN ĐĂNG NHẬP của nhân sự (15/09/2026).

    Tạo/đổi mật khẩu/đổi tên đăng nhập/thu hồi chạy ở route Next bằng khoá quản
    trị GoTrue (backend chưa giữ khoá ấy) và trước đây KHÔNG để lại dấu vết nào.
    Route gọi đây sau mỗi thao tác thành công. Không bao giờ nhận mật khẩu.
    """
    from clinicai.services.audit import record_event

    async with pool.acquire() as conn, conn.transaction():
        ten = await conn.fetchval(
            "SELECT s.full_name FROM staff s JOIN clinic_membership m"
            "  ON m.staff_id = s.id AND m.clinic_id = $2::uuid"
            " WHERE s.id = $1::uuid",
            str(id),
            identity.clinic_id,
        )
        if ten is None:
            raise NotFoundError("Không tìm thấy nhân sự này.")
        await record_event(
            conn,
            event_type=f"staff.account_{body.hanh_dong}",
            aggregate_type="staff",
            aggregate_id=str(id),
            identity=identity,
            origin="api:staff-account",
            payload={"staff_id": str(id), "hanh_dong": body.hanh_dong},
        )
    return {"ok": True}


@router.get("/staff/{id}/capabilities", response_model=StaffCapabilitiesResponse)
async def get_staff_capabilities_endpoint(
    id: UUID,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> StaffCapabilitiesResponse:
    """Retrieve capabilities for a staff member in the current clinic."""
    try:
        dtos = await get_staff_capabilities(pool, id, str(identity.clinic_id))
        return StaffCapabilitiesResponse(
            staff_id=id,
            capabilities=[dto.capability for dto in dtos],
        )
    except CoreResourceNotFoundError as exc:
        raise NotFoundError(exc.message) from exc


@router.post(
    "/staff/{id}/capabilities",
    response_model=StaffCapabilityDTO,
    status_code=status.HTTP_201_CREATED,
)
async def grant_staff_capability(
    id: UUID,
    body: CapabilityRequest,
    identity: StaffIdentity = Depends(_STAFF_MANAGEMENT_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> StaffCapabilityDTO:
    """Grant a capability to a staff member (MANAGEMENT only)."""
    if str(identity.staff_id) == str(id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Quản lý không được tự cấp quyền cho chính mình.",
        )
    try:
        dto = await add_capability(
            pool,
            staff_id=id,
            capability=body.capability,
            clinic_id=str(identity.clinic_id),
            proficiency_level=body.proficiency_level,
        )
    except CoreResourceNotFoundError as exc:
        raise NotFoundError(exc.message) from exc

    async with pool.acquire() as conn:
        await record_event(
            conn,
            event_type="staff.capability_granted",
            aggregate_type="staff",
            aggregate_id=str(id),
            identity=identity,
            origin="api:staff-capability",
            payload={"staff_id": str(id), "capability": body.capability},
        )
    return dto


async def _do_revoke_capability(
    id: UUID,
    capability: str,
    identity: StaffIdentity,
    pool: asyncpg.Pool,
) -> None:
    if str(identity.staff_id) == str(id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Quản lý không được tự thu hồi quyền của chính mình.",
        )
    try:
        await revoke_capability(
            pool,
            staff_id=id,
            capability=capability,
            clinic_id=str(identity.clinic_id),
        )
    except CoreResourceNotFoundError as exc:
        raise NotFoundError(exc.message) from exc

    async with pool.acquire() as conn:
        await record_event(
            conn,
            event_type="staff.capability_revoked",
            aggregate_type="staff",
            aggregate_id=str(id),
            identity=identity,
            origin="api:staff-capability",
            payload={"staff_id": str(id), "capability": capability},
        )


@router.delete(
    "/staff/{id}/capabilities/{capability:path}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def revoke_staff_capability_path(
    id: UUID,
    capability: str,
    identity: StaffIdentity = Depends(_STAFF_MANAGEMENT_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> None:
    """Revoke a capability from a staff member via path parameter (MANAGEMENT only)."""
    await _do_revoke_capability(id, capability, identity, pool)


@router.delete(
    "/staff/{id}/capabilities",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def revoke_staff_capability_query(
    id: UUID,
    capability: str = Query(...),
    identity: StaffIdentity = Depends(_STAFF_MANAGEMENT_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> None:
    """Revoke a capability from a staff member via query parameter (MANAGEMENT only)."""
    await _do_revoke_capability(id, capability, identity, pool)
