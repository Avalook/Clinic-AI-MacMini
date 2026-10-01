"""Làm thêm tại quầy — nút "+ dịch vụ" ở Tiếp đón / Đo sinh hiệu (01/10/2026).

Router mỏng: quyền (lego Tiếp đón / Sinh hiệu cho nút; `config.wiring.manage`
cho danh sách) và mọi luật nằm trong `services/lam_them_tai_quay_service.py`.
"""

from __future__ import annotations

from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from clinicai.api.identity import StaffIdentity, get_current_identity
from clinicai.core.database import get_db_pool
from clinicai.services.lam_them_tai_quay_service import LamThemTaiQuayService

router = APIRouter()


@router.get("/lam-them/cau-hinh")
async def doc_cau_hinh(
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    return await LamThemTaiQuayService(pool).cau_hinh(identity=identity)


class MucBody(BaseModel):
    nhan: str | None = Field(default=None, max_length=40)
    bat: bool = True
    thu_tu: int | None = None
    o_tiep_don: bool = True
    o_sinh_hieu: bool = True


class ThuTuMuc(BaseModel):
    service_code: str = Field(min_length=1, max_length=64)
    thu_tu: int = Field(ge=0, le=9999)


class ThuTuBody(BaseModel):
    muc: list[ThuTuMuc] = Field(min_length=1, max_length=100)


@router.put("/lam-them/cau-hinh/{service_code}")
async def luu_muc(
    service_code: str,
    body: MucBody,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    return await LamThemTaiQuayService(pool).luu_muc(
        identity=identity,
        service_code=service_code,
        nhan=body.nhan,
        bat=body.bat,
        thu_tu=body.thu_tu,
        o_tiep_don=body.o_tiep_don,
        o_sinh_hieu=body.o_sinh_hieu,
    )


@router.delete("/lam-them/cau-hinh/{service_code}")
async def bo_muc(
    service_code: str,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    return await LamThemTaiQuayService(pool).bo_muc(
        identity=identity, service_code=service_code
    )


@router.put("/lam-them/cau-hinh-thu-tu")
async def doi_thu_tu(
    body: ThuTuBody,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    return await LamThemTaiQuayService(pool).doi_thu_tu(
        identity=identity,
        muc=[item.model_dump() for item in body.muc],
    )


@router.get("/lam-them/nut")
async def nut_cho_luot(
    noi: str = Query(..., max_length=20),
    luot: str = Query("", max_length=12000),
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    return await LamThemTaiQuayService(pool).nut_cho_luot(
        identity=identity, noi=noi, visit_ids=luot
    )


class DatBody(BaseModel):
    visit_id: str = Field(min_length=1, max_length=64)
    service_code: str = Field(min_length=1, max_length=64)
    noi: str = Field(min_length=1, max_length=20)
    chon: bool
    expected_order_id: str | None = Field(default=None, max_length=64)
    expected_version: int | None = Field(default=None, ge=1)
    expected_state_revision: int = Field(ge=0)
    idempotency_key: str = Field(min_length=8, max_length=200)


@router.post("/lam-them/dat")
async def dat(
    body: DatBody,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    return await LamThemTaiQuayService(pool).dat(
        identity=identity,
        visit_id=body.visit_id,
        service_code=body.service_code,
        noi=body.noi,
        chon=body.chon,
        expected_order_id=body.expected_order_id,
        expected_version=body.expected_version,
        expected_state_revision=body.expected_state_revision,
        idempotency_key=body.idempotency_key,
    )


class DonBody(BaseModel):
    order_id: str = Field(min_length=1, max_length=64)


@router.post("/lam-them/dong-dich-vu")
async def dong_dich_vu(
    body: DonBody,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    return await LamThemTaiQuayService(pool).dong_dich_vu(
        identity=identity, order_id=body.order_id
    )


@router.post("/lam-them/hoan-tac-dich-vu")
async def hoan_tac_dich_vu(
    body: DonBody,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    return await LamThemTaiQuayService(pool).hoan_tac_dich_vu(
        identity=identity, order_id=body.order_id
    )
