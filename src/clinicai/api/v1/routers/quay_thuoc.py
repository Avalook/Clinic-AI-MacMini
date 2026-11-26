"""Quầy thuốc chỉnh ĐƠN BÁN trước khi thu (Tuyền 24/09/2026).

Cửa theo QUYỀN "Thu tiền thuốc" (``payment.medicine.collect``) — kiểm trong
QuayThuocService, trong chính giao dịch. Router mỏng.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from clinicai.api.identity import StaffIdentity, get_current_identity
from clinicai.core.database import get_db_pool
from clinicai.services.payment_access_service import (
    authorize_drug_line,
    authorize_payment,
)
from clinicai.services.quay_thuoc_service import QuayThuocService
from clinicai.services.thuoc import go_dong_lech

router = APIRouter()


@router.get("/quay-thuoc/luot/{visit_id}")
async def doc_don_ban(
    visit_id: UUID,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Đơn bán của lượt: dòng bác sĩ kê + dòng quầy thêm, kèm tích / số mua."""
    identity = await authorize_payment(
        pool, identity, visit_id=str(visit_id), kind="thuoc"
    )
    return await QuayThuocService(pool).doc(visit_id=str(visit_id), identity=identity)


class ChonBody(BaseModel):
    prescription_id: UUID
    mua: bool


@router.post("/quay-thuoc/chon")
async def chon(
    body: ChonBody,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Tích (khách lấy) / bỏ tick (khách không lấy)."""
    identity = await authorize_drug_line(pool, identity, str(body.prescription_id))
    return await QuayThuocService(pool).chon(
        prescription_id=str(body.prescription_id), mua=body.mua, identity=identity
    )


class SoLuongBody(BaseModel):
    prescription_id: UUID
    so_luong: float = Field(gt=0, le=100000)


@router.post("/quay-thuoc/so-luong")
async def doi_so_luong(
    body: SoLuongBody,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Đơn bác sĩ: số mua (≤ số kê). Dòng quầy thêm: số lượng."""
    identity = await authorize_drug_line(pool, identity, str(body.prescription_id))
    return await QuayThuocService(pool).doi_so_luong(
        prescription_id=str(body.prescription_id),
        so_luong=body.so_luong,
        identity=identity,
    )


class DonViBody(BaseModel):
    prescription_id: UUID
    don_vi: str = Field(min_length=1, max_length=50)


@router.post("/quay-thuoc/don-vi")
async def doi_don_vi(
    body: DonViBody,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Đổi đơn vị bán của dòng trước khi thu; tiền lấy theo giá đơn vị đó."""
    identity = await authorize_drug_line(pool, identity, str(body.prescription_id))
    return await QuayThuocService(pool).doi_don_vi(
        prescription_id=str(body.prescription_id),
        don_vi=body.don_vi,
        identity=identity,
    )


class DongThemBody(BaseModel):
    id: UUID | None = None
    drug_catalog_id: UUID | None = None
    quantity: str | None = Field(default=None, max_length=64)
    dosage: str | None = Field(default=None, max_length=500)
    caution: str | None = Field(default=None, max_length=500)


class LuuThemBody(BaseModel):
    dong: list[DongThemBody] = Field(default_factory=list, max_length=50)


@router.post("/quay-thuoc/luot/{visit_id}/them")
async def luu_dong_them(
    visit_id: UUID,
    body: LuuThemBody,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Lấy thêm thuốc: thêm dòng mới / sửa dòng quầy đã thêm. Không xoá dòng nào."""
    identity = await authorize_payment(
        pool, identity, visit_id=str(visit_id), kind="thuoc"
    )
    return await QuayThuocService(pool).luu_dong_them(
        visit_id=str(visit_id),
        dong=[
            {
                "id": str(d.id) if d.id else None,
                "drug_catalog_id": str(d.drug_catalog_id)
                if d.drug_catalog_id
                else None,
                "quantity": d.quantity,
                "dosage": d.dosage,
                "caution": d.caution,
            }
            for d in body.dong
        ],
        identity=identity,
    )


# ── Gỡ dòng thuốc lệch ở quầy (T3, 26/11): gán thuốc đúng / điền giá ────────


class DongLech(BaseModel):
    prescription_id: str
    van_de: str | None
    drug_catalog_id: str | None
    dien_gia_duoc: bool
    ly_do_khong_dien_gia: str | None
    thuoc_chua_gia: bool
    bo_gan_duoc: bool


class DongLechOut(BaseModel):
    visit_id: str
    dong: list[DongLech]


class GanThuocBody(BaseModel):
    prescription_id: UUID
    drug_catalog_id: UUID


class BoGanBody(BaseModel):
    prescription_id: UUID


class DienGiaBody(BaseModel):
    drug_catalog_id: UUID
    # Any: luật đọc số nằm ở service (`gia_quay`), trả câu tiếng Việt.
    gia: Any = None


class KetQuaGo(BaseModel):
    ok: bool
    prescription_id: str | None = None
    id: str | None = None
    nhac: str | None = None


@router.get("/quay-thuoc/luot/{visit_id}/dong-lech", response_model=DongLechOut)
async def xem_dong_lech(
    visit_id: UUID,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Dòng đang chặn thu tiền thuốc + quầy làm được gì với từng dòng."""
    identity = await authorize_payment(
        pool, identity, visit_id=str(visit_id), kind="thuoc"
    )
    return await go_dong_lech.doc_dong_lech(
        pool, identity=identity, visit_id=str(visit_id)
    )


@router.post("/quay-thuoc/gan-thuoc", response_model=KetQuaGo)
async def gan_thuoc(
    body: GanThuocBody,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Gán dòng sang thuốc đúng trong danh mục (đổi thuốc kho; tên bác sĩ giữ)."""
    identity = await authorize_drug_line(pool, identity, str(body.prescription_id))
    return await go_dong_lech.gan_thuoc_dung(
        pool,
        identity=identity,
        prescription_id=str(body.prescription_id),
        drug_catalog_id=str(body.drug_catalog_id),
    )


@router.post("/quay-thuoc/bo-gan-thuoc", response_model=KetQuaGo)
async def bo_gan_thuoc(
    body: BoGanBody,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Hoàn tác lần gán thuốc gần nhất của dòng."""
    identity = await authorize_drug_line(pool, identity, str(body.prescription_id))
    return await go_dong_lech.hoan_tac_gan(
        pool, identity=identity, prescription_id=str(body.prescription_id)
    )


@router.post("/quay-thuoc/dien-gia", response_model=KetQuaGo)
async def dien_gia(
    body: DienGiaBody,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Điền giá cho thuốc chưa có giá — cần quyền Sửa giá thuốc (máy chủ chốt)."""
    return await go_dong_lech.dien_gia_thuoc(
        pool, identity=identity, drug_catalog_id=str(body.drug_catalog_id), gia=body.gia
    )
