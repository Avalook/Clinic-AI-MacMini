"""Nút HOÀN TÁC (Tuyền 01/10/2026: "không được để bất kể cái gì khoá hẳn").

Router mỏng: đọc thân, chuyển cho ``HoanTacService``. Quyền do hàm dịch vụ hỏi
trong chính giao dịch — ĐÚNG quyền của lệnh gốc (ai làm được thì rút lại được).

Thân chung của mọi lệnh: ``ly_do`` (tuỳ chọn) + ``xac_nhan``. Hoàn tác chạm
ràng buộc nghiệp vụ thật (đã thu tiền, khách đã về, kết quả đã duyệt) thì máy
chủ trả 409 ``CAN_XAC_NHAN`` kèm câu hệ quả; màn hỏi xác nhận, gửi lại với
``xac_nhan=true`` và lý do.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from clinicai.api.identity import StaffIdentity, get_current_identity
from clinicai.core.database import get_db_pool
from clinicai.services.hoan_tac_service import HoanTacService

router = APIRouter()


class HoanTacBody(BaseModel):
    ly_do: str | None = Field(default=None, max_length=2000)
    xac_nhan: bool = False


@router.post("/luot-kham/consultations/{consultation_id}/mo-lai")
async def mo_lai_kham(
    consultation_id: UUID,
    body: HoanTacBody | None = None,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Hoàn tác Khám xong / Hoàn tất / Xong tư vấn — phiên về lại đang khám."""
    b = body or HoanTacBody()
    return await HoanTacService(pool).mo_lai_kham(
        consultation_id=str(consultation_id),
        identity=identity,
        ly_do=b.ly_do,
        xac_nhan=b.xac_nhan,
    )


@router.post("/luot-kham/orders/{order_id}/huy-chi-dinh")
async def huy_chi_dinh(
    order_id: UUID,
    body: HoanTacBody | None = None,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Bỏ một chỉ định. Đã thu → hỏi xác nhận, khoản ấy thành tiền thừa ở quầy."""
    b = body or HoanTacBody()
    return await HoanTacService(pool).huy_chi_dinh(
        order_id=str(order_id),
        identity=identity,
        ly_do=b.ly_do,
        xac_nhan=b.xac_nhan,
    )


@router.post("/luot-kham/orders/{order_id}/execution/hoan-tac-xong")
async def hoan_tac_xong(
    order_id: UUID,
    body: HoanTacBody | None = None,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Hoàn tác "Xong" của một dịch vụ — về lại đang làm, kết quả giữ nguyên."""
    b = body or HoanTacBody()
    return await HoanTacService(pool).hoan_tac_xong_dich_vu(
        order_id=str(order_id),
        identity=identity,
        ly_do=b.ly_do,
        xac_nhan=b.xac_nhan,
    )


@router.post("/luot-kham/visits/{visit_id}/mo-lai-luot")
async def mo_lai_luot(
    visit_id: UUID,
    body: HoanTacBody | None = None,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Hoàn tác check-out / về giữa chừng — lượt mở lại."""
    b = body or HoanTacBody()
    return await HoanTacService(pool).mo_lai_luot(
        visit_id=str(visit_id),
        identity=identity,
        ly_do=b.ly_do,
        xac_nhan=b.xac_nhan,
    )
