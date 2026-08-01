"""Bảng điều khiển của chủ sản phẩm — CHỈ chạy ngoài production.

Trang này cho xem toàn cảnh hệ thống và nhận phản hồi kèm ảnh. Nó KHÔNG được
tồn tại ở production: nó liệt kê mọi tài khoản đăng nhập được, và một trang như
thế trên hệ đang phục vụ bệnh nhân là một bản đồ tấn công.

Chặn ở đây, không chỉ ở giao diện: một trang bị ẩn vẫn gọi được API nếu API
không tự từ chối.
"""

from __future__ import annotations

import os

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field

from clinicai.api.identity import ClinicRole, StaffIdentity, require_role
from clinicai.core.database import get_db_pool
from clinicai.services.console_service import ConsoleService

router = APIRouter()

_CONSOLE_GUARD = require_role(ClinicRole.MANAGEMENT)


def _refuse_in_production() -> None:
    # Đọc thẳng APP_ENV như phần còn lại của codebase (core/logging.py,
    # core/sentry.py). Mặc định coi là production khi không đặt: quên cấu hình
    # phải dẫn tới KHOÁ, không phải mở.
    if os.environ.get("APP_ENV", "production").lower() == "production":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không có trang này",
        )


class FeedbackIn(BaseModel):
    comment: str = Field(min_length=1, max_length=4000)
    severity: str = Field(default="nhan_xet")
    page_url: str | None = Field(default=None, max_length=500)
    role_at_time: str | None = Field(default=None, max_length=60)
    staff_name: str | None = Field(default=None, max_length=200)
    # Ảnh đã ghi ra đĩa bởi proxy Next; ở đây chỉ giữ đường dẫn.
    image_path: str | None = Field(default=None, max_length=500)


@router.get("/console/overview")
async def console_overview(
    response: Response,
    identity: StaffIdentity = Depends(_CONSOLE_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, object]:
    """Toàn cảnh: khối lượng việc, tài khoản, số liệu ngày, phản hồi."""
    _refuse_in_production()
    response.headers["Cache-Control"] = "no-store"
    return await ConsoleService(pool).overview(clinic_id=identity.clinic_id)


@router.post("/console/feedback", status_code=status.HTTP_201_CREATED)
async def add_feedback(
    body: FeedbackIn,
    identity: StaffIdentity = Depends(_CONSOLE_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, str]:
    """Ghi lại một phản hồi. Ngữ cảnh tự thu, không bắt gõ lại."""
    _refuse_in_production()
    if body.severity not in {"chan_dung", "lam_sai", "kho_hieu", "nhan_xet"}:
        raise HTTPException(status_code=422, detail="Mức độ không hợp lệ")
    new_id = await ConsoleService(pool).add_feedback(
        comment=body.comment,
        severity=body.severity,
        page_url=body.page_url,
        role_at_time=body.role_at_time or identity.role.value,
        staff_name=body.staff_name or identity.full_name,
        image_path=body.image_path,
    )
    return {"id": new_id}
