"""Invoice register: read permission and roster scope checked server-side."""

import json
from typing import Any

import asyncpg
from fastapi import APIRouter, Body, Depends, Query
from fastapi.responses import Response

from clinicai.api.identity import StaffIdentity, get_current_identity
from clinicai.core.database import get_db_pool
from clinicai.services.danh_sach_hoa_don_service import (
    DanhSachHoaDonService,
    xlsx_hoa_don,
)
from clinicai.services.excel_export import XLSX_MEDIA_TYPE
from clinicai.services.hoa_don_cong_ty_service import HoaDonCongTyService
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
    return await XuatHoaDonService(pool).xem(
        identity=identity,
        tu=tu,
        den=den,
        loai=loai,
        co_so=co_so,
        che_do=che_do,
        ghi_giam_gia=ghi_giam_gia,
        ghi_de=_doc_ghi_de(ghi_de),
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


# ═══════════════════════════════════════════════════════════════════════════════
# G5c — Hoá đơn công ty + xuất MISA
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/hoa-don/cong-ty/khach/{clinic_patient_id}")
async def doc_cong_ty_khach(
    clinic_patient_id: str,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Danh sách công ty của khách (điền sẵn lần trước)."""
    rows = await HoaDonCongTyService(pool).doc_cong_ty_khach(
        identity=identity, clinic_patient_id=clinic_patient_id
    )
    return {"cong_ty": rows}


@router.post("/hoa-don/cong-ty/khach/{clinic_patient_id}")
async def luu_cong_ty_khach(
    clinic_patient_id: str,
    body: dict[str, Any] = Body(...),
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Tạo hoặc cập nhật công ty của khách."""
    return await HoaDonCongTyService(pool).luu_cong_ty_khach(
        identity=identity,
        clinic_patient_id=clinic_patient_id,
        id=body.get("id"),
        ten_cong_ty=str(body.get("ten_cong_ty") or ""),
        dia_chi_cong_ty=str(body.get("dia_chi_cong_ty") or ""),
        ma_so_thue=str(body.get("ma_so_thue") or ""),
        email_nhan_hd=str(body.get("email_nhan_hd") or ""),
        is_mac_dinh=bool(body.get("is_mac_dinh", True)),
        ghi_chu=str(body.get("ghi_chu") or ""),
    )


@router.delete("/hoa-don/cong-ty/khach/{clinic_patient_id}/{id}")
async def xoa_cong_ty_khach(
    clinic_patient_id: str,
    id: str,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    await HoaDonCongTyService(pool).xoa_cong_ty_khach(identity=identity, id=id)
    return {"ok": True}


@router.get("/hoa-don/cong-ty/{payment_cycle_id}")
async def doc_hoa_don_cong_ty(
    payment_cycle_id: str,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Snapshot công ty gắn với payment_cycle (để hiển thị / chỉnh sửa)."""
    result = await HoaDonCongTyService(pool).doc_hoa_don_cong_ty(
        identity=identity, payment_cycle_id=payment_cycle_id
    )
    return {"cong_ty": result}


@router.put("/hoa-don/cong-ty/{payment_cycle_id}")
async def ghi_hoa_don_cong_ty(
    payment_cycle_id: str,
    body: dict[str, Any] = Body(...),
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Ghi/cập nhật snapshot công ty cho payment_cycle.

    Snapshot không đổi sau khi xuất MISA — sửa thì ghi lịch sử.
    """
    return await HoaDonCongTyService(pool).ghi_hoa_don_cong_ty(
        identity=identity,
        payment_cycle_id=payment_cycle_id,
        ten_cong_ty=str(body.get("ten_cong_ty") or ""),
        dia_chi_cong_ty=str(body.get("dia_chi_cong_ty") or ""),
        ma_so_thue=str(body.get("ma_so_thue") or ""),
        email_nhan_hd=str(body.get("email_nhan_hd") or ""),
        khach_cong_ty_id=body.get("khach_cong_ty_id"),
    )


@router.get("/hoa-don/cong-ty/{payment_cycle_id}/lich-su")
async def doc_lich_su_cong_ty(
    payment_cycle_id: str,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Lịch sử thay đổi thông tin công ty sau khi xuất MISA."""
    svc = HoaDonCongTyService(pool)
    hdc = await svc.doc_hoa_don_cong_ty(
        identity=identity, payment_cycle_id=payment_cycle_id
    )
    if not hdc:
        return {"lich_su": []}
    rows = await svc.doc_lich_su(identity=identity, hoa_don_cong_ty_id=hdc["id"])
    return {"lich_su": rows}


# ─── Đánh dấu xuất MISA ─────────────────────────────────────────────────────


@router.get("/hoa-don/misa-xuat")
async def doc_misa_xuat(
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Danh sách các lần đã xuất sang MISA."""
    rows = await HoaDonCongTyService(pool).doc_misa_xuat(identity=identity)
    return {"misa_xuat": rows}


@router.post("/hoa-don/misa-xuat")
async def danh_dau_xuat_misa(
    body: dict[str, Any] = Body(...),
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Đánh dấu đã xuất kỳ này sang MISA.

    Gửi `hoa_don` = mảng hoá đơn từ /hoa-don/xuat.
    """
    return await HoaDonCongTyService(pool).danh_dau_xuat_misa(
        identity=identity,
        tu_ngay=str(body.get("tu_ngay") or ""),
        den_ngay=str(body.get("den_ngay") or ""),
        hoa_don=list(body.get("hoa_don") or []),
        co_so=body.get("co_so"),
        ghi_chu=str(body.get("ghi_chu") or ""),
    )
