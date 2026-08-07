"""Specialty exam forms (W5, ADR-0012)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from clinicai.api.identity import (
    CLINICAL_WRITE_ROLES,
    StaffIdentity,
    require_role,
)
from clinicai.core.database import get_db_pool
from clinicai.services.andrology_review_service import AndrologyReviewService
from clinicai.services.clinical_form_service import ClinicalFormService

router = APIRouter()

# Reading or filling in an exam form is clinical work (ROLE-02).
_FORM_GUARD = require_role(*CLINICAL_WRITE_ROLES)


class ClinicalFormSaveRequest(BaseModel):
    visit_id: UUID
    service_code: str = Field(min_length=1, max_length=64)
    form_data: dict[str, Any] = Field(default_factory=dict)


@router.get("/clinical-forms")
async def read_clinical_form(
    visit_id: UUID,
    service_code: str,
    identity: StaffIdentity = Depends(_FORM_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Read one form. Medical content is limited to clinical roles."""
    return await ClinicalFormService(pool).get_form(
        visit_id=str(visit_id), service_code=service_code, identity=identity
    )


@router.get("/clinical-forms/history")
async def read_exam_history(
    clinic_patient_id: UUID = Query(..., description="Bệnh nhân"),
    identity: StaffIdentity = Depends(_FORM_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Các lượt khám trước của một bệnh nhân — đủ nội dung phiếu, mới nhất trước."""
    return {
        "items": await ClinicalFormService(pool).lich_su_kham(
            clinic_patient_id=str(clinic_patient_id), identity=identity
        )
    }


@router.put("/clinical-forms")
async def save_clinical_form(
    body: ClinicalFormSaveRequest,
    identity: StaffIdentity = Depends(_FORM_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, object]:
    """Upsert one form. Refused once the visit is FINALIZED (ADR-0008)."""
    await ClinicalFormService(pool).save_form(
        visit_id=str(body.visit_id),
        service_code=body.service_code,
        form_data=body.form_data,
        identity=identity,
    )
    return {"ok": True}


class AndrologyReviewRequest(BaseModel):
    form_data: dict[str, Any] = Field(default_factory=dict)


@router.post("/clinical-forms/andrology-review")
async def andrology_review(
    body: AndrologyReviewRequest,
    identity: StaffIdentity = Depends(_FORM_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Cờ dưới ngưỡng WHO, gợi ý xét nghiệm di truyền, và BMI — cho form NK.

    POST chứ không phải GET vì nó nhận cả form đang gõ dở, chưa lưu: bác sĩ cần
    thấy cờ NGAY khi nhập tinh dịch đồ, không phải sau khi bấm lưu. Và nội dung
    lâm sàng không nên nằm trong query string, nơi nó vào log máy chủ.

    KHÔNG ghi gì và KHÔNG tạo chỉ định nào — mọi thứ trả về là gợi ý để bác sĩ
    đọc (Notion §13).
    """
    return await AndrologyReviewService(pool).review(
        identity=identity, form_data=body.form_data
    )
