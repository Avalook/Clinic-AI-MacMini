"""Ký bệnh án, cho phép gửi kết quả, đính chính (Notion §6).

CHỈ BÁC SĨ. Guard nằm ở router VÀ trong service: router chặn sớm để người dùng
nhận một câu tiếng Việt, service chặn lần nữa vì nó là chỗ duy nhất mọi đường
gọi đều đi qua — kể cả một script nội bộ sau này.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field, field_validator

from clinicai.api.identity import (
    ClinicRole,
    StaffIdentity,
    get_current_identity,
    require_role,
)
from clinicai.core.database import get_db_pool
from clinicai.services.clinical_sign_service import ClinicalSignService
from clinicai.services.dinh_chinh_don import (
    MAX_CAUTION_LENGTH,
    MAX_DOSAGE_LENGTH,
    MAX_DRUG_NAME_LENGTH,
    MAX_PRESCRIPTIONS_PER_AMENDMENT,
    MAX_QUANTITY_LENGTH,
)

router = APIRouter()

# Quản lý KHÔNG có ở đây, có chủ ý: ký là trách nhiệm chuyên môn, không phải
# quyền hành chính.
_SIGN_GUARD = require_role(ClinicRole.DOCTOR)
_ULTRASOUND_SIGN_GUARD = require_role(ClinicRole.DOCTOR, ClinicRole.ULTRASOUND_DOCTOR)
_RELEASE_GUARD = require_role(ClinicRole.DOCTOR)
_AMEND_GUARD = require_role(ClinicRole.DOCTOR)


@router.get("/clinical/{visit_id:uuid}/status")
async def clinical_status(
    visit_id: UUID,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Trạng thái hồ sơ + những gì còn thiếu để ký được.

    ĐỌC mở cho mọi vai lâm sàng: CSKH cần biết đã được phép gửi chưa, Điều
    dưỡng cần biết hồ sơ đã khoá chưa. Chỉ GHI mới giới hạn ở bác sĩ.
    """
    return await ClinicalSignService(pool).status(
        identity=identity, visit_id=str(visit_id)
    )


class SignRequest(BaseModel):
    #: Phiên bản bệnh án bác sĩ đang xem (status.record_revision).
    expected_revision: int = Field(..., ge=0)


@router.post("/clinical/{visit_id:uuid}/sign", status_code=201)
async def sign(
    visit_id: UUID,
    body: SignRequest,
    identity: StaffIdentity = Depends(_SIGN_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Ký bệnh án. Sau bước này nội dung bị khoá (TT13/2011/TT-BYT)."""
    return await ClinicalSignService(pool).sign(
        identity=identity,
        visit_id=str(visit_id),
        expected_revision=body.expected_revision,
    )


class ReleaseRequest(BaseModel):
    note: str | None = Field(default=None, max_length=500)
    #: Bản đính chính bác sĩ ĐANG NHÌN. Bắt buộc khi state AMENDED;
    #: nullable cho SIGNED (chưa có amendment).
    expected_amendment_id: str | None = None


@router.post("/clinical/{visit_id:uuid}/release", status_code=201)
async def release(
    visit_id: UUID,
    body: ReleaseRequest,
    identity: StaffIdentity = Depends(_RELEASE_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """BƯỚC HAI: cho phép CSKH gửi kết quả cho bệnh nhân.

    Tách khỏi việc ký theo yêu cầu của Quang: bệnh án nguy hiểm thì bác sĩ ký
    xong vẫn giữ lại, CSKH không thấy nút gửi.
    """
    return await ClinicalSignService(pool).release(
        identity=identity,
        visit_id=str(visit_id),
        note=body.note,
        expected_amendment_id=body.expected_amendment_id,
    )


class AmendPrescriptionItem(BaseModel):
    """Một dòng Rx đã ký: schema chặt để payload lỗi không biến thành xoá dòng."""

    model_config = ConfigDict(extra="forbid")

    id: UUID | None = None
    drug_name: str = Field(min_length=1, max_length=MAX_DRUG_NAME_LENGTH)
    quantity: str | None = Field(default=None, max_length=MAX_QUANTITY_LENGTH)
    dosage: str | None = Field(default=None, max_length=MAX_DOSAGE_LENGTH)
    caution: str | None = Field(default=None, max_length=MAX_CAUTION_LENGTH)

    @field_validator("drug_name")
    @classmethod
    def drug_name_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Tên thuốc không được để trống")
        return value


class AmendRequest(BaseModel):
    # Bắt buộc, và CHECK ở tầng service cũng đòi — một bản đính chính không lý
    # do thì về sau không ai biết vì sao nội dung đổi.
    reason: str = Field(min_length=1, max_length=1000)
    # Bốn mục SOAP và/hoặc `don_thuoc`; service lọc và validate lại lần nữa.
    corrected: dict[str, Any]
    # Phiên bản clinical_record từ status; chặn tab cũ ghi đè SOAP hoặc tạo
    # amendment dựa trên một bệnh án đã thay đổi.
    expected_revision: int = Field(ge=0)
    # Fingerprint từ status; bắt buộc ở service khi sửa `don_thuoc`.
    expected_rx: str | None = Field(
        default=None, min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$"
    )

    @field_validator("corrected")
    @classmethod
    def validate_prescription_payload(cls, value: dict[str, Any]) -> dict[str, Any]:
        raw = value.get("don_thuoc")
        if raw is None:
            return value
        if not isinstance(raw, list):
            raise ValueError("Đơn thuốc đính chính phải là một danh sách")
        if len(raw) > MAX_PRESCRIPTIONS_PER_AMENDMENT:
            raise ValueError("Đơn thuốc đính chính có quá nhiều dòng")
        validated = [
            AmendPrescriptionItem.model_validate(item).model_dump(mode="json")
            for item in raw
        ]
        return {**value, "don_thuoc": validated}


@router.post("/clinical/{visit_id:uuid}/amend", status_code=201)
async def amend(
    visit_id: UUID,
    body: AmendRequest,
    identity: StaffIdentity = Depends(_AMEND_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Đính chính bản đã ký. Bản cũ được giữ nguyên.

    Nếu bản cũ đã được phép gửi: thu hồi quyền gửi và tạo việc thông báo lại
    cho CSKH.
    """
    return await ClinicalSignService(pool).amend(
        identity=identity,
        visit_id=str(visit_id),
        reason=body.reason,
        corrected=body.corrected,
        expected_revision=body.expected_revision,
        expected_rx=body.expected_rx,
    )


@router.post("/clinical/ultrasound/{ultrasound_id:uuid}/sign", status_code=201)
async def sign_ultrasound(
    ultrasound_id: UUID,
    identity: StaffIdentity = Depends(_ULTRASOUND_SIGN_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Bác sĩ siêu âm ký kết quả CỦA MÌNH."""
    return await ClinicalSignService(pool).sign_ultrasound(
        identity=identity, ultrasound_id=str(ultrasound_id)
    )
