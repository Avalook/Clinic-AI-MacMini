"""Cấu hình phòng khám — sơ đồ phòng, tầng, và ai làm được việc gì.

GHI chỉ quản lý. ĐỌC thì tuỳ đọc cái gì:

* Sơ đồ (overview) và dịch vụ (services) mở cho vai vận hành — bảng điều phối
  cần biết phòng nào phục vụ bước nào, màn đặt lịch cần biết dịch vụ nào dùng
  phiếu nào. Đây là cấu trúc chỗ làm việc, không phải hồ sơ của ai.
* DANH SÁCH NHÂN SỰ (staff) CHỈ QUẢN LÝ (Quang chốt 2026-08-06). Nó trả về tên
  từng người kèm việc họ làm được — cùng loại dữ liệu với /api/v1/staff, vốn đã
  chỉ mở cho MANAGEMENT. Trước đây hai đường cùng một loại dữ liệu mà hai mức
  quyền khác nhau, nên khoá cửa này còn đường kia vẫn mở.

Tách quyền ở tầng router thay vì trong một handler: gộp chung thì một lần sửa
nhầm điều kiện là mở luôn quyền đổi sơ đồ phòng khám.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from clinicai.api.identity import (
    ClinicRole,
    StaffIdentity,
    get_current_identity,
    require_role,
)
from clinicai.core.database import get_db_pool
from clinicai.services.clinic_config_service import ClinicConfigService
from clinicai.services.thu_ky_bac_si import dat_bac_si_cho_thu_ky

router = APIRouter()

_WRITE_GUARD = require_role(ClinicRole.MANAGEMENT)
# Cùng mức với _WRITE_GUARD nhưng là hằng RIÊNG: hai câu hỏi khác nhau ("ai đổi
# được sơ đồ" và "ai đọc được danh sách nhân sự") tình cờ cùng đáp án hôm nay.
# Dùng chung một hằng thì ngày nới một bên sẽ nới luôn bên kia mà không ai thấy.
_STAFF_READ_GUARD = require_role(ClinicRole.MANAGEMENT)


@router.get("/clinic-config/overview")
async def overview(
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Cơ sở → tầng → phòng, kèm bước mỗi phòng phục vụ."""
    return await ClinicConfigService(pool).overview(identity=identity)


