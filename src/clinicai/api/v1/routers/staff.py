"""FastAPI endpoints for Staff management."""

from typing import Literal
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel

from clinicai.api.exceptions import NotFoundError, ValidationError
from clinicai.api.identity import (
    StaffIdentity,
    get_current_identity,
)
from clinicai.api.nghi_huu import bao_da_nghi
from clinicai.core.database import get_db_pool
from clinicai.core.exceptions import (
    ResourceNotFoundError as CoreResourceNotFoundError,
)
from clinicai.core.exceptions import (
    ValidationError as CoreValidationError,
)
from clinicai.permissions.cua_quyen import cua_quyen
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
# Lego 19 "Nhân sự & phân quyền" (Tuyền 25/09/2026): hỏi QUYỀN, không hỏi vai —
# thu lego là mất quyền thêm nhân sự / tạo tài khoản / đặt lại mật khẩu ngay.
_STAFF_MANAGEMENT_GUARD = cua_quyen("staff.manage")
_TAI_KHOAN_GUARD = cua_quyen("account.manage")


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


# ── Đọc nhẹ cho màn đặt lịch / lịch trực (24/09/2026) ─────────────────────
# Hai helper giao diện (`lib/doctors-server.ts`, `lib/roster-names.ts`) từng đọc
# thẳng bảng `staff` bằng Supabase. Khai TRƯỚC `/staff/{id}`: đường ấy nuốt mọi
# chữ đứng sau `/staff/` rồi đòi UUID.


@router.get("/staff/bac-si-dat-duoc")
async def bac_si_dat_duoc(
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> list[dict[str, str | None]]:
    """Bác sĩ nhận được lịch hẹn (DOCTOR, ULTRASOUND_DOCTOR) đang làm, theo tên."""
    rows = await pool.fetch(
        """
        SELECT DISTINCT s.id::text AS id, s.full_name
          FROM staff s
          JOIN clinic_membership m ON m.staff_id = s.id AND m.is_active
         WHERE m.clinic_id = $1::uuid AND s.is_active
           AND m.role IN ('DOCTOR', 'ULTRASOUND_DOCTOR')
         ORDER BY s.full_name
        """,
        identity.clinic_id,
    )
    return [dict(r) for r in rows]


@router.get("/staff/tai-khoan")
async def danh_sach_tai_khoan(
    identity: StaffIdentity = Depends(_TAI_KHOAN_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> list[dict[str, object]]:
    """Nhân sự + đã nối tài khoản đăng nhập chưa — màn Thiết lập tài khoản /
    Thêm tài khoản (Quản lý). Trước đọc thẳng `staff` bằng Supabase (24/09)."""
    rows = await pool.fetch(
        """
        SELECT DISTINCT s.id::text AS id, s.full_name, s.short_name,
               s.primary_department, s.employment_type, s.is_active,
               s.auth_user_id::text AS auth_user_id
          FROM staff s
          JOIN clinic_membership m ON m.staff_id = s.id
         WHERE m.clinic_id = $1::uuid
         ORDER BY s.primary_department, s.full_name
        """,
        identity.clinic_id,
    )
    return [dict(r) for r in rows]


@router.get("/staff/ten")
async def ten_nhan_vien(
    ids: list[UUID] = Query(default_factory=list, max_length=500),
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, str]:
    """Tên chuẩn theo mã nhân viên (cùng phòng khám) — ghép tên lịch trực."""
    if not ids:
        return {}
    rows = await pool.fetch(
        """
        SELECT s.id::text AS id, s.full_name
          FROM staff s
          JOIN clinic_membership m ON m.staff_id = s.id
         WHERE m.clinic_id = $1::uuid AND s.id = ANY($2::uuid[])
        """,
        identity.clinic_id,
        [str(x) for x in ids],
    )
    return {r["id"]: r["full_name"] for r in rows if r["full_name"]}


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
    identity: StaffIdentity = Depends(_TAI_KHOAN_GUARD),
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
        nhan_su_id=id,
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
        nhan_su_id=id,
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
        nhan_su_id=id,
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
        nhan_su_id=id,
    )
