"""Thai kỳ — đọc cho vai lâm sàng, ghi chỉ bác sĩ (``ThaiKyService`` gác lần hai)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from clinicai.api.identity import ClinicRole, StaffIdentity, require_role
from clinicai.core.database import get_db_pool
from clinicai.permissions.cua_quyen import cua_quyen
from clinicai.services.thai_ky_service import ThaiKyService

router = APIRouter()

_DOC_GUARD = require_role(
    ClinicRole.DOCTOR,
    ClinicRole.TKYK,
    ClinicRole.ULTRASOUND_DOCTOR,
    ClinicRole.NURSE_ULTRASOUND,
)
# Ghi thai kỳ: QUYỀN ghi bệnh án, không vai (28/09/2026).
_GHI_GUARD = cua_quyen("clinical.record.write")


class TaoThaiKyBody(BaseModel):
    clinic_patient_id: UUID
    visit_id: UUID | None = None
    # Ngày để dạng chuỗi: luật đọc ngày trả câu tiếng Việt, không để Pydantic
    # ném một mảng lỗi kỹ thuật.
    du_kien_sinh: str | None = Field(default=None, max_length=10)
    nguon_du_kien_sinh: str | None = Field(default=None, max_length=20)
    kinh_cuoi: str | None = Field(default=None, max_length=10)
    nguy_co_cao: bool = False
    ly_do_nguy_co: str | None = Field(default=None, max_length=2000)


class CapNhatThaiKyBody(BaseModel):
    du_kien_sinh: str | None = Field(default=None, max_length=10)
    nguon_du_kien_sinh: str | None = Field(default=None, max_length=20)
    kinh_cuoi: str | None = Field(default=None, max_length=10)
    nguy_co_cao: bool | None = None
    ly_do_nguy_co: str | None = Field(default=None, max_length=2000)
    ket_cuc: str | None = Field(default=None, max_length=20)
    ngay_ket_cuc: str | None = Field(default=None, max_length=10)


@router.get("/thai-ky")
async def doc_thai_ky(
    clinic_patient_id: UUID = Query(...),
    identity: StaffIdentity = Depends(_DOC_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    return await ThaiKyService(pool).doc(
        clinic_patient_id=str(clinic_patient_id), identity=identity
    )


@router.post("/thai-ky", status_code=201)
async def tao_thai_ky(
    body: TaoThaiKyBody,
    identity: StaffIdentity = Depends(_GHI_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    du_lieu = body.model_dump(exclude={"clinic_patient_id", "visit_id"})
    return await ThaiKyService(pool).tao(
        clinic_patient_id=str(body.clinic_patient_id),
        visit_id=str(body.visit_id) if body.visit_id else None,
        du_lieu=du_lieu,
        identity=identity,
    )


@router.patch("/thai-ky/{pregnancy_id}")
async def cap_nhat_thai_ky(
    pregnancy_id: UUID,
    body: CapNhatThaiKyBody,
    identity: StaffIdentity = Depends(_GHI_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    return await ThaiKyService(pool).cap_nhat(
        pregnancy_id=str(pregnancy_id),
        du_lieu=body.model_dump(exclude_unset=True),
        identity=identity,
    )
