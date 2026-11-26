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
from clinicai.services.thuoc import cach_dung_db, khoi_phuc_thuoc, xoa_thuoc
from clinicai.services.thuoc.cach_dung import CachDung

router = APIRouter()
_DOC = cua_quyen("pharmacy.view", "pharmacy.dispense")
_GHI = cua_quyen("pharmacy.dispense")


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
