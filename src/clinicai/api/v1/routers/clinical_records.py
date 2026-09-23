"""Clinical record writes (W5, ADR-0012).

The router admits every role that can write in *either* mode; which mode each
one is allowed is a rule about the record, so it lives in the service next to
the rest of them.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from clinicai.api.identity import (
    CLINICAL_WRITE_ROLES,
    StaffIdentity,
    get_current_identity,
    require_role,
)
from clinicai.core.database import get_db_pool
from clinicai.services.clinical_record_service import ClinicalRecordService
from clinicai.services.ho_so_lam_sang_doc import doc_ho_so

router = APIRouter()

# Ai ghi được bệnh án là QUYỀN `clinical.record.write`, hỏi trong hàm dịch vụ
# (CORE-B3, 23/09/2026). Cửa ngoài chỉ còn "đã đăng nhập".
_RECORD_GUARD = get_current_identity


class PrescriptionItem(BaseModel):
    # Existing rows round-trip prescription.id; new/legacy rows omit it.
    id: UUID | None = None
    drug_catalog_id: UUID | None = None
    drug_name: str | None = None
    quantity: str | None = None
    dosage: str | None = None
    caution: str | None = None


class ClinicalRecordSaveRequest(BaseModel):
    appointment_id: UUID
    clinic_patient_id: UUID
    # Nurse/reception mode: vitals and the chief complaint only.
    vitals_only: bool = False
    expected_revision: int | None = Field(default=None, ge=0, strict=True)
    approve_prescription_draft: bool = False
    chief_complaint: str | None = Field(default=None, max_length=2000)
    subjective: Any = None
    objective: Any = None
    assessment: Any = None
    plan: Any = None
    profile: dict[str, Any] | None = None
    # None means "leave the prescription alone"; [] means "clear it".
    prescriptions: list[PrescriptionItem] | None = None
    # CP6: sửa / bỏ dòng đơn đã có nhà thuốc / thu ngân đụng tới là ĐÍNH CHÍNH
    # và bắt buộc lý do (thiếu → 409 PRESCRIPTION_CORRECTION_REASON_REQUIRED).
    prescription_correction_reason: str | None = Field(default=None, max_length=1000)


#: Đọc hồ sơ lâm sàng: VAI lâm sàng (ROLE-02 — lễ tân, thu ngân, quản lý không
#: đọc nội dung y khoa), đúng tập mà trang cũ gác (`canReadClinical`).
_DOC_HO_SO_GUARD = require_role(*CLINICAL_WRITE_ROLES)


@router.get("/clinical-records/doc")
async def doc_ho_so_lam_sang(
    patient_id: str,
    appointment_id: str | None = None,
    visit_id: str | None = None,
    identity: StaffIdentity = Depends(_DOC_HO_SO_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Hồ sơ lâm sàng của một khách cho màn bệnh án (route giao diện từng tự đọc
    bảy bảng bằng Supabase — nay ở `services/ho_so_lam_sang_doc.py`)."""
    return await doc_ho_so(
        pool,
        identity=identity,
        patient_id=patient_id,
        appointment_id=appointment_id,
        visit_id=visit_id,
    )


@router.post("/clinical-records")
async def save_clinical_record(
    body: ClinicalRecordSaveRequest,
    identity: StaffIdentity = Depends(_RECORD_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Write the record for an appointment's visit, creating a draft if needed."""
    result = await ClinicalRecordService(pool).save(
        appointment_id=str(body.appointment_id),
        clinic_patient_id=str(body.clinic_patient_id),
        identity=identity,
        vitals_only=body.vitals_only,
        expected_revision=body.expected_revision,
        approve_prescription_draft=body.approve_prescription_draft,
        chief_complaint=body.chief_complaint,
        subjective=body.subjective,
        objective=body.objective,
        # "objective was absent" and "objective was sent as {}" mean different
        # things to the merge, and model_fields_set is the only way to tell.
        objective_sent="objective" in body.model_fields_set,
        assessment=body.assessment,
        plan=body.plan,
        profile=body.profile,
        prescriptions=(
            [item.model_dump() for item in body.prescriptions]
            if body.prescriptions is not None
            else None
        ),
        prescription_correction_reason=body.prescription_correction_reason,
    )
    return {"ok": True, **result}
