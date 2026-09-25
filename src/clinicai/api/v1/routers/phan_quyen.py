"""Màn phân quyền của quản lý — cấp và thu khối công việc.

Router mỏng: đọc thân, chuyển cho `PermissionService`. **Không gác bằng vai ở
đây**: cửa là capability `permission.manage`, và service tự kiểm — đó chính là
thứ cho phép phòng khám giao việc phân quyền cho một người không mang vai
MANAGEMENT mà không ai phải sửa code.

`GET /phan-quyen/danh-muc` mở cho mọi người đã đăng nhập vì nó chỉ là tên gọi các
khối; màn quản lý cần nó để vẽ. Ai cấp được cho ai thì hai endpoint kia quyết.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from clinicai.api.identity import StaffIdentity, get_current_identity
from clinicai.core.database import get_db_pool
from clinicai.permissions.can import quyen_hieu_luc
from clinicai.permissions.catalogue import KHOI, PRESET, QUYEN, quyen_cua_khoi
from clinicai.services.permission_service import PermissionService

router = APIRouter()


class CapKhoiBody(BaseModel):
    khoi: str = Field(min_length=1, max_length=64)
    #: CLINIC (mặc định) · ROOM · SHIFT — quyền hẹp lại theo phòng hoặc ca.
    scope_type: str = "CLINIC"
    scope_id: UUID | None = None
    #: Hết hạn (ISO) — cấp tạm cho một hôm thì điền.
    valid_until: str | None = None
    ly_do: str | None = Field(default=None, max_length=500)


class ThuKhoiBody(BaseModel):
    khoi: str = Field(min_length=1, max_length=64)
    ly_do: str | None = Field(default=None, max_length=500)


class LegoBody(BaseModel):
    """Bật / tắt một lego (node thanh bên) cho một người."""

    ma: str = Field(min_length=1, max_length=64)
    bat: bool
    #: Lego theo phòng (Phòng dịch vụ): trống = tất cả phòng.
    phong_ids: list[UUID] | None = None


class PresetBody(BaseModel):
    vai: str = Field(min_length=1, max_length=64)


class LuuNhomBody(BaseModel):
    """Nhóm quyền mẫu do quản lý tự đặt."""

    ma: str = Field(min_length=2, max_length=32, pattern=r"^[A-Za-z0-9_]+$")
    ten: str = Field(min_length=1, max_length=120)
    khoi: list[str] = Field(default_factory=list)
    mo_ta: str | None = Field(default=None, max_length=500)


@router.get("/phan-quyen/danh-muc")
async def danh_muc() -> dict[str, Any]:
    """Các khối công việc, quyền con của từng khối, và preset theo vai."""
    return {
        "khoi": [
            {
                "ma": k.ma,
                "ten": k.ten,
                "module": k.module,
                "mo_ta": k.mo_ta,
                "quyen": [
                    {
                        "ma": ma,
                        "ten": QUYEN[ma].ten,
                        "rui_ro": QUYEN[ma].rui_ro.value,
                        "chung_chi_lam_sang": QUYEN[ma].chung_chi_lam_sang,
                    }
                    for ma in quyen_cua_khoi(k.ma)
                ],
            }
            for k in KHOI.values()
        ],
        # Preset chỉ là gợi ý để cấp cho nhanh, không phải trần quyền.
        "preset": {vai: list(khoi) for vai, khoi in PRESET.items()},
    }


@router.get("/phan-quyen/nhom")
async def danh_sach_nhom(
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Nhóm quyền mẫu của phòng khám này — thêm, sửa, xoá được từ màn."""
    return await PermissionService(pool).danh_sach_nhom(identity=identity)


