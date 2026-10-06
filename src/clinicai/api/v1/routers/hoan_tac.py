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
from clinicai.services.so_sua_chi_dinh_service import SoSuaChiDinhService

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


@router.post("/luot-kham/orders/{order_id}/thu-hoi-duyet")
async def thu_hoi_duyet(
    order_id: UUID,
    body: HoanTacBody | None = None,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Thu hồi lần bác sĩ duyệt kết quả — về "chờ bác sĩ duyệt"."""
    b = body or HoanTacBody()
    return await HoanTacService(pool).thu_hoi_duyet_ket_qua(
        order_id=str(order_id),
        identity=identity,
        ly_do=b.ly_do,
        xac_nhan=b.xac_nhan,
    )


# ── Sổ sửa / bỏ chỉ định (Khối 2, Tuyền chốt 06/10/2026) ─────────────────────


@router.get("/luot-kham/visits/{visit_id}/so-sua-chi-dinh")
async def so_sua_chi_dinh(
    visit_id: UUID,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Lịch sử thêm / bỏ / hoàn tác chỉ định của lượt (Khám · CLS · Điều trị ·
    Thuốc) — mới nhất trước; `chi_xem` = lượt hồ sơ cũ."""
    return await SoSuaChiDinhService(pool).doc(visit_id=str(visit_id), identity=identity)


@router.post("/luot-kham/so-sua-chi-dinh/{so_id}/hoan-tac")
async def hoan_tac_bo_chi_dinh(
    so_id: UUID,
    body: HoanTacBody | None = None,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Hoàn tác một lần BỎ chỉ định (nút duy nhất của thông báo bác sĩ chính)."""
    b = body or HoanTacBody()
    return await SoSuaChiDinhService(pool).hoan_tac(
        so_id=str(so_id), identity=identity, ly_do=b.ly_do
    )
