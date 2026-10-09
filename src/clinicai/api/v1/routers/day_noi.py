"""Khối chỉnh dây nối nghiệp vụ + tự nhắc việc (nhóm 5, 24/09/2026).

Router mỏng: quyền (`config.wiring.manage`) và mọi luật nằm trong service.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from clinicai.api.identity import StaffIdentity, get_current_identity
from clinicai.core.database import get_db_pool
from clinicai.services.day_noi_service import DayNoiService
from clinicai.services.nhac_viec_service import NhacViecService

router = APIRouter()


@router.get("/day-noi")
async def doc_day_noi(
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    return await DayNoiService(pool).doc(identity=identity)


class DatDayBody(BaseModel):
    ma: str = Field(min_length=1, max_length=64)
    gia_tri: Any


@router.patch("/day-noi/day")
async def dat_day(
    body: DatDayBody,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    return await DayNoiService(pool).dat_day(
        identity=identity, ma=body.ma, gia_tri=body.gia_tri
    )


class LoaiKhamBody(BaseModel):
    qua_tu_van: bool | None = None
    di_thang_phong: bool | None = None


@router.patch("/day-noi/loai-kham/{service_type_id}")
async def dat_loai_kham(
    service_type_id: UUID,
    body: LoaiKhamBody,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    return await DayNoiService(pool).dat_loai_kham(
        identity=identity,
        service_type_id=str(service_type_id),
        qua_tu_van=body.qua_tu_van,
        di_thang_phong=body.di_thang_phong,
    )


class ChuongBody(BaseModel):
    su_kien: str = Field(min_length=1, max_length=64)
    vai: list[str] = Field(max_length=20)
    bac_si_chinh: bool
    bat: bool


@router.put("/day-noi/chuong")
async def dat_chuong(
    body: ChuongBody,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    return await DayNoiService(pool).dat_chuong(
        identity=identity,
        su_kien=body.su_kien,
        vai=body.vai,
        bac_si_chinh=body.bac_si_chinh,
        bat=body.bat,
    )


class ViTriMoiBody(BaseModel):
    ten: str = Field(min_length=1, max_length=120)
    nhom_nghe: str
    ten_ngan: str | None = Field(default=None, max_length=200)
    tang: str | None = Field(default=None, max_length=60)
    room_id: UUID | None = None


@router.post("/day-noi/vi-tri", status_code=201)
async def tao_vi_tri(
    body: ViTriMoiBody,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    return await DayNoiService(pool).tao_vi_tri(
        identity=identity,
        ten=body.ten,
        nhom_nghe=body.nhom_nghe,
        ten_ngan=body.ten_ngan,
        tang=body.tang,
        room_id=str(body.room_id) if body.room_id else None,
    )


class ViTriSuaBody(BaseModel):
    ten: str | None = Field(default=None, max_length=120)
    ten_ngan: str | None = Field(default=None, max_length=200)
    tang: str | None = Field(default=None, max_length=60)
    #: Chữ cột Phòng của bảng lịch khi vị trí không gắn phòng thật.
    phong: str | None = Field(default=None, max_length=120)
    room_id: UUID | None = None
    bo_phong: bool = False
    is_active: bool | None = None


@router.patch("/day-noi/vi-tri/{vi_tri_id}")
async def sua_vi_tri(
    vi_tri_id: UUID,
    body: ViTriSuaBody,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    return await DayNoiService(pool).sua_vi_tri(
        identity=identity,
        vi_tri_id=str(vi_tri_id),
        ten=body.ten,
        ten_ngan=body.ten_ngan,
        tang=body.tang,
        phong=body.phong,
        room_id=str(body.room_id) if body.room_id else None,
        bo_phong=body.bo_phong,
        is_active=body.is_active,
    )


# ── Tự nhắc việc ───────────────────────────────────────────────────────────


@router.get("/nhac-viec")
async def nhac_viec_cua_toi(
    clinic_patient_id: UUID | None = None,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    return {
        "items": await NhacViecService(pool).cua_toi(
            identity=identity,
            clinic_patient_id=str(clinic_patient_id) if clinic_patient_id else None,
        )
    }


class NhacBody(BaseModel):
    noi_dung: str = Field(min_length=1, max_length=500)
    nhac_luc: str = Field(min_length=1, max_length=40)
    clinic_patient_id: UUID | None = None
    visit_id: UUID | None = None


@router.post("/nhac-viec", status_code=201)
async def tao_nhac(
    body: NhacBody,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    return await NhacViecService(pool).tao(
        identity=identity,
        noi_dung=body.noi_dung,
        nhac_luc=body.nhac_luc,
        clinic_patient_id=str(body.clinic_patient_id)
        if body.clinic_patient_id
        else None,
        visit_id=str(body.visit_id) if body.visit_id else None,
    )


@router.post("/nhac-viec/{nhac_id}/xong")
async def xong_nhac(
    nhac_id: UUID,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    return await NhacViecService(pool).xong(identity=identity, nhac_id=str(nhac_id))
