"""Lab API: chỉ định xét nghiệm, ghi kết quả, duyệt/chốt, quyết báo khách.

Cửa `POST /lab/triage/{id}` (AI phân nhóm qua LangGraph) đã gỡ 24/11/2026 —
không màn nào gọi; bác sĩ quyết báo kết quả (xem `lab_release_decision`).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

import asyncpg
import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from clinicai.api.identity import (
    StaffIdentity,
)
from clinicai.api.nghi_huu import CHI_DINH_MOI, KET_QUA_MOI, bao_da_nghi
from clinicai.core.database import get_db_pool
from clinicai.core.tran import canh_bao_neu_day
from clinicai.permissions.cua_quyen import cua_quyen
from clinicai.permissions.y_khoa import cua_ghi_y_khoa, cua_y_khoa
from clinicai.services.lab_safety_service import LabReviewOutcome, LabSafetyService
from clinicai.services.thu_ky_bac_si import khach_duoc_xem

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/lab", tags=["lab"])

# Ordering a test is a doctor's decision (W5, ADR-0012).
# CHỈ LEGO (28/09/2026): cửa hỏi QUYỀN, không hỏi vai — xem permissions/cua_quyen.py.
_ORDER_GUARD = cua_quyen("clinical.order.place")
# Entering a result is clinical work: doctors, nurses and the medical secretary.
# Reception and management are deliberately excluded.
_RESULT_GUARD = cua_ghi_y_khoa
_RESULT_READ_GUARD = cua_y_khoa
# Màn Duyệt kết quả: bác sĩ + thư ký + quản lý (khớp NAV /duyet-ket-qua).
_REVIEW_READ_GUARD = cua_y_khoa
#: Duyệt / chốt kết quả = khối `duyet_ket_qua`. Hỏi QUYỀN, không hỏi vai
#: (24/09/2026).
_REVIEW_GUARD = cua_quyen(
    "result.review.approve",
    cau="Bạn không có quyền duyệt kết quả.",
)


class LabOrderRequest(BaseModel):
    """Order a lab test for a patient."""

    clinic_patient_id: UUID
    test_name: str = Field(min_length=1, max_length=200)
    appointment_id: UUID | None = None


class LabResultEntryRequest(BaseModel):
    """Attach a summary and/or the provider's document to a pending result."""

    result_value: str | None = Field(default=None, max_length=4000)
    result_link: str | None = Field(default=None, max_length=2000)
    lab_provider: str | None = Field(default=None, max_length=200)


class LabReviewRequest(BaseModel):
    """Bind the reviewed result to the patient chart visible to the doctor."""

    clinic_patient_id: UUID


class LabReviewResponse(BaseModel):
    """Durable audit state after a doctor finalises the result."""

    lab_result_id: UUID
    clinic_patient_id: UUID
    triage_group: str
    is_finalized: bool
    reviewed_by_staff_id: UUID
    reviewed_at: datetime
    already_finalized: bool


