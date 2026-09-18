"""Lab triage API (T-P9.4).

POST /lab/triage/{lab_result_id} → runs the lab_triage sub-graph and
enforces the API-layer safety gate:

    triage_group == 'GROUP_C' AND reviewed_at IS NULL
        → raise SafetyGateError (HTTP 403)

The graph itself remains graceful (no raise) — it always terminates and
records the GROUP_C state on `escalation_note` + creates a LAB_REVIEW
URGENT task. This router enforces the hard medical safety gate at the
boundary: a patient-facing caller must not receive any answer until BS
has reviewed. Once reviewed_at is populated the gate releases.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, cast
from uuid import UUID

import asyncpg
import structlog
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from clinicai.api.exceptions import AIDisabledError
from clinicai.api.identity import (
    CLINICAL_WRITE_ROLES,
    PHYSICIAN_ROLES,
    ClinicRole,
    StaffIdentity,
    require_role,
)
from clinicai.api.rate_limit import InMemoryRateLimiter
from clinicai.core.database import get_db_pool
from clinicai.core.exceptions import SafetyGateError
from clinicai.graphs.lab_triage import build_lab_triage_subgraph
from clinicai.graphs.lab_triage.state import LabTriageState
from clinicai.llm.anthropic_client import AnthropicClient
from clinicai.services.lab_order_service import LabOrderService
from clinicai.services.lab_safety_service import LabReviewOutcome, LabSafetyService
from clinicai.services.thu_ky_bac_si import khach_duoc_xem, kiem_khach

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/lab", tags=["lab"])

# Ordering a test is a doctor's decision (W5, ADR-0012).
_ORDER_GUARD = require_role(*PHYSICIAN_ROLES)
# Entering a result is clinical work: doctors, nurses and the medical secretary.
# Reception and management are deliberately excluded.
_RESULT_GUARD = require_role(*CLINICAL_WRITE_ROLES)
_TRIAGE_GUARD = require_role(*CLINICAL_WRITE_ROLES)
# Màn Duyệt kết quả: bác sĩ + thư ký + quản lý (khớp NAV /duyet-ket-qua).
_REVIEW_READ_GUARD = require_role(
    ClinicRole.DOCTOR,
    ClinicRole.ULTRASOUND_DOCTOR,
    ClinicRole.TKYK,
    ClinicRole.MANAGEMENT,
)
LAB_TRIAGE_RATE_LIMIT = InMemoryRateLimiter(
    scope="lab-triage",
    limit=30,
    window_seconds=60,
)
_REVIEW_GUARD = require_role(*PHYSICIAN_ROLES)


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
    """Create a PENDING lab_result — the doctor has asked for a test."""
    lab_result_id = await LabOrderService(pool).order_test(
        clinic_patient_id=str(body.clinic_patient_id),
        test_name=body.test_name,
        appointment_id=str(body.appointment_id) if body.appointment_id else None,
        identity=identity,
    )
    return {"ok": True, "lab_result_id": lab_result_id}


@router.patch("/results/{lab_result_id}")
async def enter_lab_result(
    lab_result_id: UUID,
    body: LabResultEntryRequest,
    identity: StaffIdentity = Depends(_RESULT_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, object]:
    """Record what came back. Never finalises — that is a separate gate."""
    if identity.co_vai({ClinicRole.TKYK}):
        # Thư ký chỉ nhập kết quả cho khách của bác sĩ mình (20260915000020).
        patient_id = await pool.fetchval(
            "SELECT clinic_patient_id::text FROM lab_result"
            " WHERE lab_result_id = $1::uuid AND clinic_id = $2::uuid",
            str(lab_result_id),
            identity.clinic_id,
        )
        if patient_id:
            await kiem_khach(pool, identity, patient_id)
    await LabOrderService(pool).enter_result(
        lab_result_id=str(lab_result_id),
        result_value=body.result_value,
        result_link=body.result_link,
        lab_provider=body.lab_provider,
        identity=identity,
    )
    return {"ok": True}


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
    return {"items": items}


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


def get_llm_client(request: Request) -> AnthropicClient:
    """FastAPI dependency: yields the application's AnthropicClient singleton."""
    client = request.app.state.llm_client
    if client is None:
        raise AIDisabledError("Tính năng AI chưa bật trên hệ thống này.")
    return cast(AnthropicClient, client)


class LabTriageResponse(BaseModel):
    """Patient-facing safe response surface for a triaged lab result."""

    lab_result_id: UUID
    triage_group: str | None
    requires_doctor_review: bool
    response_to_patient: str | None
    escalation_note: str | None
    task_ids: list[UUID]
    error: str | None


def _reviewed_at_of(result: dict[str, Any]) -> Any:
    """Pull `reviewed_at` off the LabResultRow inside graph output, if any."""
    row = result.get("lab_result_row")
    return getattr(row, "reviewed_at", None) if row is not None else None


@router.post("/triage/{lab_result_id}", response_model=LabTriageResponse)
async def triage_lab_result(
    lab_result_id: UUID,
    pool: Annotated[asyncpg.Pool, Depends(get_db_pool)],
    identity: Annotated[StaffIdentity, Depends(_TRIAGE_GUARD)],
    llm_client: Annotated[AnthropicClient, Depends(get_llm_client)],
    _rate_limit: Annotated[None, Depends(LAB_TRIAGE_RATE_LIMIT)],
) -> LabTriageResponse:
    """Run lab_triage on a single lab_result_id, enforcing the GROUP_C gate.

    Returns the triage outcome. Raises SafetyGateError (HTTP 403) when
    the result is GROUP_C and not yet reviewed by a doctor.
    """
    graph = build_lab_triage_subgraph(pool=pool, llm_client=llm_client)
    state = LabTriageState(
        lab_result_id=lab_result_id,
        clinic_id=UUID(identity.clinic_id),
    )
    result = await graph.ainvoke(state)

    triage_group = result.get("triage_group")
    reviewed_at = _reviewed_at_of(result)

    if triage_group == "GROUP_C" and reviewed_at is None:
        logger.warning(
            "api.lab.triage.safety_gate_blocked",
            lab_result_id=str(lab_result_id),
            triage_group=triage_group,
        )
        raise SafetyGateError(
            f"GROUP_C lab_result {lab_result_id} chưa được BS review — "
            "không thể trả kết quả cho BN."
        )

    return LabTriageResponse(
        lab_result_id=lab_result_id,
        triage_group=triage_group,
        requires_doctor_review=bool(result.get("requires_doctor_review", False)),
        response_to_patient=result.get("response_to_patient"),
        escalation_note=result.get("escalation_note"),
        task_ids=list(result.get("task_ids") or []),
        error=result.get("error"),
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
    identity: StaffIdentity = Depends(_RESULT_GUARD),
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
