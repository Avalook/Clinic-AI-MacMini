"""Cấu hình phòng khám — sơ đồ phòng, tầng, và ai làm được việc gì.

Đọc mở cho vai vận hành (bảng điều phối cần biết phòng nào phục vụ bước nào);
GHI chỉ quản lý. Tách hai quyền ở tầng router thay vì trong một handler: gộp
chung thì một lần sửa nhầm điều kiện là mở luôn quyền đổi sơ đồ phòng khám.
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

router = APIRouter()

_WRITE_GUARD = require_role(ClinicRole.MANAGEMENT)


@router.get("/clinic-config/overview")
async def overview(
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Cơ sở → tầng → phòng, kèm bước mỗi phòng phục vụ."""
    return await ClinicConfigService(pool).overview(identity=identity)


@router.get("/clinic-config/staff")
async def staff(
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Ai làm được bước nào."""
    return await ClinicConfigService(pool).staff(identity=identity)


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