@router.post("/orders", status_code=201)
async def order_lab_test(
    body: LabOrderRequest,
    identity: StaffIdentity = Depends(_ORDER_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, object]:
    """ĐÃ NGHỈ (Slice 1, 18/09/2026) — rail cũ, trả 410, không ghi gì."""
    bao_da_nghi(
        endpoint="POST /lab/orders",
        identity=identity,
        thay_bang=CHI_DINH_MOI,
    )


@router.patch("/results/{lab_result_id}")
async def enter_lab_result(
    lab_result_id: UUID,
    body: LabResultEntryRequest,
    identity: StaffIdentity = Depends(_RESULT_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, object]:
    """ĐÃ NGHỈ (Slice 1, 18/09/2026) — rail cũ, trả 410, không ghi gì."""
    bao_da_nghi(
        endpoint="PATCH /lab/results/{id}",
        identity=identity,
        thay_bang=KET_QUA_MOI,
        lab_result_id=lab_result_id,
    )


@router.get("/results/cho-duyet")
async def ket_qua_cho_duyet(
    identity: StaffIdentity = Depends(_REVIEW_READ_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Kết quả đã về, chưa chốt — hàng chờ màn Duyệt kết quả.

    Chuyển từ đọc thẳng Supabase ở trang (15/09/2026) để lọc được theo thư ký:
    thư ký chỉ thấy kết quả khách của bác sĩ mình được phân.
    """
    duoc = await khach_duoc_xem(pool, identity)
    rows = await pool.fetch(
        """
        SELECT r.lab_result_id::text, r.clinic_patient_id::text, r.test_code,
               r.test_name, r.result_value, r.result_numeric, r.result_unit,
               r.reference_range_low, r.reference_range_high, r.flag,
               r.triage_group, r.requires_doctor_review, r.is_finalized,
               r.result_received_at, r.external_ref,
               p.full_name, p.phone_primary
          FROM lab_result r
          LEFT JOIN patient p
            ON p.clinic_patient_id = r.clinic_patient_id
           AND p.clinic_id = r.clinic_id
         WHERE r.clinic_id = $1::uuid
           AND NOT r.is_finalized
           AND coalesce(nullif(btrim(coalesce(r.result_value, '')), ''),
                        nullif(btrim(coalesce(r.external_ref, '')), '')) IS NOT NULL
           AND r.clinic_patient_id::text
               = ANY(coalesce($2::text[], ARRAY[r.clinic_patient_id::text]))
         ORDER BY r.result_received_at DESC
         LIMIT 100
        """,
        identity.clinic_id,
        duoc,
    )
    items = []
    for r in rows:
        d = dict(r)
        d["patient"] = {
            "full_name": d.pop("full_name"),
            "phone_primary": d.pop("phone_primary"),
        }
        items.append(d)
    # Trần 100 kết quả chờ duyệt. Chạm trần là có kết quả bất thường nằm ngoài
    # trang mà bác sĩ không biết.
    return {
        "items": items,
        "bi_cat": canh_bao_neu_day("xet_nghiem.cho_duyet", len(rows), 100),
        "tran": 100,
    }


@router.post(
    "/results/{lab_result_id}/review",
    response_model=LabReviewResponse,
)
async def review_and_finalize_lab_result(
    lab_result_id: UUID,
    body: LabReviewRequest,
    identity: StaffIdentity = Depends(_REVIEW_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> LabReviewResponse:
    """Doctor-only review/finalise gate, scoped to clinic and patient."""
    outcome: LabReviewOutcome = await LabSafetyService(pool).finalize_review(
        lab_result_id=lab_result_id,
        clinic_patient_id=body.clinic_patient_id,
        identity=identity,
    )
    return LabReviewResponse(
        lab_result_id=outcome.lab_result_id,
        clinic_patient_id=outcome.clinic_patient_id,
        triage_group=outcome.triage_group,
        is_finalized=outcome.is_finalized,
        reviewed_by_staff_id=outcome.reviewed_by_staff_id,
        reviewed_at=outcome.reviewed_at,
        already_finalized=outcome.already_finalized,
    )


# ─── Lab release decision (Phase 4, cluster #4) ──────────────────────────────
# Patient notification is a clinical safety boundary, not presentation logic.
#
# ĐỔI 15/09/2026 — BÁC SĨ QUYẾT, KHÔNG PHẢI NHÓM AI. Bản cũ chỉ cho báo khi
# `triage_group = GROUP_A` VÀ đã chốt. Nhóm do AI phân; không có AI (hoặc AI xếp
# B/C) thì một kết quả bác sĩ ĐÃ duyệt và chốt vẫn không bao giờ được báo khách.
# CONTEXT v1.0: "Upload → kiểm đúng khách/chỉ định → bác sĩ đánh giá/cho phép
# gửi → gửi và ghi kết quả". Nay: đã chốt (ràng buộc DB bắt buộc có người duyệt
# + thời điểm duyệt) là được báo; nhóm AI chỉ còn là nhãn gợi ý.


class LabReleaseDecision(BaseModel):
    """Whether a lab result may be released to the patient, and why."""

    allowed: bool
    label: str


@router.get(
    "/results/{lab_result_id}/release",
    response_model=LabReleaseDecision,
)
async def lab_release_decision(
    lab_result_id: UUID,
    identity: StaffIdentity = Depends(_RESULT_READ_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> LabReleaseDecision:
    """Can this lab result be told to the patient?

    Finalized by a doctor → allowed=True. Everything else fails closed.
    """
    row = await pool.fetchrow(
        """
        SELECT triage_group, is_finalized
          FROM lab_result
         WHERE lab_result_id = $1
           AND clinic_id = $2::uuid
        """,
        lab_result_id,
        identity.clinic_id,
    )
    if row is None:
        return LabReleaseDecision(
            allowed=False, label="Không tìm thấy kết quả xét nghiệm"
        )

    triage = row["triage_group"]
    finalized = bool(row["is_finalized"])

    if finalized:
        if triage == "GROUP_C":
            return LabReleaseDecision(
                allowed=True,
                label="Bác sĩ đã duyệt — được báo BN (bất thường: báo trực tiếp)",
            )
        return LabReleaseDecision(allowed=True, label="Bác sĩ đã duyệt — được báo BN")
    return LabReleaseDecision(allowed=False, label="Chờ bác sĩ duyệt — KHÔNG báo BN")
