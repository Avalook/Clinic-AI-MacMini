"""Foetal ultrasound measurements (W5, ADR-0012).

Thin router. The gate is ULTRASOUND_DOCTOR and nothing wider — the clinic asked
for that specifically, so it is stated here rather than folded into a general
"clinical writer" role.
"""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from clinicai.api.identity import ClinicRole, StaffIdentity, require_role
from clinicai.core.database import get_db_pool
from clinicai.services.ultrasound_board_service import (
    ULTRASOUND_ROLES,
    UltrasoundBoardService,
    group_by_patient,
)
from clinicai.services.ultrasound_service import UltrasoundService

router = APIRouter()

_SONOGRAPHER_GUARD = require_role(ClinicRole.ULTRASOUND_DOCTOR)


class UltrasoundMeasurements(BaseModel):
    """The seven standard foetal measurements: six in mm, EFW in grams.

    EFW is typed in by the doctor. It is NOT derived from BPD/HC/AC/FL, and
    should not be until the clinic signs off on a formula — see the service.
    """

    crl: float | str | None = None
    nt: float | str | None = None
    bpd: float | str | None = None
    hc: float | str | None = None
    ac: float | str | None = None
    fl: float | str | None = None
    efw: float | str | None = None


class UltrasoundSaveRequest(BaseModel):
    appointment_id: UUID
    clinic_patient_id: UUID
    measurements: UltrasoundMeasurements | None = None
    # Abnormality is the doctor's call, never inferred from the numbers.
    is_abnormal: bool | None = None
    status: Literal["in_progress", "completed"] | None = None
    note: str | None = Field(default=None, max_length=2000)


@router.post("/ultrasound/measurements")
async def save_ultrasound_measurements(
    body: UltrasoundSaveRequest,
    identity: StaffIdentity = Depends(_SONOGRAPHER_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Attach measurements to the appointment's visit, creating it if needed."""
    findings = await UltrasoundService(pool).save_measurements(
        appointment_id=str(body.appointment_id),
        clinic_patient_id=str(body.clinic_patient_id),
        measurements=(
            body.measurements.model_dump(exclude_unset=True)
            if body.measurements is not None
            else None
        ),
        is_abnormal=body.is_abnormal,
        status=body.status,
        identity=identity,
    )
    return {"ok": True, "findings": findings}


# ── Bộ phận Siêu âm: bốn màn ────────────────────────────────────────────────

_SONO_GUARD = require_role(*ULTRASOUND_ROLES)


@router.get("/ultrasound/queue")
async def sono_queue(
    identity: StaffIdentity = Depends(_SONO_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Hàng chờ siêu âm hôm nay, kèm bốn ô sẵn sàng."""
    return await UltrasoundBoardService(pool).queue(identity=identity)


@router.get("/ultrasound/rooms")
async def sono_rooms(
    identity: StaffIdentity = Depends(_SONO_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Ba phòng siêu âm: đang làm, đang chờ. Lọc theo cơ sở người đang đứng."""
    return await UltrasoundBoardService(pool).rooms(identity=identity)


@router.get("/ultrasound/records")
async def sono_records(
    signed: bool = Query(False, description="true = tab đã ký, false = tab soạn"),
    days: int = Query(1, ge=1, le=90),
    identity: StaffIdentity = Depends(_SONO_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Bản ghi siêu âm. Tab đã ký gom theo BỆNH NHÂN, không theo bản ghi —
    người tra cứu nghĩ theo "chị A có những phiếu nào"."""
    out = await UltrasoundBoardService(pool).records(
        identity=identity, signed=signed, days=days
    )
    if signed:
        return {"patients": group_by_patient(out["items"])}
    return out


class SonoDraftRequest(BaseModel):
    """Soạn kết quả siêu âm. KHÔNG có trường chữ ký — ký là đường riêng."""

    visit_id: UUID
    ultrasound_type: str = Field(min_length=1, max_length=120)
    # `findings` có CẤU TRÚC: mô tả từng tạng, từng số đo — không phải một đoạn
    # văn. Cột trong database là jsonb, và giữ đúng kiểu ở API nghĩa là về sau
    # tra "mọi ca có nội mạc > 14mm" là một câu truy vấn, không phải đọc chữ.
    findings: dict[str, Any] | None = None
    impression: str | None = None
    gestational_age_weeks: int | None = Field(default=None, ge=0, le=45)


@router.post("/ultrasound/draft", status_code=201)
async def sono_save_draft(
    body: SonoDraftRequest,
    identity: StaffIdentity = Depends(_SONO_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Lưu / cập nhật bản nháp kết quả.

    Bản ĐÃ KÝ không đi qua đây: trigger `ultrasound_signed_block_update` chặn
    mọi sửa nội dung sau chữ ký, và đó là chốt đúng — sửa một kết quả đã ký phải
    qua đường đính chính, có lý do, giữ lại bản cũ.
    """
    return await UltrasoundBoardService(pool).save_draft(
        identity=identity,
        visit_id=str(body.visit_id),
        ultrasound_type=body.ultrasound_type,
        findings=body.findings,
        impression=body.impression,
        gestational_age_weeks=body.gestational_age_weeks,
    )
