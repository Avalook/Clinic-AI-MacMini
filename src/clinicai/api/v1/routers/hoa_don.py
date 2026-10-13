"""Invoice register: read permission and roster scope checked server-side."""

from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

from clinicai.api.identity import StaffIdentity, get_current_identity
from clinicai.core.database import get_db_pool
from clinicai.services.danh_sach_hoa_don_service import (
    DanhSachHoaDonService,
    xlsx_hoa_don,
)
from clinicai.services.excel_export import XLSX_MEDIA_TYPE
from clinicai.services.xuat_hoa_don_service import XuatHoaDonService, xlsx_misa

router = APIRouter()


@router.get("/hoa-don")
async def danh_sach_hoa_don(
    tu: str | None = Query(None, max_length=40),
    den: str | None = Query(None, max_length=40),
    tim: str | None = Query(None, max_length=200),
    loai: str | None = Query(None, max_length=20),
    trang_thai: str | None = Query(None, max_length=30),
    co_so: str | None = Query(None, max_length=64),
    ca: str | None = Query(None, max_length=10),
    can_kiem_tra: bool = Query(False),
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    return await DanhSachHoaDonService(pool).xem(
        identity=identity,
        tu=tu,
        den=den,
        tim=tim,
        loai=loai,
        trang_thai=trang_thai,
        co_so=co_so,
        ca=ca,
        can_kiem_tra=can_kiem_tra,
    )


@router.get("/hoa-don/xlsx")
async def danh_sach_hoa_don_excel(
    data: dict[str, Any] = Depends(danh_sach_hoa_don),
) -> Response:
    return Response(
        xlsx_hoa_don(data),
        media_type=XLSX_MEDIA_TYPE,
        headers={
            "Content-Disposition": 'attachment; filename="danh-sach-hoa-don.xlsx"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/hoa-don/xuat")
async def xuat_hoa_don(
    tu: str | None = Query(None, max_length=40),
    den: str | None = Query(None, max_length=40),
    loai: str | None = Query(None, max_length=20),
    co_so: str | None = Query(None, max_length=64),
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    return await XuatHoaDonService(pool).xem(
        identity=identity, tu=tu, den=den, loai=loai, co_so=co_so
    )


@router.get("/hoa-don/xuat/xlsx")
async def xuat_hoa_don_excel(
    data: dict[str, Any] = Depends(xuat_hoa_don),
) -> Response:
    ten = f"hoa-don-gtgt-{data['tu']}-den-{data['den']}.xlsx"
    return Response(
        xlsx_misa(data["hoa_don"]),
        media_type=XLSX_MEDIA_TYPE,
        headers={
            "Content-Disposition": f'attachment; filename="{ten}"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