@router.post("/phan-quyen/nhom")
async def luu_nhom(
    body: LuuNhomBody,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Thêm mới hoặc sửa một nhóm. Sửa nhóm KHÔNG đổi quyền của người đã cấp."""
    return await PermissionService(pool).luu_nhom(
        ma=body.ma, ten=body.ten, khoi=body.khoi, mo_ta=body.mo_ta, identity=identity
    )


@router.get("/phan-quyen/man")
async def quyen_theo_man(
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Quyền THEO MÀN (Tuyền chốt 23/09): mỗi nhóm mẫu đang bật màn nào."""
    return await PermissionService(pool).theo_man(identity=identity)


class DoiManBody(BaseModel):
    nhom: str = Field(min_length=1, max_length=64)
    man: str = Field(min_length=1, max_length=64)
    bat: bool


@router.post("/phan-quyen/man")
async def doi_man(
    body: DoiManBody,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Bật/tắt một màn cho một nhóm mẫu (quyền `permission.manage`)."""
    return await PermissionService(pool).doi_man(
        ma_nhom=body.nhom, ma_man=body.man, bat=body.bat, identity=identity
    )


@router.post("/phan-quyen/nhom/{ma}/xoa")
async def xoa_nhom(
    ma: str,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Nhóm dựng sẵn thì tắt, nhóm tự đặt thì xoá hẳn."""
    return await PermissionService(pool).xoa_nhom(ma=ma, identity=identity)


@router.get("/phan-quyen/toi")
async def quyen_cua_toi(
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Màn hình đọc cái này để vẽ thanh bên và ẩn nút.

    Ẩn nút KHÔNG phải bảo mật: mọi lệnh vẫn kiểm lại quyền ở backend.
    """
    async with pool.acquire() as conn:
        return {"quyen": await quyen_hieu_luc(conn, identity)}


@router.get("/phan-quyen/nhan-su/{staff_id}")
async def quyen_cua_nguoi(
    staff_id: UUID,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    return await PermissionService(pool).quyen_cua_nguoi(
        staff_id=str(staff_id), identity=identity
    )


@router.post("/phan-quyen/nhan-su/{staff_id}/cap")
async def cap_khoi(
    staff_id: UUID,
    body: CapKhoiBody,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    return await PermissionService(pool).cap_khoi(
        staff_id=str(staff_id),
        khoi=body.khoi,
        identity=identity,
        scope_type=body.scope_type,
        scope_id=str(body.scope_id) if body.scope_id else None,
        valid_until=body.valid_until,
        ly_do=body.ly_do,
    )


@router.post("/phan-quyen/nhan-su/{staff_id}/thu")
async def thu_khoi(
    staff_id: UUID,
    body: ThuKhoiBody,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    return await PermissionService(pool).thu_khoi(
        staff_id=str(staff_id),
        khoi=body.khoi,
        identity=identity,
        ly_do=body.ly_do,
    )


@router.post("/phan-quyen/nhan-su/{staff_id}/them-preset")
async def them_preset(
    staff_id: UUID,
    body: PresetBody,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Thêm nhanh một nhóm khối theo vai. Vẫn sửa được từng khối sau đó."""
    return await PermissionService(pool).them_preset(
        staff_id=str(staff_id), vai=body.vai, identity=identity
    )


@router.get("/phan-quyen/nhan-su/{staff_id}/lego")
async def lego_cua_nguoi(
    staff_id: UUID,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """21 lego của một người (Tuyền 25/09/2026) — bật / một phần / tắt."""
    return await PermissionService(pool).lego_cua_nguoi(
        staff_id=str(staff_id), identity=identity
    )


@router.post("/phan-quyen/nhan-su/{staff_id}/lego")
async def doi_lego(
    staff_id: UUID,
    body: LegoBody,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Bật / tắt một lego cho một người (+ chọn phòng với Phòng dịch vụ)."""
    return await PermissionService(pool).doi_lego(
        staff_id=str(staff_id),
        ma=body.ma,
        bat=body.bat,
        identity=identity,
        phong_ids=[str(p) for p in body.phong_ids] if body.phong_ids else None,
    )
