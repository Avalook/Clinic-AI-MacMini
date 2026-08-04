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
from pydantic import BaseModel, Field

from clinicai.api.identity import (
    ClinicRole,
    StaffIdentity,
    get_current_identity,
    require_role,
)
from clinicai.core.database import get_db_pool
from clinicai.services.clinical_sign_service import ClinicalSignService

router = APIRouter()

# Quản lý KHÔNG có ở đây, có chủ ý: ký là trách nhiệm chuyên môn, không phải
# quyền hành chính.
_SIGN_GUARD = require_role(ClinicRole.DOCTOR, ClinicRole.ULTRASOUND_DOCTOR)


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


@router.post("/clinical/{visit_id:uuid}/sign", status_code=201)
async def sign(
    visit_id: UUID,
    identity: StaffIdentity = Depends(_SIGN_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Ký bệnh án. Sau bước này nội dung bị khoá (TT13/2011/TT-BYT)."""
    return await ClinicalSignService(pool).sign(
        identity=identity, visit_id=str(visit_id)
    )


class ReleaseRequest(BaseModel):
    note: str | None = Field(default=None, max_length=500)


@router.post("/clinical/{visit_id:uuid}/release", status_code=201)
async def release(
    visit_id: UUID,
    body: ReleaseRequest,
    identity: StaffIdentity = Depends(_SIGN_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """BƯỚC HAI: cho phép CSKH gửi kết quả cho bệnh nhân.

    Tách khỏi việc ký theo yêu cầu của Quang: bệnh án nguy hiểm thì bác sĩ ký
    xong vẫn giữ lại, CSKH không thấy nút gửi.
    """
    return await ClinicalSignService(pool).release(
        identity=identity, visit_id=str(visit_id), note=body.note
    )


class AmendRequest(BaseModel):
    # Bắt buộc, và CHECK ở tầng service cũng đòi — một bản đính chính không lý
    # do thì về sau không ai biết vì sao nội dung đổi.
    reason: str = Field(min_length=1, max_length=1000)
    # Chỉ bốn mục SOAP; service lọc lại lần nữa. Giá trị là OBJECT (các cột
    # SOAP là jsonb, nội dung thật dạng {"chan_doan": "..."}), không phải chuỗi.
    corrected: dict[str, Any]


@router.post("/clinical/{visit_id:uuid}/amend", status_code=201)
async def amend(
    visit_id: UUID,
    body: AmendRequest,
    identity: StaffIdentity = Depends(_SIGN_GUARD),
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
    )


@router.post("/clinical/ultrasound/{ultrasound_id:uuid}/sign", status_code=201)
async def sign_ultrasound(
    ultrasound_id: UUID,
    identity: StaffIdentity = Depends(_SIGN_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Bác sĩ siêu âm ký kết quả CỦA MÌNH."""
    return await ClinicalSignService(pool).sign_ultrasound(
        identity=identity, ultrasound_id=str(ultrasound_id)
    )
