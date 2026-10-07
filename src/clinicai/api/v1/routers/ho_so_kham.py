"""HỒ SƠ KHÁM của một lượt — dịch vụ của lượt + khối "Điều trị" (07/10/2026).

Router mỏng; luật ở `services/ho_so_dich_vu.py`. Plan
docs/KE-HOACH-CHON-DICH-VU-HO-SO-KHAM.md (T1, T5, T6).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from clinicai.api.identity import StaffIdentity, get_current_identity
from clinicai.core.database import get_db_pool
from clinicai.permissions.doc_bang import doi_mot_quyen
from clinicai.permissions.y_khoa import doc_duoc_in_phieu
from clinicai.services import ho_so_dich_vu, khoi_dieu_tri, lich_su_luot
from clinicai.services.doi_dich_vu_kham import QUYEN_DOI_TRONG_HO_SO

router = APIRouter(tags=["ho-so-kham"])


@router.get("/ho-so-kham/lich-su")
async def lich_su(
    clinic_patient_id: UUID,
    tu: str | None = Query(default=None, max_length=32),
    den: str | None = Query(default=None, max_length=32),
    dich_vu_id: UUID | None = None,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Popup "Lịch sử khám": MỌI lượt của khách (cả không phiếu, Notion).

    Ngày rác → bỏ lọc ấy (không 500). Đọc: người đọc y khoa / trưởng ca, hoặc
    khâu quầy / CSKH in phiếu."""
    async with pool.acquire() as conn:
        if not await doc_duoc_in_phieu(conn, identity):
            await doi_mot_quyen(
                conn,
                identity,
                QUYEN_DOI_TRONG_HO_SO,
                cau="Bạn không có quyền xem lịch sử khám.",
            )
        return await lich_su_luot.doc(
            conn,
            clinic_id=identity.clinic_id,
            clinic_patient_id=str(clinic_patient_id),
            tu=tu,
            den=den,
            dich_vu_id=str(dich_vu_id) if dich_vu_id else None,
        )


class DoiDichVuBody(BaseModel):
    service_type_id: UUID


class DieuTriBody(BaseModel):
    cam_nhan: str = Field(default="", max_length=5000)
    van_de_sau: str = Field(default="", max_length=5000)
    #: Bản người dùng đang nhìn (0 = chưa có) — chống đè.
    phien_ban: int = Field(default=0, ge=0)


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
    """Bản mới nhất của khối "Điều trị" (hồ sơ, bản in)."""
    return await khoi_dieu_tri.doc(pool, identity=identity, visit_id=str(visit_id))


@router.put("/ho-so-kham/{visit_id}/dieu-tri")
async def luu_dieu_tri(
    visit_id: UUID,
    body: DieuTriBody,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Tự lưu khối "Điều trị": thêm một phiên bản (không đè bản cũ)."""
    return await khoi_dieu_tri.luu(
        pool,
        identity=identity,
        visit_id=str(visit_id),
        cam_nhan=body.cam_nhan,
        van_de_sau=body.van_de_sau,
        phien_ban=body.phien_ban,
    )