@router.get("/clinic-config/staff")
async def staff(
    identity: StaffIdentity = Depends(_STAFF_READ_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Ai làm được bước nào — CHỈ QUẢN LÝ, xem docstring đầu file."""
    return await ClinicConfigService(pool).staff(identity=identity)


@router.get("/clinic-config/services")
async def services(
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Dịch vụ khám nào dùng phiếu nào, kèm danh mục phiếu đang bật."""
    return await ClinicConfigService(pool).services(identity=identity)


class ServiceFormRequest(BaseModel):
    service_type_id: UUID
    #: Rỗng = dịch vụ này không có phiếu khám chuyên khoa (thủ thuật, tư vấn).
    form_code: str | None = Field(default=None, max_length=32)
    #: Chỉ khai khi nội dung khám khác nhau theo giới — hôm nay đúng một dịch
    #: vụ: khám tiền hôn nhân (nữ phụ khoa, nam nam khoa).
    form_code_nam: str | None = Field(default=None, max_length=32)


@router.put("/clinic-config/service-form")
async def set_service_form(
    body: ServiceFormRequest,
    identity: StaffIdentity = Depends(_WRITE_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Gán phiếu khám cho một dịch vụ — thay cho việc đoán từ tên."""
    return await ClinicConfigService(pool).set_service_form(
        identity=identity,
        service_type_id=str(body.service_type_id),
        form_code=body.form_code,
        form_code_nam=body.form_code_nam,
    )


class RoomFloorRequest(BaseModel):
    room_id: UUID
    #: Nhãn tự do: "1", "Trệt", "B1", "Tòa A – T5". Rỗng = chưa khai.
    floor: str | None = Field(default=None, max_length=40)


@router.put("/clinic-config/room-floor")
async def set_room_floor(
    body: RoomFloorRequest,
    identity: StaffIdentity = Depends(_WRITE_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Đặt tầng cho một phòng."""
    return await ClinicConfigService(pool).set_room_floor(
        identity=identity, room_id=str(body.room_id), floor=body.floor
    )


# ── Phòng là tài nguyên (CORE-C, 23/09/2026): định danh = room_id ──────────
class RoomCreateRequest(BaseModel):
    location_id: UUID
    name: str = Field(min_length=1, max_length=80)
    #: Bước chính — "phòng này làm việc gì". Thêm bước khác ở room-nodes.
    node_code: str = Field(min_length=1, max_length=64)
    floor: str | None = Field(default=None, max_length=40)


@router.post("/clinic-config/rooms")
async def create_room(
    body: RoomCreateRequest,
    identity: StaffIdentity = Depends(_WRITE_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Thêm phòng. Tên tự do; mã nội bộ tự sinh, không ai phải gõ."""
    return await ClinicConfigService(pool).create_room(
        identity=identity,
        location_id=str(body.location_id),
        name=body.name,
        node_code=body.node_code,
        floor=body.floor,
    )


class RoomNameRequest(BaseModel):
    room_id: UUID
    name: str = Field(min_length=1, max_length=80)


@router.put("/clinic-config/room-name")
async def rename_room(
    body: RoomNameRequest,
    identity: StaffIdentity = Depends(_WRITE_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Đổi tên hiển thị — room_id giữ nguyên, lịch/hàng chờ không mất gì."""
    return await ClinicConfigService(pool).rename_room(
        identity=identity, room_id=str(body.room_id), name=body.name
    )


class RoomActiveRequest(BaseModel):
    room_id: UUID
    is_active: bool


@router.put("/clinic-config/room-active")
async def set_room_active(
    body: RoomActiveRequest,
    identity: StaffIdentity = Depends(_WRITE_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Bật/tắt phòng (tắt chứ không xoá)."""
    return await ClinicConfigService(pool).set_room_active(
        identity=identity, room_id=str(body.room_id), is_active=body.is_active
    )


class NodesRequest(BaseModel):
    #: Danh sách ĐẦY ĐỦ, không phải phần thêm. Rỗng = không phục vụ bước nào.
    node_codes: list[str] = Field(default_factory=list)


class RoomNodesRequest(NodesRequest):
    room_id: UUID


@router.put("/clinic-config/room-nodes")
async def set_room_nodes(
    body: RoomNodesRequest,
    identity: StaffIdentity = Depends(_WRITE_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Phòng này phục vụ những bước nào — "phòng siêu âm" là một dòng ở đây."""
    return await ClinicConfigService(pool).set_room_nodes(
        identity=identity, room_id=str(body.room_id), node_codes=body.node_codes
    )


class StaffNodesRequest(NodesRequest):
    staff_id: UUID


@router.put("/clinic-config/staff-nodes")
async def set_staff_nodes(
    body: StaffNodesRequest,
    identity: StaffIdentity = Depends(_WRITE_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Người này làm được những bước nào — khám 5 chuyên khoa, hay chỉ siêu âm."""
    return await ClinicConfigService(pool).set_staff_nodes(
        identity=identity, staff_id=str(body.staff_id), node_codes=body.node_codes
    )


class ThuKyBacSiRequest(BaseModel):
    thu_ky_staff_id: UUID
    bac_si_staff_ids: list[UUID] = Field(default_factory=list, max_length=50)


@router.put("/clinic-config/thu-ky-bac-si")
async def set_thu_ky_bac_si(
    body: ThuKyBacSiRequest,
    identity: StaffIdentity = Depends(_WRITE_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Thư ký này đi cùng những bác sĩ nào (Tuyền chốt 15/09/2026)."""
    return await dat_bac_si_cho_thu_ky(
        pool,
        identity=identity,
        thu_ky_staff_id=str(body.thu_ky_staff_id),
        bac_si_staff_ids=[str(x) for x in body.bac_si_staff_ids],
    )
