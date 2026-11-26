"""Danh mục thuốc: xoá thuốc chưa từng dùng (lưu bản chụp trước) và khôi phục.

Router mỏng — luật ở `services/thuoc/`. Quyền khối Nhà thuốc như sửa danh mục
(`pharmacy.dispense`); xem danh sách đã xoá thì `pharmacy.view` cũng được.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from clinicai.api.identity import StaffIdentity, get_current_identity
from clinicai.core.database import get_db_pool
from clinicai.permissions.cua_quyen import cua_quyen
from clinicai.services.thuoc import (
    cach_dung_db,
    don_vi_con,
    het_thuoc,
    khoi_phuc_thuoc,
    xoa_thuoc,
)
from clinicai.services.thuoc.cach_dung import CachDung

router = APIRouter()
_DOC = cua_quyen("pharmacy.view", "pharmacy.dispense")
_GHI = cua_quyen("pharmacy.dispense")
#: Quầy thu thuốc + nhà thuốc xem ngày dự tính dùng hết thuốc (Tuyền 26/11).
_HET = cua_quyen("payment.medicine.collect", "pharmacy.view", "pharmacy.dispense")


class ChoDungThuoc(BaseModel):
    bang: str
    nhan: str
    so: int


class XoaDuoc(BaseModel):
    xoa_duoc: bool
    ly_do: str | None = None
    da_dung: list[ChoDungThuoc] = Field(default_factory=list)


class XoaRequest(BaseModel):
    # Không giới hạn ở đây: service trả câu tiếng Việt (luật đầu vào rác).
    ly_do: str | None = None


class DaXoa(BaseModel):
    id: str
    da_xoa: bool
    ten: str
    ban_luu_id: str


class ThuocDaXoa(BaseModel):
    id: str
    drug_catalog_id: str
    ten: str
    ly_do: str
    xoa_luc: datetime
    nguoi_xoa: str | None = None
    khoi_phuc_luc: datetime | None = None
    nguoi_khoi_phuc: str | None = None
    da_khoi_phuc: bool


class TinhDong(BaseModel):
    drug_catalog_id: UUID | None = None
    so_luong: str = Field(default="", max_length=100)
    don_vi: str = Field(default="", max_length=100)
    ct: CachDung | None = None
    #: Chữ cách dùng hiện có (kiểu "chỉ chữ" giữ nguyên chữ này).
    chu: str = Field(default="", max_length=2000)
    #: Bác sĩ sửa tay "uống từ ngày thứ … đến ngày thứ … của chu kỳ" (Tuyền 26/11).
    tu_ngay: int | None = Field(default=None, ge=1, le=60)
    den_ngay: int | None = Field(default=None, ge=1, le=60)


class TinhRequest(BaseModel):
    visit_id: UUID | None = None
    #: Bác sĩ nhập tay (để trống = lấy từ phiếu khám của lượt).
    kinh_lan_cuoi: str | None = Field(default=None, max_length=60)
    chu_ky: str | None = Field(default=None, max_length=20)
    dong: list[TinhDong] = Field(default_factory=list, max_length=100)


class UocTinh(BaseModel):
    kinh_toi: date
    bat_dau: date
    het: date


class KetQuaDong(BaseModel):
    tinh_duoc: bool
    ly_do: str | None = None
    cau: str
    lieu_ngay: str | None = None
    so_ngay: int | None = None
    ngay_het: date | None = None
    so_lieu_can: str | None = None
    goi_y_so_luong: int | None = None
    uoc_tinh: UocTinh | None = None
    #: Thuốc theo chu kỳ kinh + mốc đang dùng (từ câu cách dùng hoặc bác sĩ sửa).
    theo_chu_ky: bool = False
    tu_ngay: int | None = None
    den_ngay: int | None = None


class KinhCuaLuot(BaseModel):
    kinh_lan_cuoi: str | None = None
    chu_ky: str | None = None
    #: "phieu" = lấy từ phiếu khám · "go_tay" = bác sĩ nhập · None = không có.
    nguon: str | None = None
    doc_duoc: bool


class TinhKetQua(BaseModel):
    ngay_ke: date
    kinh: KinhCuaLuot
    dong: list[KetQuaDong]


class CachDungMacDinh(BaseModel):
    id: str
    don_vi_goc: str
    can_khai_so_lieu: bool
    cach_dung: str
    ct: CachDung | None = None
    so_lieu_moi_don_vi_goc: Decimal | None = None
    cau: str | None = None


class LuuCachDung(BaseModel):
    ct: CachDung | None = None
    so_lieu_moi_don_vi_goc: Decimal | None = Field(default=None, gt=0, le=100000)


@router.post("/thuoc/cach-dung/tinh", response_model=TinhKetQua)
async def cua_tinh_cach_dung(
    body: TinhRequest,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> TinhKetQua:
    """Số ngày dùng / ngày hết / gợi ý SL / câu in của các dòng đang kê (chưa lưu)."""
    kq = await cach_dung_db.tinh_don(
        pool,
        identity=identity,
        visit_id=str(body.visit_id) if body.visit_id else None,
        dong=[
            {
                "drug_catalog_id": str(d.drug_catalog_id)
                if d.drug_catalog_id
                else None,
                "so_luong": d.so_luong,
                "don_vi": d.don_vi,
                "ct": d.ct,
                "chu": d.chu,
                "tu_ngay": d.tu_ngay,
                "den_ngay": d.den_ngay,
            }
            for d in body.dong
        ],
        kinh_lan_cuoi=body.kinh_lan_cuoi,
        chu_ky=body.chu_ky,
    )
    return TinhKetQua.model_validate(kq)


@router.get("/thuoc/{thuoc_id}/cach-dung", response_model=CachDungMacDinh)
async def cua_doc_cach_dung(
    thuoc_id: UUID,
    identity: StaffIdentity = Depends(_DOC),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> CachDungMacDinh:
    kq = await cach_dung_db.doc_mac_dinh(
        pool, identity=identity, thuoc_id=str(thuoc_id)
    )
    return CachDungMacDinh.model_validate(kq)


@router.put("/thuoc/{thuoc_id}/cach-dung", response_model=CachDungMacDinh)
async def cua_luu_cach_dung(
    thuoc_id: UUID,
    body: LuuCachDung,
    identity: StaffIdentity = Depends(_GHI),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> CachDungMacDinh:
    kq = await cach_dung_db.luu_mac_dinh(
        pool,
        identity=identity,
        thuoc_id=str(thuoc_id),
        ct=body.ct,
        so_lieu=body.so_lieu_moi_don_vi_goc,
    )
    return CachDungMacDinh.model_validate(kq)


class NgayHetThuoc(BaseModel):
    ten: str | None = None
    so_luong: str
    so_ngay: int
    ngay_het: date
    #: Thuốc theo chu kỳ kinh: ngày bắt đầu uống (ước tính từ kinh lần cuối).
    bat_dau: date | None = None


class DanhSachNgayHet(BaseModel):
    items: list[NgayHetThuoc]


@router.get("/thuoc/het-thuoc", response_model=DanhSachNgayHet)
async def cua_ngay_het_thuoc(
    visit_id: UUID | None = None,
    phieu_id: UUID | None = None,
    identity: StaffIdentity = Depends(_HET),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> DanhSachNgayHet:
    """Ngày dự tính dùng hết thuốc của lượt (theo mã lượt hoặc mã phiếu thu thuốc)."""
    if visit_id is None and phieu_id is None:
        return DanhSachNgayHet(items=[])
    ds = await het_thuoc.ngay_het_thuoc_cua_luot(
        pool,
        identity=identity,
        visit_id=str(visit_id) if visit_id else None,
        phieu_id=str(phieu_id) if phieu_id else None,
    )
    return DanhSachNgayHet.model_validate({"items": ds})


class DongQuayTinh(BaseModel):
    id: str = Field(max_length=64)
    drug_catalog_id: UUID | None = None
    so_luong: str = Field(default="", max_length=40)
    don_vi: str = Field(default="", max_length=40)
    chu: str = Field(default="", max_length=2000)


class TinhDongQuay(BaseModel):
    visit_id: UUID
    dong: list[DongQuayTinh] = Field(max_length=200)


class NgayHetDong(BaseModel):
    so_ngay: int
    ngay_het: date
    bat_dau: date | None = None


@router.post("/thuoc/het-thuoc/dong", response_model=dict[str, NgayHetDong])
async def cua_ngay_het_tung_dong(
    body: TinhDongQuay,
    identity: StaffIdentity = Depends(_HET),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, NgayHetDong]:
    """Quầy thu thuốc: ngày hết thuốc theo SỐ ĐANG BÁN của từng dòng (Tuyền 26/11)."""
    kq = await het_thuoc.ngay_het_tung_dong(
        pool,
        identity=identity,
        visit_id=str(body.visit_id),
        dong=[d.model_dump(mode="json") for d in body.dong],
    )
    return {k: NgayHetDong.model_validate(v) for k, v in kq.items()}


class DonViCon(BaseModel):
    id: str
    don_vi_me: str
    don_vi_con: str | None = None
    so_con: Decimal | None = None
    gia_me: int | None = None
    gia_con: int | None = None
    gia_con_tu_tinh: int | None = None
    xem_truoc: str
    goi_y: list[str]


class LuuDonViCon(BaseModel):
    don_vi_con: str | None = Field(default=None, max_length=20)
    so_con: Decimal | None = Field(default=None, gt=0, le=100000)
    gia_con: Decimal | None = Field(default=None, gt=0, le=1_000_000_000)


@router.get("/thuoc/{thuoc_id}/don-vi-con", response_model=DonViCon)
async def cua_doc_don_vi_con(
    thuoc_id: UUID,
    identity: StaffIdentity = Depends(_DOC),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> DonViCon:
    """Khối "Đơn vị con và tính số ngày dùng hết thuốc" (Tuyền 26/11)."""
    kq = await don_vi_con.doc_don_vi_con(
        pool, identity=identity, thuoc_id=str(thuoc_id)
    )
    return DonViCon.model_validate(kq)


@router.put("/thuoc/{thuoc_id}/don-vi-con", response_model=DonViCon)
async def cua_luu_don_vi_con(
    thuoc_id: UUID,
    body: LuuDonViCon,
    identity: StaffIdentity = Depends(_GHI),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> DonViCon:
    kq = await don_vi_con.luu_don_vi_con(
        pool,
        identity=identity,
        thuoc_id=str(thuoc_id),
        don_vi_con=body.don_vi_con,
        so_con=body.so_con,
        gia_con=body.gia_con,
    )
    return DonViCon.model_validate(kq)


class DanhSachDaXoa(BaseModel):
    items: list[ThuocDaXoa]


class DaKhoiPhuc(BaseModel):
    id: str
    ten: str
    khoi_phuc: bool


@router.get("/thuoc/{thuoc_id}/xoa-duoc", response_model=XoaDuoc)
async def cua_xoa_duoc(
    thuoc_id: UUID,
    identity: StaffIdentity = Depends(_GHI),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> XoaDuoc:
    kq = await xoa_thuoc.thuoc_xoa_duoc(pool, identity=identity, thuoc_id=str(thuoc_id))
    return XoaDuoc(**kq)


@router.post("/thuoc/{thuoc_id}/xoa", response_model=DaXoa)
async def cua_xoa_thuoc(
    thuoc_id: UUID,
    body: XoaRequest,
    identity: StaffIdentity = Depends(_GHI),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> DaXoa:
    kq = await xoa_thuoc.xoa_thuoc(
        pool, identity=identity, thuoc_id=str(thuoc_id), ly_do=body.ly_do
    )
    return DaXoa(**kq)


@router.get("/thuoc/da-xoa", response_model=DanhSachDaXoa)
async def cua_thuoc_da_xoa(
    identity: StaffIdentity = Depends(_DOC),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> DanhSachDaXoa:
    ds = await khoi_phuc_thuoc.danh_sach_da_xoa(pool, identity=identity)
    return DanhSachDaXoa(items=[ThuocDaXoa(**d) for d in ds])


@router.post("/thuoc/da-xoa/{ban_luu_id}/khoi-phuc", response_model=DaKhoiPhuc)
async def cua_khoi_phuc_thuoc(
    ban_luu_id: UUID,
    identity: StaffIdentity = Depends(_GHI),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> DaKhoiPhuc:
    kq = await khoi_phuc_thuoc.khoi_phuc(
        pool, identity=identity, ban_luu_id=str(ban_luu_id)
    )
    return DaKhoiPhuc(**kq)
