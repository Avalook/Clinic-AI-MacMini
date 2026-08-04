"""Liên kết bệnh nhân và đồng ý chia sẻ hồ sơ — §6.5, cho mọi dịch vụ khám.

Bốn cửa ghi ở đây đều là quyết định về quyền riêng tư, nên chúng KHÔNG dùng
chung quyền với các màn hình lâm sàng khác: xem `CONSENT_WRITE_ROLES`.

`GET /patients/{id}/shared-form` là chỗ DUY NHẤT hệ thống đọc hồ sơ của một
bệnh nhân trong buổi khám của một bệnh nhân khác. Mọi màn hình muốn ghép dữ
liệu hai người phải đi qua nó.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from clinicai.api.identity import StaffIdentity, get_current_identity, require_role
from clinicai.core.database import get_db_pool
from clinicai.services.consent_service import CONSENT_WRITE_ROLES, ConsentService

router = APIRouter()

# `sorted` để thứ tự vai trong thông báo lỗi không đổi giữa các lần chạy —
# frozenset lặp theo thứ tự băm, và một thông báo đổi chữ mỗi lần khởi động thì
# không tra cứu được.
_WRITE_GUARD = require_role(*sorted(CONSENT_WRITE_ROLES))


@router.get("/patients/{patient_id}/links")
async def links(
    patient_id: UUID,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Ai liên kết với bệnh nhân này, và mỗi chiều chia sẻ được form nào."""
    return {
        "partners": await ConsentService(pool).linked_partners(
            identity=identity, patient_id=str(patient_id)
        )
    }


@router.get("/patients/{patient_id}/shared-form")
async def shared_form(
    patient_id: UUID,
    viewing_patient_id: UUID = Query(
        ..., description="Bệnh nhân đang được khám — người sẽ NHÌN THẤY hồ sơ."
    ),
    form_code: str = Query(..., description="Mã form, ví dụ NK / HMVS."),
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Hồ sơ của `patient_id` hiện trong buổi khám của `viewing_patient_id`.

    Trả `allowed: false` kèm danh sách rỗng khi chưa có đồng ý — màn hình phải
    nói rõ "chưa được phép xem", không để trống. Để trống sẽ được đọc thành
    "chưa làm" và bác sĩ sẽ chỉ định lại lần nữa.
    """
    return await ConsentService(pool).shared_form(
        identity=identity,
        subject_patient_id=str(patient_id),
        viewing_patient_id=str(viewing_patient_id),
        form_code=form_code,
    )


class LinkRequest(BaseModel):
    patient_a: UUID
    patient_b: UUID
    #: SPOUSE · PARTNER · FAMILY
    relation: str = Field(max_length=20)
    note: str | None = Field(default=None, max_length=500)


@router.post("/patients/links")
async def create_link(
    body: LinkRequest,
    identity: StaffIdentity = Depends(_WRITE_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Ghi nhận quan hệ. Liên kết KHÔNG mở quyền đọc — cần thêm bản đồng ý."""
    return await ConsentService(pool).link(
        identity=identity,
        patient_a=str(body.patient_a),
        patient_b=str(body.patient_b),
        relation=body.relation,
        note=body.note,
    )


class GrantRequest(BaseModel):
    #: Hồ sơ của ai được chia sẻ.
    subject_patient_id: UUID
    #: Ai được xem.
    grantee_patient_id: UUID
    #: Mã form, hoặc ['ALL']. Danh sách rỗng bị từ chối.
    form_codes: list[str] = Field(min_length=1)
    #: Bản đồng ý có chữ ký — mã/đường dẫn tài liệu. Bắt buộc.
    source_document: str = Field(min_length=1, max_length=300)


@router.post("/patients/consents")
async def grant(
    body: GrantRequest,
    identity: StaffIdentity = Depends(_WRITE_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    return await ConsentService(pool).grant(
        identity=identity,
        subject_patient_id=str(body.subject_patient_id),
        grantee_patient_id=str(body.grantee_patient_id),
        form_codes=body.form_codes,
        source_document=body.source_document,
    )


class RevokeRequest(BaseModel):
    #: Bắt buộc — database cũng chặn thu hồi không lý do.
    reason: str = Field(min_length=1, max_length=500)


@router.post("/patients/consents/{consent_id}/revoke")
async def revoke(
    consent_id: UUID,
    body: RevokeRequest,
    identity: StaffIdentity = Depends(_WRITE_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    return await ConsentService(pool).revoke(
        identity=identity, consent_id=str(consent_id), reason=body.reason
    )
