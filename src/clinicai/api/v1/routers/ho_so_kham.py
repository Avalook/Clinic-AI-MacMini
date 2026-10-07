"""HỒ SƠ KHÁM của một lượt — phần dịch vụ của lượt (07/10/2026).

Router mỏng; luật ở `services/ho_so_dich_vu.py`. Plan
docs/KE-HOACH-CHON-DICH-VU-HO-SO-KHAM.md (T1, T5).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel

from clinicai.api.identity import StaffIdentity, get_current_identity
from clinicai.core.database import get_db_pool
from clinicai.services import dieu_tri_ban_kham, ghi_chu_luot, ho_so_dich_vu

router = APIRouter(tags=["ho-so-kham"])


class DoiDichVuBody(BaseModel):
    service_type_id: UUID


class LamTaiBanKhamBody(BaseModel):
    expected_execution_revision: int
    attempt_id: UUID | None = None


class GhiChuBody(BaseModel):
    noi_dung: str = ""
    phien_ban: int = 0


@router.get("/ho-so-kham/{visit_id}/dich-vu")
async def doc_dich_vu(
    visit_id: UUID,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Dịch vụ của lượt, đổi được không, lịch sử đổi, phiếu cũ, "Khách đã đặt"."""
    return await ho_so_dich_vu.doc(pool, identity=identity, visit_id=str(visit_id))


@router.post("/ho-so-kham/{visit_id}/doi-dich-vu")
async def doi_dich_vu(
    visit_id: UUID,
    body: DoiDichVuBody,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Đổi dịch vụ khám ngay trong hồ sơ (quyền + luật ở service)."""
    return await ho_so_dich_vu.doi(
        pool,
        identity=identity,
        visit_id=str(visit_id),
        service_type_id=str(body.service_type_id),
    )


@router.get("/ho-so-kham/{visit_id}/dieu-tri")
async def doc_dieu_tri(
    visit_id: UUID,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Thẻ chỉ định điều trị của lượt: phiếu điều trị, trạng thái, nút."""
    return await dieu_tri_ban_kham.doc_the(
        pool, identity=identity, visit_id=str(visit_id)
    )


@router.post("/ho-so-kham/{visit_id}/dieu-tri/{order_id}/{lenh}")
async def lam_tai_ban_kham(
    visit_id: UUID,
    order_id: UUID,
    lenh: str,
    body: LamTaiBanKhamBody,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    """[Làm tại bàn khám] · [Xong] · hoàn tác (lam | xong | huy-lam |
    hoan-tac-xong) — luật + cửa tiền ở service."""
    return await dieu_tri_ban_kham.thao_tac(
        pool,
        identity=identity,
        visit_id=str(visit_id),
        order_id=str(order_id),
        lenh=lenh,
        expected_execution_revision=body.expected_execution_revision,
        attempt_id=str(body.attempt_id) if body.attempt_id else None,
        idempotency_key=idempotency_key,
    )


@router.get("/ho-so-kham/{visit_id}/ghi-chu")
async def doc_ghi_chu(
    visit_id: UUID,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Ô chữ tự do của lượt "Khác": bản mới nhất, có hiện / ghi được không."""
    return await ghi_chu_luot.doc(pool, identity=identity, visit_id=str(visit_id))


@router.put("/ho-so-kham/{visit_id}/ghi-chu")
async def luu_ghi_chu(
    visit_id: UUID,
    body: GhiChuBody,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Lưu thêm một phiên bản (409 khi màn cầm bản cũ)."""
    return await ghi_chu_luot.luu(
        pool,
        identity=identity,
        visit_id=str(visit_id),
        noi_dung=body.noi_dung,
        phien_ban=body.phien_ban,
    )
