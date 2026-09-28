"""Foetal ultrasound measurements (W5, ADR-0012).

Thin router. The gate is ULTRASOUND_DOCTOR and nothing wider — the clinic asked
for that specifically, so it is stated here rather than folded into a general
"clinical writer" role.
"""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

import asyncpg
import structlog
from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    Response,
    UploadFile,
)
from pydantic import BaseModel, Field

from clinicai.api.identity import StaffIdentity
from clinicai.core.database import get_db_pool
from clinicai.permissions.cua_quyen import cua_quyen
from clinicai.services.media_service import MediaService
from clinicai.services.ultrasound_board_service import (
    UltrasoundBoardService,
    group_by_patient,
)
from clinicai.services.ultrasound_service import UltrasoundService

logger = structlog.get_logger()
router = APIRouter()

# CHỈ LEGO (28/09/2026): cửa hỏi QUYỀN, không hỏi vai — xem permissions/cua_quyen.py.
_SONOGRAPHER_GUARD = cua_quyen("result.form.fill", moi_phong=True)


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

# CHỈ LEGO (28/09/2026): cửa hỏi QUYỀN, không hỏi vai — xem permissions/cua_quyen.py.
_SONO_GUARD = cua_quyen(
    "service.execute.start", "result.form.fill", "dispatch.manage", moi_phong=True
)


@router.get("/ultrasound/queue")
async def sono_queue(
    identity: StaffIdentity = Depends(_SONO_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Hàng chờ siêu âm hôm nay, kèm bốn ô sẵn sàng."""
    return await UltrasoundBoardService(pool).queue(identity=identity)


class NhanCaRequest(BaseModel):
    #: Trưởng ca / quản lý chọn bác sĩ siêu âm; bác sĩ siêu âm tự nhận thì bỏ trống.
    bac_si_id: UUID | None = None


@router.post("/ultrasound/queue/{work_item_id}/nhan")
async def nhan_ca_sieu_am(
    work_item_id: UUID,
    body: NhanCaRequest,
    identity: StaffIdentity = Depends(_SONO_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """ĐÃ NGHỈ (S0-6, 18/09/2026) — trả 410, không ghi gì.

    Endpoint rail cũ này ghi đè người đã nhận ca (người sau thắng, không 409).
    Không màn nào còn gọi: Phòng siêu âm dùng rail mới
    ``LuotKhamService.start_service`` (khoá dòng, người thứ hai nhận 409).
    Target Contract 18/09: không sửa logic cũ, chưa xoá cứng — ghi log người gọi
    để biết còn ai dùng; xoá hẳn khi một thời gian không còn lượt gọi nào.
    """
    logger.warning(
        "endpoint_retired_called",
        endpoint="POST /ultrasound/queue/{id}/nhan",
        staff_id=identity.staff_id,
        role=identity.role.value,
        work_item_id=str(work_item_id),
    )
    raise HTTPException(
        status_code=410,
        detail={
            "error": "ENDPOINT_RETIRED",
            "message": "Nhận ca siêu âm kiểu cũ đã ngừng — dùng màn Phòng siêu âm "
            "(nút Bắt đầu).",
        },
    )


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


# ── Ảnh siêu âm ────────────────────────────────────────────────────────────


@router.post("/ultrasound/{ultrasound_id}/image", status_code=201)
async def upload_image(
    ultrasound_id: UUID,
    file: UploadFile = File(...),
    identity: StaffIdentity = Depends(_SONO_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Gắn ảnh vào một bản ghi siêu âm.

    Tên tệp người dùng gửi CHỈ dùng làm nhãn; tên trên đĩa do hệ thống đặt.
    Kiểu tệp kiểm bằng mấy byte đầu, không bằng đuôi tên.
    """
    data = await file.read()
    return await MediaService(pool).attach_ultrasound_image(
        identity=identity,
        ultrasound_id=str(ultrasound_id),
        data=data,
        display_name=file.filename,
    )


@router.get("/ultrasound/image")
async def get_image(
    key: str,
    identity: StaffIdentity = Depends(_SONO_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> Response:
    """Đọc một ảnh. Khoá phải thuộc phòng khám của người hỏi — kiểm ở service."""
    data, mime = await MediaService(pool).read_ultrasound_image(
        identity=identity, key=key
    )
    return Response(
        content=data,
        media_type=mime,
        headers={
            # Ảnh bệnh nhân KHÔNG được nằm lại trong bộ đệm dùng chung. `private`
            # cho phép trình duyệt của chính người xem giữ, không cho proxy giữ.
            "Cache-Control": "private, max-age=300",
            # Trình duyệt không được tự đoán kiểu và chạy nội dung như HTML.
            "X-Content-Type-Options": "nosniff",
        },
    )
