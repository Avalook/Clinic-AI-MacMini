"""Bàn xét nghiệm đối tác đời mới (ADR-0015). Router mỏng — luật ở services/xet_nghiem.

Router cũ `doi_tac.py` đóng băng (test đếm cửa); cửa mới vào đây, mọi cửa có
`response_model`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

import asyncpg
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from clinicai.api.identity import StaffIdentity
from clinicai.core.database import get_db_pool
from clinicai.permissions.cua_quyen import cua_quyen
from clinicai.services.xet_nghiem import quyen_ban
from clinicai.services.xet_nghiem.cai_dat import CaiDatDoiTac
from clinicai.services.xet_nghiem.doi_tac import QUYEN_QUAN_LY

router = APIRouter()
_QUAN_LY = cua_quyen(QUYEN_QUAN_LY)


# ── Hợp đồng ────────────────────────────────────────────────────────────────
class AnhXaOut(BaseModel):
    id: str
    doi_tac_id: str
    service_price_id: str
    service_code: str
    ten_dich_vu: str
    unit_price: int | None
    gia_goi_y: int | None
    hen_tra_so_ngay: int | None
    mac_dinh: bool
    #: giá / hẹn HIỆU LỰC máy chủ đã tính — màn chỉ hiển thị (luật 7).
    gia_hieu_luc: int | None
    hen_tra_hieu_luc: int | None


class DriveDenOut(BaseModel):
    nhan: str
    mau: Literal["neutral", "success", "danger"]


class DoiTacOut(BaseModel):
    id: str
    ten: str
    ma_ngan: str
    sdt: str | None
    ghi_chu: str | None
    drive_folder_id: str | None
    tai_khoan_nhan_ck: str | None
    hen_tra_so_ngay_mac_dinh: int | None
    ngung_luc: datetime | None
    ly_do_ngung: str | None
    #: còn gán dịch vụ mới được không (đối tác chưa ngưng) — màn không tự suy.
    gan_duoc: bool
    dich_vu: list[AnhXaOut]
    #: Đèn nhịp Drive (máy chủ tính chữ + màu chip — `drive.den_drive`).
    drive_den: DriveDenOut


class DichVuThuHoOut(BaseModel):
    id: str
    service_code: str
    name: str
    unit_price: int | None


class DanhSachDoiTacOut(BaseModel):
    doi_tac: list[DoiTacOut]
    dich_vu_thu_ho: list[DichVuThuHoOut]
    nguong_lay_mau_ngay: int
    hien_ma_ong: bool


class DoiTacIn(BaseModel):
    """Kiểu lỏng: luật ô ở `o_nhap.doc_form_doi_tac` (rác → 422 câu dễ hiểu)."""

    ten: str = Field(default="", max_length=500)
    ma_ngan: str = Field(default="", max_length=50)
    sdt: str | None = Field(default=None, max_length=100)
    ghi_chu: str | None = Field(default=None, max_length=4000)
    drive_folder: str | None = Field(default=None, max_length=1000)
    tai_khoan_nhan_ck: str | None = Field(default=None, max_length=1000)
    hen_tra_so_ngay_mac_dinh: str | int | None = None


class NgungIn(BaseModel):
    ngung: bool
    ly_do: str | None = Field(default=None, max_length=4000)


class AnhXaIn(BaseModel):
    doi_tac_id: str = Field(max_length=64)
    service_price_id: str = Field(max_length=64)
    gia_goi_y: str | int | None = None
    hen_tra_so_ngay: str | int | None = None
    mac_dinh: bool = True


class NguongIn(BaseModel):
    nguong_lay_mau_ngay: str | int
    #: Công tắc "Hiện mã ống" — không gửi ⇒ giữ nguyên.
    hien_ma_ong: bool | None = None


class QuyenNguoiOut(BaseModel):
    staff_id: str
    ten: str | None
    lam_viec: bool
    quan_ly: bool


class BangQuyenOut(BaseModel):
    nguoi: list[QuyenNguoiOut]


# ── Cửa ─────────────────────────────────────────────────────────────────────
@router.get("/xet-nghiem/quyen", response_model=BangQuyenOut)
async def bang_quyen(
    identity: StaffIdentity = Depends(_QUAN_LY),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> object:
    """Bảng Quyền (chỉ xem) — quyền THỰC TẾ ai vào bàn XN / ai quản lý.
    Sửa ở màn Phân quyền."""
    async with pool.acquire() as conn:
        return {"nguoi": await quyen_ban.bang_quyen(conn, identity.clinic_id)}


@router.get("/xet-nghiem/doi-tac", response_model=DanhSachDoiTacOut)
async def danh_sach_doi_tac(
    identity: StaffIdentity = Depends(_QUAN_LY),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> object:
    return await CaiDatDoiTac(pool).danh_sach(identity)


@router.post("/xet-nghiem/doi-tac", response_model=DanhSachDoiTacOut)
async def them_doi_tac(
    body: DoiTacIn,
    identity: StaffIdentity = Depends(_QUAN_LY),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> object:
    return await CaiDatDoiTac(pool).luu_doi_tac(identity, body.model_dump(), None)


@router.put("/xet-nghiem/doi-tac/{doi_tac_id}", response_model=DanhSachDoiTacOut)
async def sua_doi_tac(
    doi_tac_id: str,
    body: DoiTacIn,
    identity: StaffIdentity = Depends(_QUAN_LY),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> object:
    return await CaiDatDoiTac(pool).luu_doi_tac(identity, body.model_dump(), doi_tac_id)


@router.post("/xet-nghiem/doi-tac/{doi_tac_id}/ngung", response_model=DanhSachDoiTacOut)
async def ngung_doi_tac(
    doi_tac_id: str,
    body: NgungIn,
    identity: StaffIdentity = Depends(_QUAN_LY),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> object:
    return await CaiDatDoiTac(pool).ngung(identity, doi_tac_id, body.ngung, body.ly_do)


@router.post("/xet-nghiem/doi-tac-dich-vu", response_model=DanhSachDoiTacOut)
async def gan_dich_vu(
    body: AnhXaIn,
    identity: StaffIdentity = Depends(_QUAN_LY),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> object:
    return await CaiDatDoiTac(pool).gan(identity, body.model_dump())


@router.post(
    "/xet-nghiem/doi-tac-dich-vu/{anh_xa_id}/bo", response_model=DanhSachDoiTacOut
)
async def bo_gan_dich_vu(
    anh_xa_id: str,
    identity: StaffIdentity = Depends(_QUAN_LY),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> object:
    return await CaiDatDoiTac(pool).bo_gan(identity, anh_xa_id)


@router.put("/xet-nghiem/cai-dat", response_model=DanhSachDoiTacOut)
async def luu_cai_dat(
    body: NguongIn,
    identity: StaffIdentity = Depends(_QUAN_LY),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> object:
    return await CaiDatDoiTac(pool).nguong(
        identity, body.nguong_lay_mau_ngay, body.hien_ma_ong
    )
