"""FastAPI endpoints for Staff management."""

from typing import Literal
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel

from clinicai.api.exceptions import NotFoundError, ValidationError
from clinicai.api.identity import (
    ClinicRole,
    StaffIdentity,
    get_current_identity,
    require_role,
)
from clinicai.api.nghi_huu import bao_da_nghi
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
from clinicai.services.audit import record_event
from clinicai.services.staff_service import (
    StaffService,
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


# ── Quyền kiểu cũ (`staff_capability`) — ĐÃ NGHỈ 23/09/2026 ──────────────────
#
# Chỉ còn MỘT hệ quyền: `capability_grant`, quản ở màn Phân quyền. Bốn endpoint
# dưới vẫn trả lời (410, không ghi gì, ghi log người gọi) để biết còn ai dùng
# trước khi xoá hẳn — cùng mẫu với các lối ghi cũ của Slice 1.
QUYEN_O_PHAN_QUYEN = (
    "Quyền nay quản ở màn Phân quyền (/phan-quyen). Xác nhận tệp kết quả là khối"
    " “Xác nhận tệp kết quả”."
)


@router.get("/staff/{id}/capabilities")
async def get_staff_capabilities_endpoint(
    id: UUID,
    identity: StaffIdentity = Depends(get_current_identity),
) -> None:
    """ĐÃ NGHỈ — xem `QUYEN_O_PHAN_QUYEN`."""
    bao_da_nghi(
        endpoint="GET /staff/{id}/capabilities",
        identity=identity,
        thay_bang=QUYEN_O_PHAN_QUYEN,
        staff_id=id,
    )


@router.post("/staff/{id}/capabilities")
async def grant_staff_capability(
    id: UUID,
    identity: StaffIdentity = Depends(_STAFF_MANAGEMENT_GUARD),
) -> None:
    """ĐÃ NGHỈ — xem `QUYEN_O_PHAN_QUYEN`."""
    bao_da_nghi(
        endpoint="POST /staff/{id}/capabilities",
        identity=identity,
        thay_bang=QUYEN_O_PHAN_QUYEN,
        staff_id=id,
    )


@router.delete("/staff/{id}/capabilities/{capability:path}")
async def revoke_staff_capability_path(
    id: UUID,
    capability: str,
    identity: StaffIdentity = Depends(_STAFF_MANAGEMENT_GUARD),
) -> None:
    """ĐÃ NGHỈ — xem `QUYEN_O_PHAN_QUYEN`."""
    bao_da_nghi(
        endpoint="DELETE /staff/{id}/capabilities/{capability}",
        identity=identity,
        thay_bang=QUYEN_O_PHAN_QUYEN,
        staff_id=id,
    )


@router.delete("/staff/{id}/capabilities")
async def revoke_staff_capability_query(
    id: UUID,
    capability: str = Query(...),
    identity: StaffIdentity = Depends(_STAFF_MANAGEMENT_GUARD),
) -> None:
    """ĐÃ NGHỈ — xem `QUYEN_O_PHAN_QUYEN`."""
    bao_da_nghi(
        endpoint="DELETE /staff/{id}/capabilities",
        identity=identity,
        thay_bang=QUYEN_O_PHAN_QUYEN,
        staff_id=id,
    )
