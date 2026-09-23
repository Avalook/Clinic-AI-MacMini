"""Biểu mẫu: mở phiếu, tự lưu, hoàn tất, và xuất bản bản mẫu mới.

Router mỏng. Mọi luật nằm ở `FormEngineService`; quyền kiểm bằng capability
(`result.form.fill`, `catalogue.form_template.publish`), không theo vai.

Người dùng hằng ngày không thấy chữ "Template Engine": họ chỉ thấy "Đã lưu
10:32" và nút [Hoàn tất].
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from clinicai.api.identity import StaffIdentity, get_current_identity
from clinicai.core.database import get_db_pool
from clinicai.services.form_engine_service import FormEngineService

router = APIRouter()


class MoPhieuBody(BaseModel):
    service_order_id: UUID
    form_id: str = Field(min_length=1, max_length=64)


class LuuBody(BaseModel):
    #: {ma_o: {gia_tri, nguon}} — nguồn lạ bị chặn ngay lúc lưu.
    du_lieu: dict[str, Any] = Field(default_factory=dict)
    expected_revision: int = Field(ge=0)
    #: Người THỰC HIỆN dịch vụ, khác người đang gõ.
    thuc_hien_boi: UUID | None = None


class HoanTatBody(BaseModel):
    expected_revision: int = Field(ge=0)
    thuc_hien_boi: UUID | None = None
    #: Bắt buộc khi đang sửa lại kết quả đã hoàn tất — đi vào
    #: `visit_amendment.reason`, nơi duy nhất giữ lý do.
    ly_do_sua: str | None = Field(default=None, max_length=1000)


class XuatBanBody(BaseModel):
    khung: list[dict[str, Any]] = Field(min_length=1)


@router.get("/bieu-mau")
async def danh_sach(
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Các biểu mẫu đang dùng — màn "Quản lý biểu mẫu" đọc cái này."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT form_id, version, ten, nhom, xuat_ban_luc FROM form_definition"
            " WHERE clinic_id = $1::uuid AND trang_thai = 'PUBLISHED'"
            " ORDER BY nhom, ten",
            identity.clinic_id,
        )
    return {"bieu_mau": [dict(r) for r in rows]}


@router.post("/phieu/mo")
async def mo_phieu(
    body: MoPhieuBody,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    return await FormEngineService(pool).mo_phieu(
        service_order_id=str(body.service_order_id),
        form_id=body.form_id,
        identity=identity,
    )


@router.post("/phieu/{phieu_id}/luu")
async def luu_nhap(
    phieu_id: UUID,
    body: LuuBody,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Tự lưu. Không phát sự kiện — nháp chưa phải sự thật nghiệp vụ."""
    return await FormEngineService(pool).luu_nhap(
        phieu_id=str(phieu_id),
        du_lieu=body.du_lieu,
        expected_revision=body.expected_revision,
        identity=identity,
        thuc_hien_boi=str(body.thuc_hien_boi) if body.thuc_hien_boi else None,
    )


@router.post("/phieu/{phieu_id}/hoan-tat")
async def hoan_tat(
    phieu_id: UUID,
    body: HoanTatBody,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Xác nhận toàn bộ nội dung hiện tại, kể cả câu mẫu không sửa.

    MỘT NÚT, NHIỀU SỰ THẬT (ChatGPT #156, Tuyền #157): lần đầu thì đóng luôn
    dịch vụ còn đang làm dở và phát `result.ready` nếu dịch vụ có kết quả ngay
    tại phòng; bấm sau khi [Sửa lại] thì phát `result.corrected`.
    """
    return await FormEngineService(pool).hoan_tat(
        phieu_id=str(phieu_id),
        expected_revision=body.expected_revision,
        identity=identity,
        thuc_hien_boi=str(body.thuc_hien_boi) if body.thuc_hien_boi else None,
        ly_do_sua=body.ly_do_sua,
    )


@router.post("/phieu/{phieu_id}/mo-sua")
async def mo_sua(
    phieu_id: UUID,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Mở lại phiếu đã hoàn tất để sửa. Kết quả cũ vẫn là kết quả chính thức.

    Trả về TOÀN BỘ phiếu hiện hành, không chỉ số revision: người thứ hai phải
    nhận đúng bản nháp đang có, kể cả những ô người đầu vừa gõ.
    """
    return await FormEngineService(pool).mo_sua(
        phieu_id=str(phieu_id), identity=identity
    )


class HuySuaBody(BaseModel):
    #: Bản nháp là của CHUNG — huỷ bằng số cũ là xoá cái người khác vừa gõ.
    expected_revision: int = Field(ge=0)


@router.post("/phieu/{phieu_id}/huy-sua")
async def huy_sua(
    phieu_id: UUID,
    body: HuySuaBody,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Bỏ bản sửa đang gõ dở. Bản chính thức không đổi một chữ."""
    return await FormEngineService(pool).huy_sua(
        phieu_id=str(phieu_id),
        identity=identity,
        expected_revision=body.expected_revision,
    )


@router.post("/bieu-mau/{form_id}/xuat-ban")
async def xuat_ban(
    form_id: str,
    body: XuatBanBody,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Bản mới thành bản đang dùng. Phiếu đã điền giữ nguyên bản cũ."""
    return await FormEngineService(pool).xuat_ban(
        form_id=form_id, khung=body.khung, identity=identity
    )
