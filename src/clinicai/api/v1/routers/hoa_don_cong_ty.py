"""Hoá đơn công ty (G5c): công ty trong hồ sơ khách + bản chụp trên hoá đơn.

Router mỏng — luật (MST chỉ nhắc, bản chụp không đổi theo hồ sơ, lịch sử sửa)
nằm ở `HoaDonCongTyService`. Cửa theo QUYỀN (lego), không theo vai.
"""

from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from clinicai.api.identity import StaffIdentity, get_current_identity
from clinicai.core.database import get_db_pool
from clinicai.permissions.cua_quyen import cua_quyen
from clinicai.services.hoa_don_cong_ty_service import (
    QUYEN_CONG_TY,
    HoaDonCongTyService,
)

router = APIRouter()

_CUA = cua_quyen(*QUYEN_CONG_TY)


class CongTyRequest(BaseModel):
    """Tên bắt buộc; các ô còn lại để trống được. MST sai dạng vẫn lưu (chỉ nhắc)."""

    ten_cong_ty: str = Field(max_length=2000)
    dia_chi_cong_ty: str = Field("", max_length=2000)
    ma_so_thue: str = Field("", max_length=200)
    email_nhan_hd: str = Field("", max_length=2000)
    nguoi_mua: str = Field("", max_length=2000)


class CongTyKhachRequest(CongTyRequest):
    id: str | None = Field(None, max_length=64)


class CongTyHoaDonRequest(CongTyRequest):
    khach_cong_ty_id: str | None = Field(None, max_length=64)
    luu_vao_ho_so: bool = True


class AnRequest(BaseModel):
    an: bool = True


@router.get("/hoa-don/cong-ty/khach/{clinic_patient_id}")
async def doc_cong_ty_khach(
    clinic_patient_id: str,
    ca_da_an: bool = Query(False),
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Không có quyền → ``duoc_xem: false`` + rỗng (màn ẩn khối), không 403."""
    svc = HoaDonCongTyService(pool)
    if not await svc.duoc_xem(identity=identity):
        return {"cong_ty": [], "duoc_xem": False}
    rows = await svc.doc_cong_ty_khach(
        identity=identity, clinic_patient_id=clinic_patient_id, ca_da_an=ca_da_an
    )
    return {"cong_ty": rows, "duoc_xem": True}


@router.put("/hoa-don/cong-ty/khach/{clinic_patient_id}")
async def luu_cong_ty_khach(
    clinic_patient_id: str,
    body: CongTyKhachRequest,
    identity: StaffIdentity = Depends(_CUA),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    return await HoaDonCongTyService(pool).luu_cong_ty_khach(
        identity=identity,
        clinic_patient_id=clinic_patient_id,
        id_=body.id,
        ten_cong_ty=body.ten_cong_ty,
        dia_chi_cong_ty=body.dia_chi_cong_ty,
        ma_so_thue=body.ma_so_thue,
        email_nhan_hd=body.email_nhan_hd,
        nguoi_mua=body.nguoi_mua,
    )


@router.put("/hoa-don/cong-ty/an/{id}")
async def an_cong_ty_khach(
    id: str,
    body: AnRequest,
    identity: StaffIdentity = Depends(_CUA),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Gỡ công ty khỏi hồ sơ khách (an=true) hoặc khôi phục (an=false)."""
    return await HoaDonCongTyService(pool).an_cong_ty_khach(
        identity=identity, id_=id, an=body.an
    )


@router.get("/hoa-don/cong-ty/phieu/{payment_cycle_id}")
async def doc_cong_ty_hoa_don(
    payment_cycle_id: str,
    identity: StaffIdentity = Depends(_CUA),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Công ty đang ghi trên hoá đơn + gợi ý điền sẵn từ hồ sơ khách."""
    return await HoaDonCongTyService(pool).doc_hoa_don(
        identity=identity, payment_cycle_id=payment_cycle_id
    )


@router.put("/hoa-don/cong-ty/phieu/{payment_cycle_id}")
async def ghi_cong_ty_hoa_don(
    payment_cycle_id: str,
    body: CongTyHoaDonRequest,
    identity: StaffIdentity = Depends(_CUA),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    return await HoaDonCongTyService(pool).ghi_hoa_don(
        identity=identity,
        payment_cycle_id=payment_cycle_id,
        ten_cong_ty=body.ten_cong_ty,
        dia_chi_cong_ty=body.dia_chi_cong_ty,
        ma_so_thue=body.ma_so_thue,
        email_nhan_hd=body.email_nhan_hd,
        nguoi_mua=body.nguoi_mua,
        khach_cong_ty_id=body.khach_cong_ty_id,
        luu_vao_ho_so=body.luu_vao_ho_so,
    )


@router.delete("/hoa-don/cong-ty/phieu/{payment_cycle_id}")
async def bo_cong_ty_hoa_don(
    payment_cycle_id: str,
    identity: StaffIdentity = Depends(_CUA),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Bỏ chọn hoá đơn công ty — hoàn tác bằng PUT lại (không xoá dòng nào)."""
    return await HoaDonCongTyService(pool).bo_hoa_don(
        identity=identity, payment_cycle_id=payment_cycle_id
    )


@router.get("/hoa-don/cong-ty/phieu/{payment_cycle_id}/lich-su")
async def lich_su_cong_ty_hoa_don(
    payment_cycle_id: str,
    identity: StaffIdentity = Depends(_CUA),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    rows = await HoaDonCongTyService(pool).doc_lich_su(
        identity=identity, payment_cycle_id=payment_cycle_id
    )
    return {"lich_su": rows}
