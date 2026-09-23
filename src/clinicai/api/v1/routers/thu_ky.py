"""Phạm vi của thư ký y khoa (Tuyền chốt 15/09/2026: thư ký theo bác sĩ).

Màn hình (server component Next) hỏi ở đây thay vì tự đọc Supabase: luật "thư ký
nào theo bác sĩ ấy" nằm ở một chỗ — clinicai.services.thu_ky_bac_si.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends

from clinicai.api.identity import (
    CLINICAL_WRITE_ROLES,
    StaffIdentity,
    get_current_identity,
    require_role,
)
from clinicai.core.database import get_db_pool
from clinicai.services import ho_so_khach_doc
from clinicai.services.thu_ky_bac_si import khach_duoc_xem, kiem_khach, pham_vi

router = APIRouter()


@router.get("/thu-ky/pham-vi")
async def xem_pham_vi(
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Người gọi có phải thư ký không; nếu có, đi cùng bác sĩ nào (có thể rỗng)."""
    return await pham_vi(pool, identity)


@router.get("/thu-ky/khach-duoc-xem")
async def danh_sach_khach_duoc_xem(
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Mã khách thư ký được xem. `gioi_han = false` = không phải thư ký."""
    ids = await khach_duoc_xem(pool, identity)
    return {"gioi_han": ids is not None, "ids": ids or []}


@router.get("/thu-ky/khach/{clinic_patient_id}")
async def duoc_xem_khach(
    clinic_patient_id: UUID,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """200 = được xem khách này; 403 kèm lý do khi thư ký không được."""
    await kiem_khach(pool, identity, str(clinic_patient_id))
    return {"ok": True}


@router.get("/ho-so-khach/{clinic_patient_id}/duoc-mo")
async def duoc_mo_ho_so(
    clinic_patient_id: UUID,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Người gọi được mở hồ sơ khách này không (24/09/2026 — trang hồ sơ bệnh
    nhân từng tự đọc bảng `appointment` để kiểm). Luật ở `ho_so_khach_doc.duoc_mo`."""
    return {"ok": await ho_so_khach_doc.duoc_mo(pool, identity, str(clinic_patient_id))}


@router.get("/ho-so-khach/{clinic_patient_id}/hanh-chinh")
async def ho_so_hanh_chinh(
    clinic_patient_id: UUID,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Thông tin hành chính + 20 lịch hẹn gần nhất."""
    return await ho_so_khach_doc.hanh_chinh(
        pool, identity=identity, khach=str(clinic_patient_id)
    )


@router.get("/ho-so-khach/{clinic_patient_id}/lich-su-lam-sang")
async def ho_so_lich_su_lam_sang(
    clinic_patient_id: UUID,
    # ROLE-02: nội dung y khoa chỉ cho vai lâm sàng.
    identity: StaffIdentity = Depends(require_role(*CLINICAL_WRITE_ROLES)),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Lượt khám (+ SOAP), xét nghiệm, thai kỳ."""
    return await ho_so_khach_doc.lich_su_lam_sang(
        pool, identity=identity, khach=str(clinic_patient_id)
    )


@router.get("/ho-so-khach/{clinic_patient_id}/cskh")
async def ho_so_nhat_ky_cskh(
    clinic_patient_id: UUID,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Nhật ký CSKH của khách (30 dòng mới nhất)."""
    return {
        "items": await ho_so_khach_doc.nhat_ky_cskh(
            pool, identity=identity, khach=str(clinic_patient_id)
        )
    }
