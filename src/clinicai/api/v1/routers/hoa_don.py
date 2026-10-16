"""Invoice register: read permission and roster scope checked server-side."""

import json
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
from clinicai.services.hoa_don_misa_service import HoaDonMisaService
from clinicai.services.theo_hang_hoa_service import (
    TheoHangHoaService,
    xlsx_theo_hang_hoa,
)
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
    nhom: str | None = Query(None, max_length=30),
    hinh_thuc: str | None = Query(None, max_length=20),
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
        nhom=nhom,
        hinh_thuc=hinh_thuc,
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


def _doc_ghi_de(raw: str | None) -> dict[str, str]:
    """`{"id dòng": "thuế suất"}` gõ tay lúc xuất; rác → rỗng (không ném)."""
    try:
        v = json.loads(raw) if raw else {}
    except (ValueError, TypeError):
        return {}
    if not isinstance(v, dict) or len(v) > 2000:
        return {}
    return {str(k)[:64]: str(x)[:20] for k, x in v.items()}


@router.get("/hoa-don/xuat")
async def xuat_hoa_don(
    tu: str | None = Query(None, max_length=40),
    den: str | None = Query(None, max_length=40),
    loai: str | None = Query(None, max_length=20),
    co_so: str | None = Query(None, max_length=64),
    che_do: str | None = Query(
        None, max_length=10, description="tach (mặc định) | mot — nhiều thuế suất"
    ),
    ghi_giam_gia: bool = Query(False, description="K2: dòng giá gốc + dòng chiết khấu"),
    ghi_de: str | None = Query(
        None, max_length=60000, description='JSON {"id dòng": "thuế suất"}'
    ),
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    data = await XuatHoaDonService(pool).xem(
        identity=identity,
        tu=tu,
        den=den,
        loai=loai,
        co_so=co_so,
        che_do=che_do,
        ghi_giam_gia=ghi_giam_gia,
        ghi_de=_doc_ghi_de(ghi_de),
        kem_dau_van_tay=True,
    )
    # "Đã xuất MISA" / "có thay đổi sau khi xuất" của từng hoá đơn (G5c).
    return await HoaDonMisaService(pool).gan_trang_thai(identity=identity, data=data)


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


@router.get("/hoa-don/theo-hang-hoa")
async def theo_hang_hoa(
    tu: str | None = Query(None, max_length=40),
    den: str | None = Query(None, max_length=40),
    loai: str | None = Query(None, max_length=20),
    co_so: str | None = Query(None, max_length=64),
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Thống kê theo mặt hàng trong kỳ (kế toán) — cùng cổng với Xuất hoá đơn."""
    return await TheoHangHoaService(pool).xem(
        identity=identity, tu=tu, den=den, loai=loai, co_so=co_so
    )


@router.get("/hoa-don/theo-hang-hoa/xlsx")
async def theo_hang_hoa_excel(
    data: dict[str, Any] = Depends(theo_hang_hoa),
) -> Response:
    ten = f"theo-hang-hoa-{data['tu']}-den-{data['den']}.xlsx"
    return Response(
        xlsx_theo_hang_hoa(data),
        media_type=XLSX_MEDIA_TYPE,
        headers={
            "Content-Disposition": f'attachment; filename="{ten}"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
